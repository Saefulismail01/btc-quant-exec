# Lighter Exchange Gateway — Build From Scratch

> **Audience:** AI agents atau developer yang ingin membangun Lighter execution gateway dari nol.
> Dokumentasi ini ditulis berdasarkan implementasi nyata di `backend/app/adapters/gateways/lighter_execution_gateway.py`.

---

## Daftar Isi

1. [Overview & Arsitektur](#1-overview--arsitektur)
2. [Dependencies](#2-dependencies)
3. [Credentials & Environment Variables](#3-credentials--environment-variables)
4. [Autentikasi (Auth Token)](#4-autentikasi-auth-token)
5. [Nonce Management — KRITIS](#5-nonce-management--kritis)
6. [Integer Scaling untuk Price & Size](#6-integer-scaling-untuk-price--size)
7. [API Endpoints yang Digunakan](#7-api-endpoints-yang-digunakan)
8. [Inisialisasi Gateway](#8-inisialisasi-gateway)
9. [Market Order](#9-market-order)
10. [Stop-Loss & Take-Profit Orders](#10-stop-loss--take-profit-orders)
11. [Menutup Posisi](#11-menutup-posisi)
12. [Query Akun & Posisi](#12-query-akun--posisi)
13. [Fetch Fills & Order History](#13-fetch-fills--order-history)
14. [PnL Calculation](#14-pnl-calculation)
15. [Error Handling & Retry](#15-error-handling--retry)
16. [Trade Persistence (DuckDB)](#16-trade-persistence-duckdb)
17. [Full Trade Flow Example](#17-full-trade-flow-example)
18. [Checklist Build Gateway Baru](#18-checklist-build-gateway-baru)

---

## 1. Overview & Arsitektur

Lighter adalah perpetual DEX berbasis ZK di Ethereum L2. Gateway ini bertindak sebagai adapter antara trading bot dengan Lighter API menggunakan official Python SDK.

```
Trading Bot
    │
    ▼
LighterExecutionGateway          ← file utama
    ├── LighterNonceManager      ← sequential nonce persistence
    ├── lighter_math.py          ← integer scaling
    └── lighter SDK              ← SignerClient (signing + submission)
```

**Pola desain:** Clean Architecture — gateway hanya implementasi dari `BaseExchangeExecutionGateway` interface. Bot tidak tahu Lighter secara langsung; semua lewat interface ini.

---

## 2. Dependencies

```txt
# requirements.txt
lighter-sdk>=1.0.0       # SDK resmi Lighter
aiohttp>=3.9.0           # Async HTTP client
python-dotenv>=1.0.0     # Load .env
duckdb>=0.10.0           # Trade persistence
pydantic>=2.6.0          # Config validation
eth_account>=0.11.0      # Ethereum key handling (dipakai SDK)
```

Install:
```bash
pip install lighter-sdk aiohttp python-dotenv duckdb pydantic eth_account
```

Import SDK:
```python
import lighter  # package name: lighter-sdk
```

---

## 3. Credentials & Environment Variables

Buat file `.env` di root project:

```env
# === MODE ===
LIGHTER_EXECUTION_MODE=testnet         # "testnet" atau "mainnet"
LIGHTER_TRADING_ENABLED=false          # WAJIB false saat testing; true untuk live trading

# === TESTNET ===
LIGHTER_TESTNET_API_KEY=0xYourPublicKey
LIGHTER_TESTNET_API_SECRET=0xYourPrivateKey
LIGHTER_TESTNET_BASE_URL=https://mainnet.zklighter.elliot.ai/api/v1
LIGHTER_TESTNET_WS_URL=wss://mainnet.zklighter.elliot.ai/stream

# === MAINNET ===
LIGHTER_MAINNET_API_KEY=0xYourMainnetPublicKey
LIGHTER_MAINNET_API_SECRET=0xYourMainnetPrivateKey

# === INDEX ===
LIGHTER_API_KEY_INDEX=2                # Mulai dari index 2; index 0-1 reserved
LIGHTER_ACCOUNT_INDEX=3                # Account index di Lighter (cek di UI)
```

---

## 3.1 Cara Mendapatkan API Key, Secret Key, dan Account Index

> **PENTING:** Bagian ini menjelaskan langkah-langkah untuk mendapatkan credentials yang diperlukan agar gateway bisa terhubung ke Lighter.

### Perbedaan API Key Index vs Account Index

| Parameter | Sumber | Penjelasan |
|-----------|--------|------------|
| **API Key Index** | Dari create API Key di dashboard | Index dari API key yang dibuat (0-254, tapi 0-3 reserved) |
| **Account Index** | Dari wallet yang di-connect | Index account di Lighter (biasanya 0 untuk main account) |

**Analoginya:**
- `Account Index` = Nomor rekening bank (1 akun = banyak kartu/API key)
- `API Key Index` = Nomor kartu ATM (bisa banyak per rekening)

---

### Langkah 1: Connect Wallet & Dapatkan Account Index

1. Buka browser dan akses: **https://app.lighter.xyz**
2. Connect wallet kamu (MetaMask, Rabby, atau wallet lain yang support zkSync Era)
3. Pastikan wallet sudah terhubung ke network **zkSync Era** (mainnet) atau **zkSync Era Testnet**

**Cara dapat Account Index (dari wallet address):**

Gunakan API `accountsByL1Address` untuk konversi wallet address ke account index:

```bash
# GET /accountsByL1Address?l1_address=0xYourWalletAddress
curl "https://mainnet.zklighter.elliot.ai/api/v1/accountsByL1Address?l1_address=0xYourWalletAddress"
```

Response:
```json
{
  "sub_accounts": [
    {"account_index": 0, "public_key": "0x..."},
    {"account_index": 1, "public_key": "0x..."}
  ]
}
```

**Account Index ada di response `sub_accounts[0].account_index`** — ini adalah index akun utama kamu (biasanya 0).

> ⚠️ **PENTING:** Awalnya account index berupa hash/address, tapi Lighter mengkonversi ke angka untuk identifikasi internal. Gunakan endpoint di atas untuk dapat angka indexnya.
>
> **Sumber:** [Lighter API Docs - Account Index](https://apidocs.lighter.xyz/docs/account-index)

### Langkah 2: Buat API Key Baru

1. Di dashboard Lighter, navigasi ke **Settings** → **API Keys** (atau langsung akses https://app.lighter.xyz/apikeys)
2. Klik tombol **"Create New API Key"** atau **"+"**
3. Beri nama key tersebut (misalnya: "trading-bot-key")
4. **SIMPAN** Private Key yang ditampilkan — ini hanya muncul SEKALI, tidak bisa diambil lagi
5. Catat **API Key Index** yang otomatis di-assign (biasanya mulai dari 4 ke atas, karena 0-3 reserved untuk frontend)

```
Contoh output setelah create API key:
- API Key Index: 4          ← Ini LIGHTER_API_KEY_INDEX
- Public Key: 0xYourPublicKey...
- Private Key: 0xYourPrivateKey...  ← SIMPAN SEGERA, TIDAK BISA DIULANG!
```

### Contoh Lengkap Konfigurasi

Setelah mendapat semua credentials:

```env
# Mode
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false

# Credentials dari Langkah 2 (Create API Key)
LIGHTER_TESTNET_API_KEY=0xYourPublicKey
LIGHTER_TESTNET_API_SECRET=0xYourPrivateKey

# Index dari Langkah 1 & 2
LIGHTER_API_KEY_INDEX=4        # Dari create API key (bukan 0-3)
LIGHTER_ACCOUNT_INDEX=0        # Dari wallet yang connect (biasanya 0)
```

### Catatan Penting

| Item | Batasan |
|------|---------|
| Account Index | Assign per wallet yang connect, 0 untuk main account |
| API Key Index | 0-254, tapi 0-3 reserved untuk frontend |
| Private Key | Hanya ditampilkan SEKALI saat creation — JANGAN kehilangan! |
| Multiple Keys | Bisa buat banyak API key per account |
- Sub-account: index 2, 3, 4, dst
```

### Langkah 4: Konfigurasi Environment Variables

Setelah punya semua credentials, update file `.env`:

```env
# === MODE ===
LIGHTER_EXECUTION_MODE=testnet         # "testnet" atau "mainnet"
LIGHTER_TRADING_ENABLED=false

# === Credentials yang sudah didapat dari langkah di atas ===
LIGHTER_TESTNET_API_KEY=0xYourPublicKey      # Dari step create API key
LIGHTER_TESTNET_API_SECRET=0xYourPrivateKey   # Dari step create API key (JANGAN BAGI ORANG!)

# === Index yang sudah didapat dari langkah di atas ===
LIGHTER_API_KEY_INDEX=4                # Sesuai index dari API key yang di-create
LIGHTER_ACCOUNT_INDEX=0                # Sesuai index account di dashboard
```

### Catatan Penting

| Item | Batasan |
|------|---------|
| API Key Index | 0-254, tapi 0-3 reserved untuk frontend |
| Private Key | Hanya ditampilkan SEKALI saat creation — JANGAN kehilangan! |
| Multiple Keys | Bisa buat banyak key per account untuk different purposes |
| Revoke | Bisa revoke key lama di dashboard jika suspect compromized |

### Alternative: Buat via SDK (Programmatic)

Jika prefer buat API key lewat kode:

```python
import lighter

# Setup signer dengan L1 private key (wallet yang sudah connect ke Lighter)
signer = lighter.SignerClient(
    url="https://mainnet.zklighter.elliot.ai",  # atau testnet URL
    account_index=0,  # main account
    l1_private_key="0xYourL1PrivateKey"  # wallet private key
)

# Generate API key baru
new_key = signer.create_api_key(
    key_name="trading-bot-key",
    api_key_index=4  # pilihan index (pastikan tidak conflict)
)

print(f"Public Key: {new_key['public_key']}")
print(f"Private Key: {new_key['private_key']}")  # SIMPAN!
```

---

> **Catatan penting:**
> - "Testnet" di Lighter sebenarnya menggunakan endpoint mainnet juga — bedanya hanya di account & key yang dipakai.
> - `LIGHTER_API_KEY_INDEX=2` (bukan 0 atau 1, yang reserved untuk internal).
> - `LIGHTER_TRADING_ENABLED` adalah safety switch. Selama `false`, semua order call langsung return error tanpa menyentuh exchange.

Load credentials di Python:
```python
from dotenv import load_dotenv
import os

load_dotenv()

execution_mode = os.getenv("LIGHTER_EXECUTION_MODE", "testnet")
trading_enabled = os.getenv("LIGHTER_TRADING_ENABLED", "false").lower() == "true"
api_key_index = int(os.getenv("LIGHTER_API_KEY_INDEX", "2"))
account_index = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "3"))

if execution_mode == "mainnet":
    api_key = os.getenv("LIGHTER_MAINNET_API_KEY")
    api_secret = os.getenv("LIGHTER_MAINNET_API_SECRET")
    base_url = "https://mainnet.zklighter.elliot.ai/api/v1"
else:
    api_key = os.getenv("LIGHTER_TESTNET_API_KEY")
    api_secret = os.getenv("LIGHTER_TESTNET_API_SECRET")
    base_url = os.getenv("LIGHTER_TESTNET_BASE_URL", "https://mainnet.zklighter.elliot.ai/api/v1")
```

---

## 4. Autentikasi (Auth Token)

Lighter menggunakan token berbasis waktu (10 menit expiry) untuk authenticated endpoints.

### Generate Auth Token

```python
import lighter

def _get_signer_client(api_secret: str, account_index: int, api_key_index: int, base_url: str):
    return lighter.SignerClient(
        url=base_url.replace("/api/v1", ""),  # SDK butuh base URL tanpa path
        account_index=account_index,
        api_private_keys={api_key_index: api_secret}
    )

def generate_auth_token(client: lighter.SignerClient, api_key_index: int) -> str:
    token_result = client.create_auth_token_with_expiry(
        deadline=lighter.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY,
        api_key_index=api_key_index,
    )
    return token_result[0]  # Format: "expiry_unix:account_index:api_key_index:random_hex"
```

### Pakai Token di HTTP Request

```python
import aiohttp

async def make_authenticated_request(session, method, endpoint, base_url, auth_token, params=None, json=None):
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    url = f"{base_url}{endpoint}"
    async with session.request(method, url, headers=headers, params=params, json=json, ssl=False) as resp:
        resp.raise_for_status()
        return await resp.json()
```

> Token expired? Generate baru. Implementasikan token caching dengan TTL 9 menit (1 menit buffer sebelum 10 menit expiry).

---

## 5. Nonce Management — KRITIS

Lighter menggunakan nonce sequential wajib untuk setiap transaksi. Jika nonce salah → transaksi ditolak.

### Konsep Nonce

- Setiap account punya counter nonce di chain
- Setiap order baru harus pakai nonce = nonce_sebelumnya + 1
- Nonce tidak bisa diulang atau skip

### Implementasi Nonce Manager

```python
import json
import asyncio
import os
from pathlib import Path

class LighterNonceManager:
    STATE_FILE = "infrastructure/lighter_nonce_state.json"

    def __init__(self, api_key_index: int):
        self.api_key_index = api_key_index
        self._lock = asyncio.Lock()
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if Path(self.STATE_FILE).exists():
            with open(self.STATE_FILE) as f:
                return json.load(f)
        return {"api_key_index": self.api_key_index, "next_nonce": 1}

    def _save_state(self):
        with open(self.STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)

    async def get_next_nonce(self) -> int:
        async with self._lock:
            return self._state["next_nonce"]

    async def mark_used(self, nonce: int):
        """Panggil SETELAH order berhasil di-submit."""
        async with self._lock:
            self._state["next_nonce"] = nonce + 1
            self._save_state()

    async def resync_from_server(self, server_nonce: int):
        """Panggil saat dapat error nonce mismatch dari server."""
        async with self._lock:
            self._state["next_nonce"] = server_nonce
            self._save_state()
```

### Sync Nonce dari Server

```python
async def fetch_server_nonce(session, base_url: str, account_index: int, api_key_index: int) -> int:
    """GET /nextNonce — tidak butuh auth token."""
    async with session.get(
        f"{base_url}/nextNonce",
        params={"account_index": str(account_index), "api_key_index": str(api_key_index)},
        ssl=False
    ) as resp:
        data = await resp.json()
        return int(data["nonce"])
```

### Usage Pattern

```python
nonce = await nonce_manager.get_next_nonce()
try:
    # submit order dengan nonce ini
    result = await submit_order(..., nonce=nonce)
    await nonce_manager.mark_used(nonce)  # hanya jika berhasil
except NonceError as e:
    server_nonce = extract_server_nonce_from_error(e)
    await nonce_manager.resync_from_server(server_nonce)
    # retry dengan nonce baru
```

---

## 6. Integer Scaling untuk Price & Size

Lighter mewajibkan semua price dan size dalam bentuk **integer** (bukan float). Ini untuk keperluan ZK proof.

### Market Decimals untuk BTC/USDC

```python
MARKET_ID = 1               # BTC/USDC perpetual
DEFAULT_PRICE_DECIMALS = 1  # Harga di-scale 10x
DEFAULT_SIZE_DECIMALS = 5   # Size di-scale 100,000x
```

### Fungsi Scaling

```python
def scale_price(price_float: float, decimals: int) -> int:
    """Float → integer untuk dikirim ke Lighter."""
    return int(round(price_float * (10 ** decimals)))

def unscale_price(price_int: int, decimals: int) -> float:
    """Integer dari Lighter → float yang bisa dibaca manusia."""
    return price_int / (10 ** decimals)

def scale_size(size_float: float, decimals: int) -> int:
    """Float BTC → integer untuk dikirim ke Lighter."""
    return int(round(size_float * (10 ** decimals)))

def unscale_size(size_int: int, decimals: int) -> float:
    """Integer dari Lighter → float BTC."""
    return size_int / (10 ** decimals)

def calculate_btc_quantity(size_usdt: float, leverage: int, price: float, size_decimals: int) -> tuple[float, int]:
    """
    Hitung jumlah BTC dari margin USDT.
    Returns: (quantity_float, quantity_scaled_int)
    """
    notional = size_usdt * leverage          # e.g. 1000 USDT * 15x = 15,000
    quantity_float = notional / price        # e.g. 15,000 / 45,000 = 0.333 BTC
    quantity_scaled = scale_size(quantity_float, size_decimals)
    return quantity_float, quantity_scaled
```

### Contoh Lengkap

```python
# BTC harga $45,000, mau beli 1000 USDT dengan leverage 15x
price = 45000.0
quantity_float, quantity_scaled = calculate_btc_quantity(1000.0, 15, price, DEFAULT_SIZE_DECIMALS)
# quantity_float = 0.3333...
# quantity_scaled = 33333 (dikirim ke Lighter)

price_scaled = scale_price(price, DEFAULT_PRICE_DECIMALS)
# price_scaled = 450000
```

### Fetch Market Decimals Dinamis

Selalu refresh dari API (bukan hardcode), karena bisa berubah:

```python
async def sync_market_metadata(session, base_url: str) -> tuple[int, int]:
    """
    Fetch price_decimals dan size_decimals dari /orderBooks.
    Cache hasil ini, refresh setiap 24 jam.
    """
    async with session.get(f"{base_url}/orderBooks", ssl=False) as resp:
        data = await resp.json()

    btc_market = next(
        (m for m in data["order_books"] if m["symbol"] == "BTC"),
        None
    )
    if not btc_market:
        raise ValueError("BTC market not found in orderBooks")

    price_decimals = int(btc_market["supported_price_decimals"])
    size_decimals = int(btc_market["supported_size_decimals"])
    return price_decimals, size_decimals
```

---

## 7. API Endpoints yang Digunakan

Base URL: `https://mainnet.zklighter.elliot.ai/api/v1`

| Endpoint | Method | Auth | Kegunaan |
|---|---|---|---|
| `/orderBooks` | GET | Tidak | Fetch market metadata (decimals) |
| `/orderBookDetails` | GET | Tidak | Harga terkini, orderbook snapshot |
| `/account` | GET | Ya | Balance, posisi terbuka |
| `/accountOrders` | GET | Ya | Order terbuka |
| `/accountInactiveOrders` | GET | Ya | Order closed/filled |
| `/nextNonce` | GET | Tidak | Nonce resync dari server |

### Contoh Request

```python
# Harga terkini
async with session.get(
    f"{base_url}/orderBookDetails",
    params={"market_id": "1"},
    ssl=False
) as resp:
    data = await resp.json()
    current_price = float(data["last_trade_price"])

# Account info
data = await make_authenticated_request(
    session, "GET", "/account", base_url, auth_token,
    params={"by": "index", "value": str(account_index)}
)

# Open orders
data = await make_authenticated_request(
    session, "GET", "/accountOrders", base_url, auth_token,
    params={"account_index": str(account_index), "market_id": "1"}
)

# Closed orders (untuk detect SL/TP fill)
data = await make_authenticated_request(
    session, "GET", "/accountInactiveOrders", base_url, auth_token,
    params={"account_index": str(account_index), "market_id": "1", "limit": "10"}
)
```

---

## 8. Inisialisasi Gateway

```python
import asyncio
import aiohttp
import lighter

class LighterGateway:
    def __init__(self):
        # Load dari env
        self.execution_mode = os.getenv("LIGHTER_EXECUTION_MODE", "testnet")
        self.trading_enabled = os.getenv("LIGHTER_TRADING_ENABLED", "false").lower() == "true"
        self.api_key_index = int(os.getenv("LIGHTER_API_KEY_INDEX", "2"))
        self.account_index = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "3"))

        if self.execution_mode == "mainnet":
            self.api_secret = os.getenv("LIGHTER_MAINNET_API_SECRET")
            self.base_url = "https://mainnet.zklighter.elliot.ai/api/v1"
        else:
            self.api_secret = os.getenv("LIGHTER_TESTNET_API_SECRET")
            self.base_url = os.getenv("LIGHTER_TESTNET_BASE_URL")

        # State
        self._session: aiohttp.ClientSession | None = None
        self._signer_client: lighter.SignerClient | None = None
        self._auth_token: str | None = None
        self._token_expires_at: float = 0.0
        self._price_decimals = DEFAULT_PRICE_DECIMALS
        self._size_decimals = DEFAULT_SIZE_DECIMALS
        self._metadata_last_synced: float = 0.0

        # Nonce manager
        self.nonce_manager = LighterNonceManager(api_key_index=self.api_key_index)

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _get_signer_client(self) -> lighter.SignerClient:
        if self._signer_client is None:
            sdk_base_url = self.base_url.replace("/api/v1", "")
            self._signer_client = lighter.SignerClient(
                url=sdk_base_url,
                account_index=self.account_index,
                api_private_keys={self.api_key_index: self.api_secret}
            )
        return self._signer_client

    def _get_auth_token(self) -> str:
        import time
        # Re-generate jika akan expired dalam 60 detik
        if time.time() > self._token_expires_at - 60:
            client = self._get_signer_client()
            token_result = client.create_auth_token_with_expiry(
                deadline=lighter.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY,
                api_key_index=self.api_key_index,
            )
            self._auth_token = token_result[0]
            self._token_expires_at = time.time() + 600  # 10 menit
        return self._auth_token

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
```

---

## 9. Market Order

### Entry Market Order

```python
async def place_market_order(self, side: str, size_usdt: float, leverage: int):
    """
    side: "LONG" atau "SHORT"
    size_usdt: margin dalam USDT (bukan notional)
    leverage: multiplier, e.g. 15
    """
    # Safety check
    if not self.trading_enabled:
        raise RuntimeError("Trading disabled: set LIGHTER_TRADING_ENABLED=true")

    # Pastikan metadata fresh
    await self._maybe_sync_metadata()

    # Fetch harga terkini
    session = self._get_session()
    async with session.get(
        f"{self.base_url}/orderBookDetails",
        params={"market_id": "1"},
        ssl=False
    ) as resp:
        data = await resp.json()
        current_price = float(data["last_trade_price"])

    # Hitung quantity
    _, quantity_scaled = calculate_btc_quantity(size_usdt, leverage, current_price, self._size_decimals)

    # Price dengan slippage buffer 2%
    SLIPPAGE = 0.02
    if side == "LONG":
        execution_price = current_price * (1 + SLIPPAGE)  # BUY: harga lebih tinggi
        is_ask = False  # BUY order
    else:
        execution_price = current_price * (1 - SLIPPAGE)  # SELL: harga lebih rendah
        is_ask = True   # SELL order

    price_scaled = scale_price(execution_price, self._price_decimals)

    # Get nonce
    nonce = await self.nonce_manager.get_next_nonce()

    # Submit via SDK
    client = self._get_signer_client()
    created_order, resp, err = await client.create_market_order(
        market_index=MARKET_ID,         # 1 untuk BTC/USDC
        client_order_index=0,
        base_amount=quantity_scaled,
        avg_execution_price=price_scaled,
        is_ask=is_ask,
    )

    if err:
        raise RuntimeError(f"Market order failed: {err}")

    # Mark nonce sebagai used
    await self.nonce_manager.mark_used(nonce)

    order_id = str(created_order.tx_hash) if hasattr(created_order, "tx_hash") else str(created_order)
    return {
        "success": True,
        "order_id": order_id,
        "filled_price": current_price,
        "filled_quantity": unscale_size(quantity_scaled, self._size_decimals),
    }
```

---

## 10. Stop-Loss & Take-Profit Orders

```python
async def place_sl_order(self, side: str, trigger_price: float, quantity: float):
    """
    side: sisi POSISI yang mau di-protect ("LONG" atau "SHORT")
    trigger_price: harga trigger SL
    quantity: jumlah BTC (float)
    """
    # SL dari LONG position = SELL order; dari SHORT = BUY order
    is_ask = (side == "LONG")

    # SL slippage 0.5% — posisi bisa gap melewati trigger
    SLIPPAGE = 0.005
    if is_ask:
        exec_price = trigger_price * (1 - SLIPPAGE)   # SELL sedikit di bawah trigger
    else:
        exec_price = trigger_price * (1 + SLIPPAGE)   # BUY sedikit di atas trigger

    trigger_scaled = scale_price(trigger_price, self._price_decimals)
    exec_price_scaled = scale_price(exec_price, self._price_decimals)
    quantity_scaled = scale_size(quantity, self._size_decimals)

    nonce = await self.nonce_manager.get_next_nonce()

    client = self._get_signer_client()
    created_order, resp, err = await client.create_sl_order(
        market_index=MARKET_ID,
        client_order_index=0,
        base_amount=quantity_scaled,
        trigger_price=trigger_scaled,
        avg_execution_price=exec_price_scaled,
        is_ask=is_ask,
    )

    if err:
        raise RuntimeError(f"SL order failed: {err}")

    await self.nonce_manager.mark_used(nonce)

    order_id = str(created_order.tx_hash) if hasattr(created_order, "tx_hash") else str(created_order)
    return {"success": True, "order_id": order_id}


async def place_tp_order(self, side: str, trigger_price: float, quantity: float):
    """
    side: sisi POSISI ("LONG" atau "SHORT")
    trigger_price: harga trigger TP
    quantity: jumlah BTC (float)
    """
    # TP dari LONG = SELL; dari SHORT = BUY
    is_ask = (side == "LONG")

    # TP slippage 0.3% — lebih ketat, arah menguntungkan
    SLIPPAGE = 0.003
    if is_ask:
        exec_price = trigger_price * (1 - SLIPPAGE)
    else:
        exec_price = trigger_price * (1 + SLIPPAGE)

    trigger_scaled = scale_price(trigger_price, self._price_decimals)
    exec_price_scaled = scale_price(exec_price, self._price_decimals)
    quantity_scaled = scale_size(quantity, self._size_decimals)

    nonce = await self.nonce_manager.get_next_nonce()

    client = self._get_signer_client()
    created_order, resp, err = await client.create_tp_order(
        market_index=MARKET_ID,
        client_order_index=0,
        base_amount=quantity_scaled,
        trigger_price=trigger_scaled,
        avg_execution_price=exec_price_scaled,
        is_ask=is_ask,
    )

    if err:
        raise RuntimeError(f"TP order failed: {err}")

    await self.nonce_manager.mark_used(nonce)

    order_id = str(created_order.tx_hash) if hasattr(created_order, "tx_hash") else str(created_order)
    return {"success": True, "order_id": order_id}
```

---

## 11. Menutup Posisi

```python
async def close_position_market(self):
    """Tutup seluruh posisi terbuka dengan market order."""
    position = await self.get_open_position()
    if not position:
        return {"success": False, "error": "No open position"}

    # Balik sisi untuk close
    close_side = "SHORT" if position["side"] == "LONG" else "LONG"

    result = await self.place_market_order(
        side=close_side,
        size_usdt=position["size_usdt"],
        leverage=position["leverage"]
    )
    return result
```

---

## 12. Query Akun & Posisi

```python
async def get_account_balance(self) -> float:
    """Ambil available balance dalam USDC."""
    auth_token = self._get_auth_token()
    data = await self._authenticated_get(
        "/account",
        params={"by": "index", "value": str(self.account_index)}
    )
    return float(data.get("available_balance", 0))


async def get_open_position(self) -> dict | None:
    """
    Ambil posisi terbuka.
    Returns None jika tidak ada posisi.
    """
    data = await self._authenticated_get(
        "/account",
        params={"by": "index", "value": str(self.account_index)}
    )

    positions = data.get("positions", [])
    btc_pos = next((p for p in positions if p.get("market_id") == MARKET_ID), None)

    if not btc_pos:
        return None

    quantity = unscale_size(int(btc_pos["base_amount"]), self._size_decimals)
    if quantity <= 0:
        return None

    entry_price = unscale_price(int(btc_pos["avg_price"]), self._price_decimals)
    current_price = await self.get_current_price()

    side = "LONG" if btc_pos["side"] == "BUY" else "SHORT"

    return {
        "symbol": "BTC/USDC",
        "side": side,
        "entry_price": entry_price,
        "quantity": quantity,
        "current_price": current_price,
        "unrealized_pnl": float(btc_pos.get("unrealized_pnl", 0)),
    }


async def get_current_price(self) -> float:
    """Harga BTC terkini dari last trade."""
    session = self._get_session()
    async with session.get(
        f"{self.base_url}/orderBookDetails",
        params={"market_id": str(MARKET_ID)},
        ssl=False
    ) as resp:
        data = await resp.json()
        return float(data["last_trade_price"])


async def get_active_sl_tp(self) -> dict:
    """
    Ambil harga SL dan TP dari open orders.
    Returns: {"sl_price": float|None, "tp_price": float|None}
    """
    data = await self._authenticated_get(
        "/accountOrders",
        params={"account_index": str(self.account_index), "market_id": str(MARKET_ID)}
    )

    sl_price = None
    tp_price = None

    for order in data.get("orders", []):
        order_type = order.get("order_type", "")
        trigger = unscale_price(int(order.get("trigger_price", 0)), self._price_decimals)
        if "STOP_LOSS" in order_type:
            sl_price = trigger
        elif "TAKE_PROFIT" in order_type:
            tp_price = trigger

    return {"sl_price": sl_price, "tp_price": tp_price}
```

---

## 13. Fetch Fills & Order History

```python
async def fetch_last_closed_order(self) -> dict | None:
    """
    Ambil order terakhir yang sudah closed/filled.
    Dipakai untuk detect exit price setelah SL/TP trigger.
    """
    data = await self._authenticated_get(
        "/accountInactiveOrders",
        params={
            "account_index": str(self.account_index),
            "market_id": str(MARKET_ID),
            "limit": "10"
        }
    )

    orders = data.get("orders", [])
    if not orders:
        return None

    last = orders[0]  # Paling baru pertama

    filled_base = unscale_size(int(last.get("filled_base_amount", 0)), self._size_decimals)
    filled_quote = float(last.get("filled_quote_amount", 0)) / 1e6  # USDC 6 decimals

    # Hitung fill price
    if filled_base > 0 and filled_quote > 0:
        filled_price = filled_quote / filled_base
    else:
        # SL/TP: pakai trigger price sebagai fallback
        filled_price = unscale_price(int(last.get("trigger_price", 0)), self._price_decimals)

    return {
        "order_id": last.get("tx_hash"),
        "filled_price": filled_price,
        "filled_quote": filled_quote,
        "filled_base": filled_base,
        "order_type": last.get("order_type"),
        "status": last.get("status"),
        "timestamp": int(last.get("created_at", 0)),
    }


async def fetch_entry_fill_quote(self, order_id: str) -> float:
    """
    Ambil USDC yang dibayar untuk entry order tertentu.
    Dipakai untuk kalkulasi PnL yang akurat.
    """
    data = await self._authenticated_get(
        "/accountInactiveOrders",
        params={
            "account_index": str(self.account_index),
            "market_id": str(MARKET_ID),
            "limit": "20"
        }
    )

    for order in data.get("orders", []):
        if str(order.get("tx_hash")) == str(order_id):
            return float(order.get("filled_quote_amount", 0)) / 1e6

    return 0.0
```

---

## 14. PnL Calculation

Urutan prioritas kalkulasi PnL (dari paling akurat ke fallback):

```python
def calculate_pnl(
    side: str,
    entry_filled_quote: float,   # USDC dibayar saat entry (dari Lighter fills)
    exit_filled_quote: float,    # USDC diterima saat exit (dari Lighter fills)
    entry_price: float,
    exit_price: float,
    quantity: float,
    size_usdt: float,
    leverage: int,
) -> tuple[float, float]:
    """Returns: (pnl_usdt, pnl_pct)"""

    # CASE 1: Keduanya market order → pakai actual USDC amounts
    if entry_filled_quote > 0 and exit_filled_quote > 0:
        if side == "LONG":
            pnl_usdt = exit_filled_quote - entry_filled_quote
        else:
            pnl_usdt = entry_filled_quote - exit_filled_quote

    # CASE 2: Entry market + exit SL/TP (exit_filled_quote bisa 0)
    elif entry_filled_quote > 0 and exit_price > 0:
        entry_base = entry_filled_quote / entry_price
        exit_filled_quote_computed = entry_base * exit_price
        if side == "LONG":
            pnl_usdt = exit_filled_quote_computed - entry_filled_quote
        else:
            pnl_usdt = entry_filled_quote - exit_filled_quote_computed

    # CASE 3: Fallback murni dari price difference
    else:
        if side == "LONG":
            pnl_usdt = (exit_price - entry_price) * quantity
        else:
            pnl_usdt = (entry_price - exit_price) * quantity

    pnl_pct = (pnl_usdt / size_usdt) * 100 if size_usdt > 0 else 0.0
    return pnl_usdt, pnl_pct
```

---

## 15. Error Handling & Retry

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3

async def retry_order_call(coro_factory, operation_name: str, nonce_manager: LighterNonceManager):
    """
    Retry dengan exponential backoff.
    Otomatis handle nonce mismatch.
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await coro_factory()
        except Exception as e:
            error_str = str(e).lower()

            # Nonce error → resync
            if "nonce" in error_str or "sequence" in error_str:
                logger.warning(f"Nonce error on {operation_name}: {e}")
                try:
                    server_nonce = extract_nonce_from_error(str(e))
                    await nonce_manager.resync_from_server(server_nonce)
                    logger.info(f"Resynced nonce to {server_nonce}")
                except Exception:
                    pass
                # Tidak retry nonce error secara otomatis — raise ke caller
                raise

            # Timeout / network error → retry
            if attempt < RETRY_ATTEMPTS - 1:
                wait = 1.0 * (2 ** attempt)  # 1s, 2s
                logger.warning(f"{operation_name} attempt {attempt+1} failed, retrying in {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                logger.error(f"{operation_name} failed after {RETRY_ATTEMPTS} attempts: {e}")
                raise


def extract_nonce_from_error(error_str: str) -> int:
    """
    Parse server nonce dari error message.
    Format biasanya: "expected nonce: 42, got: 41"
    Sesuaikan dengan format error aktual dari SDK.
    """
    import re
    match = re.search(r"expected[:\s]+(\d+)", error_str)
    if match:
        return int(match.group(1))
    raise ValueError(f"Cannot extract nonce from: {error_str}")
```

---

## 16. Trade Persistence (DuckDB)

```python
import duckdb
from datetime import datetime

class LiveTradeRepository:
    DB_PATH = "infrastructure/database/btc-quant.db"

    def __init__(self):
        self.conn = duckdb.connect(self.DB_PATH)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS live_trades (
                id                  VARCHAR PRIMARY KEY,
                timestamp_open      BIGINT NOT NULL,
                timestamp_close     BIGINT,
                symbol              VARCHAR NOT NULL,
                side                VARCHAR NOT NULL,
                entry_price         DOUBLE NOT NULL,
                exit_price          DOUBLE,
                size_usdt           DOUBLE NOT NULL,
                size_base           DOUBLE NOT NULL,
                leverage            INTEGER NOT NULL,
                sl_price            DOUBLE NOT NULL,
                tp_price            DOUBLE NOT NULL,
                sl_order_id         VARCHAR,
                tp_order_id         VARCHAR,
                exit_type           VARCHAR,
                status              VARCHAR NOT NULL DEFAULT 'OPEN',
                pnl_usdt            DOUBLE,
                pnl_pct             DOUBLE,
                signal_verdict      VARCHAR,
                signal_conviction   DOUBLE,
                candle_open_ts      BIGINT,
                entry_filled_quote  DOUBLE
            )
        """)

    def insert_trade(self, trade_id: str, **kwargs):
        """Insert trade baru saat entry."""
        import time
        self.conn.execute("""
            INSERT INTO live_trades (
                id, timestamp_open, symbol, side, entry_price,
                size_usdt, size_base, leverage,
                sl_price, tp_price, sl_order_id, tp_order_id,
                status, signal_verdict, signal_conviction,
                candle_open_ts, entry_filled_quote
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
        """, [
            trade_id,
            kwargs.get("timestamp_open", int(time.time() * 1000)),
            kwargs["symbol"], kwargs["side"], kwargs["entry_price"],
            kwargs["size_usdt"], kwargs["size_base"], kwargs["leverage"],
            kwargs["sl_price"], kwargs["tp_price"],
            kwargs.get("sl_order_id"), kwargs.get("tp_order_id"),
            kwargs.get("signal_verdict"), kwargs.get("signal_conviction"),
            kwargs.get("candle_open_ts"), kwargs.get("entry_filled_quote"),
        ])

    def update_trade_on_close(self, trade_id: str, exit_price: float, exit_type: str, pnl_usdt: float, pnl_pct: float):
        """Update trade saat posisi ditutup."""
        import time
        self.conn.execute("""
            UPDATE live_trades
            SET exit_price = ?, exit_type = ?, pnl_usdt = ?, pnl_pct = ?,
                timestamp_close = ?, status = 'CLOSED'
            WHERE id = ?
        """, [exit_price, exit_type, pnl_usdt, pnl_pct, int(time.time() * 1000), trade_id])
```

---

## 17. Full Trade Flow Example

```python
import asyncio

async def execute_trade_signal(signal: dict):
    """
    Contoh full flow: entry → SL/TP → monitoring exit.
    signal = {"side": "LONG", "conviction": 95.5, "verdict": "CONFLUENCE_5"}
    """
    gateway = LighterGateway()
    repo = LiveTradeRepository()

    try:
        # 1. Cek balance
        balance = await gateway.get_account_balance()
        print(f"Balance: ${balance:.2f} USDC")

        # 2. Entry market order
        SIZE_USDT = 1000.0
        LEVERAGE = 15

        entry = await gateway.place_market_order(
            side=signal["side"],
            size_usdt=SIZE_USDT,
            leverage=LEVERAGE
        )
        print(f"Entry: {entry['order_id']} @ ${entry['filled_price']:,.2f}")

        # 3. Hitung SL/TP dari entry price
        entry_price = entry["filled_price"]
        if signal["side"] == "LONG":
            sl_price = entry_price * 0.98    # -2%
            tp_price = entry_price * 1.015   # +1.5%
        else:
            sl_price = entry_price * 1.02    # +2%
            tp_price = entry_price * 0.985   # -1.5%

        # 4. Place SL
        sl = await gateway.place_sl_order(
            side=signal["side"],
            trigger_price=sl_price,
            quantity=entry["filled_quantity"]
        )

        # 5. Place TP
        tp = await gateway.place_tp_order(
            side=signal["side"],
            trigger_price=tp_price,
            quantity=entry["filled_quantity"]
        )

        # 6. Simpan ke DB
        repo.insert_trade(
            trade_id=entry["order_id"],
            symbol="BTC/USDC",
            side=signal["side"],
            entry_price=entry_price,
            size_usdt=SIZE_USDT,
            size_base=entry["filled_quantity"],
            leverage=LEVERAGE,
            sl_price=sl_price,
            tp_price=tp_price,
            sl_order_id=sl["order_id"],
            tp_order_id=tp["order_id"],
            signal_verdict=signal.get("verdict"),
            signal_conviction=signal.get("conviction"),
        )

        print(f"Trade opened | SL: ${sl_price:,.2f} | TP: ${tp_price:,.2f}")

        # 7. Monitor exit (polling loop)
        while True:
            await asyncio.sleep(30)  # Check setiap 30 detik

            position = await gateway.get_open_position()
            if position is None:
                # Posisi sudah ditutup (SL/TP triggered)
                last_order = await gateway.fetch_last_closed_order()
                exit_price = last_order["filled_price"] if last_order else entry_price
                exit_type = "TP" if exit_price >= tp_price else "SL"

                pnl_usdt, pnl_pct = calculate_pnl(
                    side=signal["side"],
                    entry_filled_quote=0,
                    exit_filled_quote=0,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=entry["filled_quantity"],
                    size_usdt=SIZE_USDT,
                    leverage=LEVERAGE,
                )

                repo.update_trade_on_close(
                    trade_id=entry["order_id"],
                    exit_price=exit_price,
                    exit_type=exit_type,
                    pnl_usdt=pnl_usdt,
                    pnl_pct=pnl_pct,
                )

                print(f"Trade closed | {exit_type} @ ${exit_price:,.2f} | PnL: ${pnl_usdt:+.2f} ({pnl_pct:+.1f}%)")
                break

    finally:
        await gateway.close()


# Run
asyncio.run(execute_trade_signal({"side": "LONG", "conviction": 95.5, "verdict": "CONFLUENCE_5"}))
```

---

## 18. Checklist Build Gateway Baru

Gunakan checklist ini untuk memastikan implementasi lengkap:

### Setup
- [ ] Install `lighter-sdk`, `aiohttp`, `python-dotenv`, `duckdb`
- [ ] Buat `.env` dengan semua credentials
- [ ] Set `LIGHTER_TRADING_ENABLED=false` saat development

### Core Components
- [ ] `LighterNonceManager` — load/save state ke JSON, lock async, resync method
- [ ] Integer scaling functions — `scale_price`, `scale_size`, `unscale_*`
- [ ] Auth token generation dengan TTL caching
- [ ] `aiohttp.ClientSession` dengan `ssl=False` dan timeout 20s
- [ ] `lighter.SignerClient` initialization

### API Methods
- [ ] `get_current_price()` — `/orderBookDetails`
- [ ] `get_account_balance()` — `/account`
- [ ] `get_open_position()` — `/account` → parse positions
- [ ] `sync_market_metadata()` — `/orderBooks` → price/size decimals

### Order Methods
- [ ] `place_market_order(side, size_usdt, leverage)` — dengan 2% slippage
- [ ] `place_sl_order(side, trigger_price, quantity)` — dengan 0.5% slippage
- [ ] `place_tp_order(side, trigger_price, quantity)` — dengan 0.3% slippage
- [ ] `close_position_market()` — reverse side market order

### Post-Trade
- [ ] `fetch_last_closed_order()` — `/accountInactiveOrders`
- [ ] `fetch_entry_fill_quote(order_id)` — untuk PnL akurat
- [ ] `calculate_pnl(...)` — 3 level priority: fills → computed → fallback
- [ ] `LiveTradeRepository` — DuckDB schema, insert, update

### Safety & Reliability
- [ ] Safety flag check di setiap order method
- [ ] Retry dengan exponential backoff (3x, 1s-2s)
- [ ] Nonce error detection + auto-resync
- [ ] Token expiry handling (regenerate sebelum expired)
- [ ] Metadata cache dengan TTL 24 jam

### Testing
- [ ] Test koneksi tanpa order (cek balance, harga)
- [ ] Test dengan `LIGHTER_TRADING_ENABLED=false` (harus blocked)
- [ ] Test market order kecil ($10-50) dengan `LIGHTER_TRADING_ENABLED=true`
- [ ] Verifikasi nonce state terpersist di JSON

---

*Dokumentasi ini dibuat berdasarkan implementasi nyata di `backend/app/adapters/gateways/lighter_execution_gateway.py`. Untuk detail implementasi spesifik, baca file tersebut langsung.*
