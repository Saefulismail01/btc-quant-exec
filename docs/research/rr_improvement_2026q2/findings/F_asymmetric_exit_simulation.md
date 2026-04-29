# Asymmetric exit — feasibility & simulation

**Area:** F — Asymmetric Exit Feasibility  
**Status:** F.1 Complete (kode); F.2 Blocked  
**Updated:** 2026-04-24

## TL;DR

Gateway Lighter mendukung **reduce-only** SL/TP penuh posisi; **tidak** ada path terintegrasi untuk **partial close** atau **trailing order** native di `lighter_execution_gateway.py`. Simulasi counterfactual **F.2** membutuhkan OHLCV intraday selama posisi terbuka + mapping fill→episode — **belum** dijalankan (README: minimal 1m; DB inti 4H saja).

## Methodology

- Baca `close_position_market`, `place_sl_order`, `place_tp_order` di `lighter_execution_gateway.py`.  
- README skenario A–C: **tidak** diimplementasikan sebagai skrip (blocked).

## Findings

### F.1 Engine capability

| Pertanyaan | Jawaban |
|------------|---------|
| Partial close via SDK? | **Tidak** terlihat di gateway: `close_position_market` mengirim **MARKET** dengan **size = full** posisi (`position.quantity`) — ```1088:1099:backend/app/adapters/gateways/lighter_execution_gateway.py``` |
| Trailing stop server-side? | **Tidak** diverifikasi sebagai fitur first-class; hanya SL/TP trigger statis (`create_sl_order` / `create_tp_order`). |
| Emulasi client-side | Memungkinkan secara arsitektur (polling posisi + amend/cancel), **tidak** ada modul terpusat di repo yang diinventaris; **risk gap** polling: di luar scope pengukuran latensi di sesi ini. |
| Trailing SL dengan PnL > 0 | Logika freeze SL di `position_manager` mengakui kasus **SL + profit** (uji `test_sl_freeze_logic.py`) — menunjukkan trailing/widen SL bisa terjadi di lapangan tanpa schema order terpisah. |

### F.2 Counterfactual simulation

**Blocked** — alasan:

1. Hanya **`btc_ohlcv_4h`** di DuckDB default; README mensyaratkan **1m** (atau tick) intraperiode.  
2. Episode sudah diekspor (`data/episodes_lighter_2026-04-24.csv`) tetapi **tanpa** high-low path per menit, sim trailing / chandelier **bias besar**.  
3. **Tidak** menjalankan bot atau mengubah kode produksi.

**Skenario yang direncanakan README (baseline / A / B / C):** tabel komparasi **TIDAK TERSEDIA** numerik.

## Gaps & Limitations

- Butuh dataset **1m** (atau lebih halus) overlapping rentang setiap `[t_open, t_close]` episode + aturan partial fill yang konsisten dengan exchange.

## Raw Sources

- `backend/app/adapters/gateways/lighter_execution_gateway.py` (market close, SL/TP)  
- `backend/tests/test_sl_freeze_logic.py` (trailing SL scenario)  
- `docs/research/rr_improvement_2026q2/data/episodes_lighter_2026-04-24.csv`
