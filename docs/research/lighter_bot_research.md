# Panduan Lengkap Membangun Bot Trading di Lighter.xyz

Dokumen ini berisi rangkuman teknis hasil riset dokumentasi Lighter untuk keperluan pembangunan bot eksekusi trading otomatis.

---

## 1. Persyaratan Utama (Prerequisites)

Sebelum mulai membangun bot, pastikan Anda telah menyiapkan hal-hal berikut:

### A. Infrastruktur & Lokasi
*   **Lokasi Server**: Sangat disarankan untuk menggunakan **AWS Tokyo (`ap-northeast-1`)**. Lighter beroperasi dengan latensi rendah di wilayah ini untuk meminimalkan *slippage*.
*   **Koneksi**: Gunakan protokol **WebSocket** untuk pengiriman transaksi (*sendTx*) guna mendapatkan performa eksekusi yang lebih cepat dibandingkan REST API.

### B. Akun & Keamanan
*   **Akun L1 (Ethereum)**: Anda memerlukan kunci privat Ethereum (L1 Private Key) untuk:
    *   Melakukan deposit dana ke L2.
    *   Melakukan *Fast Withdrawals* atau transfer ke alamat lain.
*   **Akun L2 (Lighter)**:
    *   **Account Index**: Identitas numerik unik akun Anda di sistem Lighter.
    *   **API Keys**: Bot beroperasi menggunakan API Key. Setiap akun dapat memiliki hingga 255 API key (Indeks 0-254).
    *   **Penting**: Indeks 0 dan 1 dipesan untuk aplikasi resmi desktop dan mobile. Bot Anda sebaiknya menggunakan indeks 2 ke atas.

---

## 2. Arsitektur Teknis Bot

Bot trading Lighter bekerja di atas lapisan Layer 2 (L2) yang menggunakan model *Orderbook*.

### A. Manajemen Nonce
Setiap transaksi yang dikirim bot harus menyertakan **Nonce**.
*   Nonce bersifat unik per API Key.
*   Harus bertambah secara berurutan (increment +1) untuk setiap transaksi.
*   Jika menggunakan **Python SDK**, sistem akan mengelola nonce secara otomatis. Jika tidak, Anda harus menyimpannya di memori bot Anda.

### B. Presisi Harga & Ukuran (Decimals)
Lighter tidak menerima angka desimal (float) dalam transaksi. Semua nilai harus dikonversi ke basis unit (integer).
*   **Rumus**: `Nilai Transaksi = Harga Riil * 10^jumlah_desimal_market`.
*   Contoh: Jika market ETH/USDC memiliki desimal 6, maka harga $2500 dikirim sebagai `2500000000`.

### C. Tipe Order yang Didukung
*   **Limit Order**: Menetapkan harga spesifik.
*   **Market Order**: Eksekusi langsung di harga pasar.
*   **Post-Only**: Memastikan order hanya masuk sebagai *Maker* (tidak langsung eksekusi).
*   **IOK (Immediate or Cancel)** & **FOK (Fill or Kill)**.

---

## 3. Alur Implementasi (Workflow)

Berikut adalah langkah-langkah untuk mulai menjalankan bot:

1.  **Deposit**: Pastikan dana (ETH/USDC) sudah ada di akun L2 melalui bridge Lighter.
2.  **Instalasi SDK**:
    *   **Python**: `pip install lighter-sdk` (Direkomendasikan untuk pengembangan cepat).
    *   **Go**: `go get github.com/elliottech/lighter-go` (Direkomendasikan untuk *High Frequency Trading*).
3.  **Inisialisasi Signer**: Gunakan API Private Key Anda untuk membuat `SignerClient`. Ini akan menandatangani setiap order secara lokal sebelum dikirim ke server.
4.  **Koneksi Market Data**:
    *   Berlangganan ke channel `Order Book` untuk memantau harga.
    *   Berlangganan ke channel `Account` untuk mendapatkan update status order secara instant (apakah sudah *filled* atau *canceled*).
5.  **Eksekusi Strategi**: Kirim order berdasarkan logika bot melalui endpoint `sendTx`.

---

## 4. Strategi Optimasi (Advanced)

Untuk membuat bot Anda lebih kompetitif dan cepat:

*   **Multi-API Key Parallelism**:
    Gunakan beberapa API Key sekaligus (misal 5-10 key). Karena nonce bersifat unik per key, bot bisa mengirim banyak order secara paralel tanpa harus menunggu antrean nonce dari satu key.
*   **WebSocket sendTx**:
    Alih-alih menggunakan REST POST untuk mengirim order, gunakan format JSON lewat WebSocket yang sudah terbuka. Ini menghemat waktu jabat tangan (*handshake*) TCP/TLS.
*   **Colocation**:
    Pastikan bot berjalan di dalam VPC yang sama atau sangat dekat secara geografis dengan server Lighter di Tokyo.

---

## 5. Referensi Cepat
*   **Base URL (Production)**: `https://mainnet.zklighter.elliot.ai`
*   **WSS URL (Production)**: `wss://mainnet.zklighter.elliot.ai/stream`
*   **GitHub SDK**: [Lighter Python SDK](https://github.com/elliottech/lighter-python)
