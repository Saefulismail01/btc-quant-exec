# Signal Service Integration Guide — Tier 0c

**Doc type:** Patch instruction (diff / hook description)  
**Target files (READ-ONLY, do NOT edit):**
- `backend/app/use_cases/signal_service.py`
- `backend/app/use_cases/position_manager.py`

**Status:** Proposal — no production code changed.  
All hook code in this doc is illustrative pseudocode showing *where* and *how*
to integrate once Tier 0b/0c enters a proper git branch.

---

## 1. Summary of changes required

| # | File | Hook point | Change type |
|---|------|-----------|-------------|
| 1 | `signal_service.py` | End of `get_signal()` | Insert `SignalSnapshot` before returning `SignalResponse` |
| 2 | `signal_service.py` | OHLCV data load | Extract `candle_open_ts` from `df.iloc[-1]` timestamp |
| 3 | `position_manager.py` | After `place_order()` call | Call `repo.update_linkage(snapshot_id, ORDER_PLACED, order_id)` |
| 4 | `position_manager.py` | `insert_trade()` call (line ~922) | Remove `candle_open_ts=int(time.time()*1000)` — now in snapshot |
| 5 | Reconciliation worker | Post-fill detection | Call `repo.update_linkage(snapshot_id, ORDER_FILLED)` via trades_lighter join |

---

## 2. Bug: `candle_open_ts` in `position_manager.py:922`

### Current (buggy) code

```python
# backend/app/use_cases/position_manager.py:922 (READ-ONLY reference)
self.repo.insert_trade(
    ...
    candle_open_ts=int(time.time() * 1000),  # BUG: inserts "now" not candle timestamp
    ...
)
```

### Root cause

`candle_open_ts` is supposed to hold the timestamp of the 4H candle that
generated the signal. Instead it stores `time.time()` — the moment the trade
was placed (minutes or hours after the candle closed).

### Fix strategy

Move `candle_open_ts` to `signal_snapshots` where it is captured from the OHLCV
dataframe at signal generation time, not at order placement time.
The `live_trades` field `candle_open_ts` can be deprecated or left as-is (it
will always hold an inaccurate value until code is updated, which is OK since
`signal_snapshots` becomes the authoritative source).

---

## 3. Hook 1: `signal_service.py` — snapshot insert at signal generation

### Where to insert

Inside `get_signal()`, just before the final `return SignalResponse(...)` at
the end of the success path (around line 633 in current code).

### What data is available at that point

| Variable | Value |
|----------|-------|
| `df.iloc[-1]` | Last OHLCV row — its `.name` or `.timestamp` column is the candle open |
| `ai_bias` | MLP directional bias ("BULL" / "BEAR" / "NEUTRAL") |
| `ai_conf` | MLP confidence (0..100 scale, divide by 100 for 0..1) |
| `hmm_label` | L1 regime label string |
| `hmm_confidence` | L1 changepoint probability |
| `l2_ema_vote` | From `ema_svc.get_vote()` |
| `l2` | `bool` — L2 aligned |
| `vol_label` | L4 vol regime ("low" / "mid" / "high") |
| `vol_ratio` | L4 current/long-run ratio |
| `atr14_now` | ATR at signal |
| `funding_rate` | Funding at signal |
| `open_interest` | OI at signal |
| `spectrum.conviction_pct` | Signal conviction |
| `verdict` | Final signal verdict |

### Pseudocode

```python
# --- PROPOSED ADDITION in signal_service.get_signal() ---
# (add near line 630, BEFORE return SignalResponse(...))

import sys
sys.path.insert(0, "docs/research/rr_improvement_2026q2/proposed_code")
# ^ In production branch: remove sys.path hack, add proper import

from signal_snapshot.models import SignalSnapshot
from signal_snapshot.signal_snapshot_repository import SignalSnapshotRepository

# Candle open timestamp — from DataFrame, NOT time.time()
# df is the OHLCV DataFrame loaded from DuckDB at step 1
candle_open_ts_ms = int(df.iloc[-1].name.timestamp() * 1000)
# Note: df.iloc[-1].name is a Timestamp when index is DatetimeIndex.
# If df has a 'timestamp' column instead: int(df.iloc[-1]['timestamp'])

snapshot = SignalSnapshot.create(
    candle_open_ts=candle_open_ts_ms,        # FIX: candle timestamp, not time.time()
    intended_side="LONG" if trend_short == "BULL" else "SHORT",
    intended_size_usdt=margin_usd,           # from risk_manager output
    intended_sl_price=sl,
    intended_tp_price=tp1,
    # Layer snapshots
    l1_regime=hmm_label,
    l1_changepoint_prob=hmm_confidence,
    l2_ema_vote=ema_vote_numeric,            # need to expose numeric vote from ema_svc
    l2_aligned=l2,
    l3_prob_bull=mlp_probs.get("bull"),      # expose per-class probs from ai_svc
    l3_prob_neutral=mlp_probs.get("neutral"),
    l3_prob_bear=mlp_probs.get("bear"),
    l3_class=ai_bias,
    l4_vol_regime=vol_label,
    l4_current_vol=vol_current,
    l4_long_run_vol=vol_long_run,
    # Market context
    atr_at_signal=atr14_now,
    funding_at_signal=funding_rate,
    oi_at_signal=open_interest,
    cvd_at_signal=cvd_value,                 # add CVD fetch if not already done
    htf_zscore_at_signal=(price_now - ema50_now) / atr14_now if atr14_now else None,
    # Aggregate
    signal_verdict=verdict,
    signal_conviction=spectrum.conviction_pct,
)

snapshot_repo = SignalSnapshotRepository(db_conn)  # inject via constructor
snapshot_id = snapshot_repo.insert(snapshot)
# Pass snapshot_id downstream to position_manager via SignalResponse or shared context
```

### Minor refactoring needed in `signal_service.py`

1. **Expose MLP per-class probabilities:** `ai_svc.get_confidence()` currently returns
   `(bias, conf)`. Needs a companion `get_class_probs()` or updated signature to
   return `(bias, conf, probs_dict)`. This is the most significant change.

2. **Expose numeric L2 EMA vote:** `ema_svc` likely has a numeric vote internally;
   surfacing it as a float is needed for `l2_ema_vote`.

3. **CVD value:** Already fetched in `market_repository` — extract and pass through.

4. **Inject `SignalSnapshotRepository`:** Either via module-level singleton (consistent
   with current `_spectrum`, `_vol_est` pattern) or via constructor injection
   if `get_signal()` is refactored to accept a context object.

---

## 4. Hook 2: `position_manager.py` — update linkage after order placement

### Where to insert

After `market_result = await self.gateway.create_market_order(...)` succeeds
and `trade_id = market_result.order_id` is set (around line 907–908).

### Pseudocode

```python
# --- PROPOSED ADDITION in position_manager._open_position() ---
# (add after trade_id = market_result.order_id, before insert_trade)

from signal_snapshot.models import LinkStatus
from signal_snapshot.signal_snapshot_repository import SignalSnapshotRepository

# snapshot_id comes from signal — needs to be threaded through SignalResponse
# Option A: add snapshot_id field to SignalResponse schema
# Option B: store snapshot_id in a short-lived context dict keyed by signal hash

snapshot_id = signal.snapshot_id  # if added to SignalResponse
if snapshot_id:
    snapshot_repo.update_linkage(
        snapshot_id=snapshot_id,
        link_status=LinkStatus.ORDER_PLACED,
        lighter_order_id=trade_id,
        ts_order_placed_ms=int(time.time() * 1000),
    )
```

### Threading `snapshot_id` through the call chain

The cleanest approach (minimal diff):

1. Add optional `snapshot_id: Optional[str] = None` field to `SignalResponse` schema
   (`backend/app/schemas/signal.py`).
2. `signal_service.get_signal()` populates it after `snapshot_repo.insert()`.
3. `position_manager._open_position(signal)` reads `signal.snapshot_id`.

This is a **backward-compatible** schema addition (existing consumers ignore the new field).

---

## 5. Hook 3: Reconciliation worker — ORDER_FILLED update

After `reconcile_history()` upserts a trade from Lighter, the worker can
also update the linked snapshot:

```python
# In lighter_reconciliation_worker.reconcile_history() inner loop:
# (after upsert_trade(mirror) succeeds)
snap = signal_snapshot_repo.get_by_order_id(order.order_id)
if snap and snap.link_status == LinkStatus.ORDER_PLACED:
    signal_snapshot_repo.update_linkage(
        snapshot_id=snap.snapshot_id,
        link_status=LinkStatus.ORDER_FILLED,
    )
```

This closes the lifecycle: PENDING → ORDER_PLACED → ORDER_FILLED.

---

## 6. Orphan detection (daily batch)

```python
# Run daily, e.g. as a scheduled task or startup check:
now_ms = int(time.time() * 1000)
threshold_ms = now_ms - 10 * 60 * 1000  # 10-minute timeout

# Get all known trade_ids from trades_lighter
known_ids = set(row[0] for row in conn.execute(
    "SELECT trade_id FROM trades_lighter"
).fetchall())

orphan_count = signal_snapshot_repo.mark_orphaned(
    older_than_ms=threshold_ms,
    trades_lighter_ids=known_ids,
)
logger.info(f"Orphan detection: {orphan_count} snapshots marked ORPHANED")
```

Orphan rate is a signal-quality metric: high orphan rate → order placement
pipeline has issues (rejected orders, callback misses).

---

## 7. Flow diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ signal_service.get_signal()                                                 │
│                                                                             │
│  1. Load OHLCV → df (candle_open_ts = df.iloc[-1].name)                    │
│  2. Compute L1/L2/L3/L4                                                     │
│  3. Build SignalResponse                                                    │
│  4. ✨ INSERT signal_snapshots (link_status=PENDING)                        │
│  5. Attach snapshot_id to SignalResponse                                    │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ SignalResponse (with snapshot_id)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ position_manager._open_position()                                           │
│                                                                             │
│  1. await gateway.create_market_order()                                     │
│  2. trade_id = market_result.order_id                                       │
│  3. ✨ UPDATE signal_snapshots SET link_status=ORDER_PLACED,                │
│         lighter_order_id=trade_id                                           │
│  4. repo.insert_trade(...)  ← candle_open_ts removed from here             │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ (async, periodic)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LighterReconciliationWorker.reconcile_history()                             │
│                                                                             │
│  1. fetch accountInactiveOrders                                             │
│  2. upsert_trade → trades_lighter (CLOSED)                                  │
│  3. ✨ UPDATE signal_snapshots SET link_status=ORDER_FILLED                 │
│         WHERE lighter_order_id = order.order_id                             │
└─────────────────────────────────────────────────────────────────────────────┘
                     │ (daily batch)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Orphan detection                                                            │
│  UPDATE signal_snapshots SET link_status=ORPHANED                          │
│  WHERE link_status=ORDER_PLACED AND ts_order_placed_ms < threshold          │
│    AND lighter_order_id NOT IN (SELECT trade_id FROM trades_lighter)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Files to change when implementing (production branch only)

| File | Change |
|------|--------|
| `backend/app/schemas/signal.py` | Add `snapshot_id: Optional[str] = None` to `SignalResponse` |
| `backend/app/use_cases/signal_service.py` | Insert snapshot at signal generation; expose MLP class probs |
| `backend/app/use_cases/position_manager.py` | Call `update_linkage` after order; remove `candle_open_ts=time.time()` |
| `backend/app/use_cases/ai_service.py` | Expose per-class probabilities from `get_confidence()` |
| `backend/app/use_cases/ema_service.py` | Expose numeric EMA vote as float |
| `backend/app/infrastructure/database/` | Add `snapshot_repo` construction (inject into signal_service / position_manager) |

**DO NOT edit any of the above in this proposal.** Changes tracked here, applied in
`refactor/reconciliation-pipeline` git branch by the lead analyst.
