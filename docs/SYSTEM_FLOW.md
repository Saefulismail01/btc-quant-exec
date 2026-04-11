# BTC-Scalping System Flow Diagram

## Overview

```mermaid
flowchart TD
    A[Data Ingestion Daemon<br/>60s interval] --> B[Fetch OHLCV from Binance]
    B --> C[Generate Signal]
    C --> D{Paper Trade}
    D --> E[Paper Trade Service]
    D --> F{Live Trade}
    F --> G[PositionManager Sync]
    G --> H[Process Signal<br/>Execute Trade]
    H --> I[Telegram Notification]
    
    style A fill:#1a1a2e,stroke:#4ecca3,color:#fff
    style G fill:#16213e,stroke:#e94560,color:#fff
    style H fill:#16213e,stroke:#e94560,color:#fff
```

## Detailed Ingestion Cycle

```mermaid
flowchart TD
    subgraph INGESTION["Data Ingestion Use Case"]
        A[Cycle Start] --> B[Fetch OHLCV 500 candles]
        B --> C[Fetch FGI, Funding, Long/Short Ratio]
        C --> D[Generate Signal with BCD]
        D --> E[Signal Cache]
    end
    
    subgraph PAPER["Paper Trade"]
        E --> G[PaperTradeService.process_signal]
        G --> H[Check Signal vs Paper Position]
    end
    
    subgraph LIVE["Live Execution"]
        E --> J[PositionManager]
        J --> K[sync_position_status]
        K --> L{Position Exists?}
        L -->|Yes| M[Manage Existing]
        L -->|No| N[process_signal]
        N --> O{Valid Signal?}
        O -->|BUY/SELL| P[Open Position]
        O -->|NEUTRAL| Q[Skip]
    end
    
    style INGESTION fill:#1a1a2e,stroke:#4ecca3,color:#fff
    style LIVE fill:#16213e,stroke:#e94560,color:#fff
```

## PositionManager Sync Flow

```mermaid
flowchart TD
    START[sync_position_status] --> A[Get OPEN trade from DB]
    A --> B{Trade exists?}
    B -->|No| C[Return False]
    B -->|Yes| D[Get position from Exchange]
    
    D --> E{call get_open_position}
    E -->|Has Position| F[Position Still Open]
    F --> G[Sync SL/TP prices]
    G --> H[Return False]
    
    E -->|None| I[Retry after 3s]
    I --> J[Call get_open_position again]
    J --> K{Still None?}
    K -->|Yes| L[Position CLOSED at Exchange]
    
    L --> M[Fetch last closed order]
    M --> N{call fetch_last_closed_order}
    N -->|Found| O[Get exit price]
    N -->|Not Found| P[Fallback Heuristic]
    
    O --> Q[Calculate PnL]
    P --> R[Use distance to SL/TP]
    R --> S[Calculate PnL]
    Q --> T[Update DB]
    S --> T
    T --> U[update_trade_on_close]
    U --> V[Mark status=CLOSED]
    V --> W[Risk Manager Record]
    W --> X[Telegram Close Notification]
    
    X --> Y[Return True]
    
    style L fill:#ff6b6b,stroke:#e94560,color:#fff
    style M fill:#ffd93d,stroke:#6c5ce7,color:#000
    style U fill:#6c5ce7,stroke:#fff,color:#fff
```

## BUG LOCATION - Root Cause

### Masalah:
`fetch_last_closed_order()` mengembalikan **FIRST** order dari list tanpa filtering - bisa dapat order dari trade sebelumnya!

```mermaid
flowchart TD
    subgraph BUG["🔴 BUG: fetch_last_closed_order()"]
        A[Position closed at Exchange<br/>get_open_position() = None] --> B[Fetch last closed order]
        
        B --> C["fetch_last_closed_order()"]
        C --> D[GET /accountInactiveOrders<br/>limit=10]
        D --> E[Get list of closed orders<br/>[OrderTradeB, OrderTradeA, ...]]
        E --> F[Loop through orders]
        F --> G[Skip canceled orders]
        G --> H[Calculate filled_price]
        H --> I{Order valid?}
        I -->|No| J[Continue to next order]
        I -->|Yes| K[Return FIRST order found]
        
        K --> L[🔴 PROBLEM: Returns FIRST order]
        L --> M[OrderTradeA - bukan<br/>OrderTradeB yang lagi di-sync!]
        
        M --> N[Update DB with wrong exit price]
        N --> O[❌ DB still shows OPEN<br/>OR wrong trade updated]
    end
    
    style A fill:#ff6b6b,stroke:#e94560,color:#fff
    style L fill:#ffd93d,stroke:#6c5ce7,color:#000
    style O fill:#e94560,stroke:#fff,color:#fff
```

### Timeline Race Condition:

```mermaid
sequenceDiagram
    participant Cycle as Cycle
    participant DB as Database
    participant Lighter as Lighter API

    alt Timeline yang menyebabkan bug:
        Note over Cycle,DB: 08:00 UTC - Trade A
        Cycle->>Lighter: Open Trade A ($71,747)
        Lighter->>DB: Record Trade A
        Note over DB: Trade A: OPEN

        Cycle->>Lighter: TP Hit ($72,261)
        Lighter->>DB: Trade A closed ✓

        Note over Cycle,DB: 08:00 UTC - Trade B
        Cycle->>Lighter: Open Trade B ($72,088)
        Lighter->>DB: Record Trade B
        Note over DB: Trade B: OPEN

        Note over Cycle,DB: 08:05 UTC - Sync Trade B
        Cycle->>Lighter: get_open_position()
        Lighter->>Cycle: None ❌ (tidak ada posisi)
        
        Cycle->>Lighter: fetch_last_closed_order()
        Lighter->>Cycle: Order A ($72,261)  ← 🔴 MASALAH!<br/>Returns first order dari list
        Note over Cycle: Salah trade!
        
        Cycle->>DB: update_trade_on_close(TradeB)
        Note over DB: ❌ Trade B di-update dengan<br/>exit price dari Trade A
        Note over DB: Trade B status: OPEN (gagal)
    end
```

## FIXED FLOW - With Entry Price Filtering

### Solution: Filter dengan expected_entry_price

```mermaid
flowchart TD
    START[sync_position_status] --> A[Get trade from DB<br/>entry_price: $72,088]
    
    A --> B[get_open_position]
    B --> C{Position?}
    C -->|Exists| D[Sync SL/TP from exchange]
    C -->|None| E[Position CLOSED at Exchange]
    
    E --> F[fetch_last_closed_order<br/>expected_entry_price: $72,088<br/>tolerance: 2%]
    
    F --> G[GET /accountInactiveOrders<br/>limit: 10]
    G --> H[Loop through ALL orders]
    
    H --> I{Order canceled?}
    I -->|Yes| J[Continue]
    I -->|No| K[Calculate filled_price]
    
    K --> L[Check: Does exit price<br/>match entry ± 2%?]
    L -->|Match| M[✅ Found correct order!]
    L -->|No Match| N[Continue to next order]
    N --> O{More orders?}
    O -->|Yes| H
    O -->|No| P[Fallback: Use SL/TP from DB]
    
    M --> Q[Update trade with<br/>correct exit price]
    P --> Q
    
    Q --> R[update_trade_on_close]
    R --> S[Status = CLOSED ✅]
    
    style C fill:#ff6b6b,stroke:#e94560,color:#fff
    style M fill:#4ecca3,stroke:#fff,color:#fff
    style Q fill:#6c5ce7,stroke:#fff,color:#fff
```

### Fixed Sequence Diagram:

```mermaid
sequenceDiagram
    participant Cycle as Cycle
    participant DB as Database
    participant Lighter as Lighter API

    Cycle->>DB: Get trade from DB<br/>(entry_price: $72,088)
    DB->>Cycle: Trade B info

    Cycle->>Lighter: get_open_position()
    Lighter->>Cycle: None ❌

    Cycle->>Lighter: fetch_last_closed_order(<br/>expected_entry=$72,088)
    Lighter->>Cycle: All closed orders
    Note over Cycle: Filter by entry price<br/>$72,088 ± 2%

    Cycle->>Lighter: Find order with<br/>matching entry price
    Lighter->>Cycle: Order B ($72,261)<br/>✅ Correct!

    Cycle->>DB: update_trade_on_close(<br/>Trade B, exit=$72,261)
    Note over DB: Trade B: CLOSED ✅
```

## Files Involved

| File | Responsibility |
|------|-----------------|
| `data_ingestion_use_case.py` | Main daemon loop |
| `position_manager.py` | Sync + Execute |
| `lighter_execution_gateway.py` | Lighter API calls |
| `live_trade_repository.py` | DB read/write |

## Summary - Root Cause & Fix

### Root Cause:
`fetch_last_closed_order()` mengembalikan **FIRST** closed order dari list tanpa filtering by entry price. Ketika multiple trades ada di list, fungsi ini bisa return order dari trade sebelumnya - bukan yang sedang di-sync!

### Why This Happens:
1. API `/accountInactiveOrders` mengembalikan list 10 orders terbaru
2. Fungsi loop dan ambil **pertama** yang valid (tidak canceled)
3. Tidak ada filter "Apakah ini order untuk trade yang lagi di-sync?"
4. Result: bisa dapat order dari trade sebelumnya

### Fix yang Diperlukan:

**File:** `lighter_execution_gateway.py`
```python
async def fetch_last_closed_order(
    self,
    expected_entry_price: Optional[float] = None,  # ← TAMBAHKAN
    tolerance_pct: float = 2.0,
) -> Optional[Dict[str, Any]]:
```

**Logic:**
```python
# Loop through ALL orders
for order in closed_orders:
    filled_price = calculate_price(order)
    
    # Filter by entry price
    if expected_entry_price:
        diff_pct = abs(filled_price - expected_entry_price) / expected_entry_price * 100
        if diff_pct <= tolerance_pct:
            return order  # ✅ Found correct!
    else:
        return order  # Backward compatible
```

**Caller:** `position_manager.py`
```python
last_order = await self.gateway.fetch_last_closed_order(
    expected_entry_price=db_trade.entry_price
)
```

### Files Involved:

| File | Change |
|------|--------|
| `lighter_execution_gateway.py` | Add `expected_entry_price` param + filtering logic |
| `position_manager.py` | Pass `db_trade.entry_price` to caller |

### Benefits:
- ✅ Can get accurate exit price dari exchange
- ✅ Filter order yang benar sesuai trade
- ✅ Fallback to DB only if no match
- ✅ Backward compatible (param optional)