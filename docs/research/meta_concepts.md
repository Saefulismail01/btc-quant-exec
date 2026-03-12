# BTC-QUANT Meta-Konsep & Arsitektur Layer

Dokumen ini menjelaskan struktur tingkat tinggi dari platform **BTC-QUANT** dan bagaimana setiap lapisan (layer) bekerja sama untuk menghasilkan sinyal trading.

## 1. Peta Konsep Arsitektur Komprehensif (Mermaid)

Berikut adalah visualisasi lengkap seluruh ekosistem BTC-QUANT, dari sumber data hingga representasi visual.

```mermaid
graph TD
    %% ==========================================
    %% 1. DATA INGESTION LAYER (Sourcing & Storage)
    %% ==========================================
    subgraph Ingestion [Layer 0: Ingesti Data & Persistensi]
        BIN[Binance Futures API] -->|REST & Websocket| ENG(Data Engine)
        
        %% Detail Data Points yang ditarik
        subgraph Data_Points [Data Point Spesifik]
            OHLCV[OHLCV: Harga & Volume]
            OI_Hist[Open Interest: Total & Change]
            Funding[Funding Rate: Sentiment Cost]
            Micro[Microstructure: CVD & Liquidation]
        end
        
        BIN -.-> OHLCV & OI_Hist & Funding & Micro
        OHLCV & OI_Hist & Funding & Micro --> ENG
        ENG -->|Auto-Upsert 60s| DDB[(DuckDB: btc-quant.db)]
    end

    %% ==========================================
    %% 2. QUANTUM ANALYSIS PIPELINE (Multi-Layer)
    %% ==========================================
    subgraph Pipeline [Quantum Analysis Pipeline]
        DDB -->|Fetch Features| L1_HMM[Layer 1: HMM Engine]
        DDB -->|Fetch Technicals| L2_Tech[Layer 2: Technical Engine]
        DDB -->|Fetch ML Inputs| L3_AI[Layer 3: AI/ML Engine]
        DDB -->|Fetch Context| L5_LLM[Layer 5: Narrative Engine]

        %% Detail Layer 1: Market Regime
        subgraph L1_Detail [Analisis Kondisi Pasar - HMM]
            L1_HMM -->|Statistical Clustering| HMM_States{Mapping 4 State}
            HMM_States -->|Trending Up| Bull[Bullish / Trend]
            HMM_States -->|Trending Down| Bear[Bearish / Trend]
            HMM_States -->|Low Vol| Calm[Sideways / Calm]
            HMM_States -->|High Vol| Vol[Choppy / Volatile]
        end

        %% Detail Layer 2: Technical Flow
        subgraph L2_Detail [Konfirmasi Tren & Momentum]
            L2_Tech -->|Ichimoku Cloud| Cloud{Harga vs Senkou}
            L2_Tech -->|EMA Confluence| EMA{Cross 9/21/50}
            Cloud & EMA -->|Trend Sync| Tech_Score[Technical Trend Score]
        end

        %% Detail Layer 3: AI Signal Intelligence
        subgraph L3_Detail [Probabilitas Pola Non-Linear]
            L3_AI -->|Pre-Processing| Scaler[Standard Scaler Manager]
            Scaler -->|Input Layer| MLP[Neural Network MLP]
            MLP -->|Softmax Layer| AI_Prob[Signal Probability: 0-1]
        end
    end

    %% ==========================================
    %% 3. DECISION & RISK MANAGEMENT
    %% ==========================================
    subgraph Decision [Layer 4: Decision & Risk Execution]
        %% Cross-Layer Confluence
        Bull & Bear & Calm & Vol -->|Context Filter| L4_Main(Decision Engine)
        Tech_Score -->|Directional Confirm| L4_Main
        AI_Prob -->|Mathematical Edge| L4_Main

        %% Logic Trigger
        L4_Main -->|Confluence Score > 0.7| SIG{Signal Trigger}
        
        %% Risk & Execution
        SIG -->|Entry Buy/Sell| RISK[Risk Management]
        RISK -->|ATR-based Vol| SL_TP[Dynamic SL/TP]
        RISK -->|Kelly Criterion| Size[Position Sizing]
        
        Size & SL_TP --> EXEC[Final Execution Signal]
    end

    %% ==========================================
    %% 4. PRESENTATION LAYER
    %% ==========================================
    subgraph Presentation [Output Dashboard & Narasi]
        EXEC -->|Signal Context| L5_LLM[Layer 5: Narrative Engine]
        L5_LLM -->|GPT-4/Claude Context| NARR[Narrative & Rationale]
        EXEC & NARR --> API[FastAPI Backend]
        API -->|JSON Response| UI[[React Dashboard UI]]
    end

    %% ==========================================
    %% STYLING & COLOR CODING (Disesuaikan)
    %% ==========================================
    style BIN fill:#fff176,stroke:#fbc02d,color:#000
    style ENG fill:#81d4fa,stroke:#0288d1,color:#000
    style DDB fill:#2196f3,stroke:#0d47a1,color:#fff,stroke-width:3px
    
    style L1_Detail fill:#fff3e0,stroke:#ff9800
    style L2_Detail fill:#e8f5e9,stroke:#4caf50
    style L3_Detail fill:#f3e5f5,stroke:#9c27b0
    
    style L4_Main fill:#ff7043,stroke:#d84315,color:#fff,stroke-width:2px
    style SIG fill:#4caf50,stroke:#1b5e20,color:#fff
    style EXEC fill:#ffd54f,stroke:#ff8f00,color:#000,stroke-width:4px
    
    style UI fill:#1a1a1a,stroke:#00e676,color:#00e676,stroke-width:4px
```

---

## 2. Detail Fungsional Setiap Layer

### Layer 1: Market Regime Detection (HMM)
- **Fungsi**: Mesin deteksi kondisi struktural pasar.
- **Input**: Log returns, realized volatility (14), HL candle range, dan **OI Rate of Change**.
- **Algoritma**: *Hidden Markov Model* (HMM) dengan distribusi Gaussian.
- **Output**: 4 State pasar (Bullish, Bearish, Calm, Volatile).
- **Deep Tech**: Menggunakan algoritma **Baum-Welch** untuk estimasi parameter dan **Viterbi** untuk menentukan urutan state paling mungkin. Layer ini krusial karena menentukan parameter risiko di Layer 4.

### Layer 2: Technical Trend Confluence (EMA & Ichimoku)
- **Fungsi**: Konfirmasi arah momentum secara deterministik.
- **Input**: Harga OHLCV.
- **Konfigurasi**:
  *   **EMA Confluence**: Perpotongan EMA 9, 21, dan 50.
  *   **Ichimoku Cloud**: Posisi harga terhadap Senkou Span A/B (Cloud) dan Kijun-Sen.
- **Output**: Technical Score (Aligned vs Not Aligned).

### Layer 3: AI Signal Intelligence (MLP)
- **Fungsi**: Prediksi pola non-linear jangka pendek.
- **Arsitektur**: *Multi-Layer Perceptron* (Neural Network) dengan 2 hidden layers (64x32 atau 128x64).
- **HMM Feature Cross**: Salah satu fitur tercanggih — input HMM dari Layer 1 dimasukkan ke dalam Layer 3 sebagai fitur tambahan (*One-Hot*), menyilangkan konteks regime dengan prediksi harga.
- **Statistik**: Berfungsi sebagai filter probabilitas (Softmax score > 55% untuk konfirmasi).

### Layer 4: Decision Engine & Risk Execution
- **Fungsi**: Agregator keputusan dan manajemen modal.
- **Logika**: Menggabungkan L1 (Konteks), L2 (Momentum), dan L3 (Probabilitas AI) menjadi **Skor Konfluens (0-100)**.
- **Manajemen Risiko**:
  *   **Dynamic SL/TP**: 1.5x ATR dari harga entry.
  *   **Sizing**: Menggunakan perhitungan **Kelly Criterion** disesuaikan dengan volatilitas pasar.
  *   **Leverage**: Dinamis (2x - 7x) bergantung pada rasio ATR/Price.

### Layer 5: Sentiment, Narrative & LLM Synthesis
- **Fungsi**: Penerjemah strategis dan filter psikologi.
- **Model**: LLM (OpenAI/Kimi) dengan *Zero-Shot Chain-of-Thought*.
- **Input Utama**: Menerima data kuantitatif gabungan dari **Layer 4**.
- **Truth Enforcer**: Mengunci narasi LLM agar tidak bertentangan dengan data kuantitatif:
  *   Jika Skor Konfluens < 40%, narasi dipaksa menjadi **NEUTRAL**.
  *   Jika Skor > 80%, narasi dipaksa memberikan justifikasi untuk **STRONG SIGNAL**.

---

## 3. Perkembangan Hasil Backtest

Evolusi performa BTC-QUANT dibagi menjadi dua fase utama:

### Fase 1: Baseline OHLCV (Februari 2026 Awal)
*   **Strategi**: Hanya menggunakan harga (High, Low, Close, Volume).
*   **Hasil**:
    *   **Akurasi Direksional HMM**: ~40-48%.
    *   **Kelemahan**: Sering terjadi "false signal" saat market choppy karena HMM tidak memiliki konteks likuiditas atau dominasi posisi (Open Interest).
    *   **Insight**: Model cenderung bias ke arah tren dominan terakhir (momentum-heavy).

### Fase 2: Integrasi Mikrostruktur (Maret 2026)
*   **Perubahan**: Menambahkan fitur **Open Interest (OI)** dan **Funding Rate**. 
*   **Implementasi**: Fitur `oi_rate_of_change` dimasukkan ke dalam HMM Training.
*   **Hasil Evaluasi Terbaru (2026-03-01)**:
    *   **Akurasi**: Masih berada di range 42-45% untuk prediksi direksional murni (~168 bar data).
    *   **Peningkatan**: Model lebih responsif terhadap lonjakan posisi (OI Spike). HMM sekarang memiliki kemampuan "Feature Dropping" — jika data mikrostruktur lama tidak ada, model tetap bisa train menggunakan OHLCV tanpa crash.
    *   **Kesimpulan**: Penambahan mikrostruktur meningkatkan "Keyakinan" (Confidence) model pada saat terjadi *breakout* yang didukung volume dan OI, meskipun probabilitas statistik mentah belum naik signifikan karena keterbatasan window data historis.

---

## 4. Aliran Data Mikrostruktur
Model sekarang tidak hanya melihat *apa* yang terjadi (Harga), tapi *siapa* dan *seberapa besar* dorongan di baliknya:
- **Open Interest**: Menunjukkan apakah uang baru sedang masuk (uptrend sehat) atau hanya *short covering* (uptrend lemah).
- **Funding Rate**: Menunjukkan agresi dari sisi Long vs Short.
