# BTC-QUANT: Master Architecture Diagram (Mermaid)

File ini berisi master diagram **BTC-QUANT v2.1** yang paling detail, menjelaskan alur data dari sumber mentah (Binance) hingga menjadi keputusan trading yang terukur.

```mermaid
graph TD
    %% ==========================================
    %% 0. DATA INGESTION LAYER
    %% ==========================================
    subgraph L0 [Layer 0: Ingestion & Storage]
        direction LR
        BIN[Binance API] --- ENG(Data Engine)
        ENG --- DDB[(btc-quant.db)]
        
        subgraph L0_Detail [Metrics Captured]
            OHLCV[OHLCV]
            OI[Open Interest]
            FR[Funding Rate]
            MS[Microstructure]
        end
        BIN -.-> L0_Detail
        L0_Detail --> ENG
    end

    %% ==========================================
    %% 1. ANALYSIS PIPELINE
    %% ==========================================
    subgraph L1_3 [Analysis Pipeline]
        direction TB
        DDB ==> L1[Layer 1: HMM Engine]
        DDB ==> L2[Layer 2: Technical Engine]
        DDB ==> L3[Layer 3: AI/ML Engine]

        L1 ---|Market Regime| L1_R{Regime}
        L2 ---|Trend Confluence| L2_C{Technical}
        L3 ---|Pattern Probability| L3_P{AI Signal}
        
        %% Feature Cross (PHASE 3)
        L1 -.->|Regime Context| L3
    end

    %% ==========================================
    %% 2. DECISION & RISK (EXECUTION)
    %% ==========================================
    subgraph L4 [Layer 4: Decision & Risk]
        direction TB
        L1_R & L2_C & L3_P ==> DE(Decision Engine)
        
        DE -->|Score > 0.7| SIG{Signal}
        SIG -->|Entry| RISK[Risk Manager]
        
        subgraph Risk_Detail [Risk Parameters]
            ATR[ATR-based SL/TP]
            Kelly[Kelly Sizing]
            Lev[Dynamic Leverage]
        end
        RISK --- Risk_Detail
        Risk_Detail --> EXEC([Final Execution Signal])
    end

    %% ==========================================
    %% 3. NARRATIVE & PRESENTATION
    %% ==========================================
    subgraph L5 [Layer 5: Narrative & UI]
        direction LR
        EXEC ==> L5_N(Narrative Engine)
        L5_N ---|Contextual Rationale| DASH[[React Dashboard UI]]
    end

    %% ==========================================
    %% STYLING & BRANDING
    %% ==========================================
    style BIN  fill:#FFF9C4,stroke:#FBC02D,stroke-width:2px
    style DDB  fill:#BBDEFB,stroke:#1976D2,stroke-width:3px
    style DE   fill:#FFCCBC,stroke:#E64A19,stroke-width:3px
    style EXEC fill:#C8E6C9,stroke:#388E3C,stroke-width:4px
    style DASH fill:#212121,stroke:#00E676,stroke-width:3px,color:#00E676

    classDef engine fill:#F5F5F5,stroke:#9E9E9E,stroke-width:1px
    class L1,L2,L3,L5_N engine
``````

### 🛠️ Deep-Dive Teknis Per Layer (v2.1)

#### **Layer 0: Data Ingestion & Storage**
*   **Pipeline**: Menggunakan REST + Websocket (Binance Futures).
*   **Database**: **DuckDB** (`btc-quant.db`). Dipilih karena performa query OLAP yang sangat cepat untuk data *time-series* lokal.
*   **Metrics**: Selain OHLCV dasar, sistem menangkap:
    *   **Open Interest (OI)**: Mengukur aliran modal baru (kekuatan tren).
    *   **Funding Rate**: Mengukur agresi (bias) antara Long vs Short.
    *   **Liquidations**: Mendeteksi *exhaustion* pasar atau potensi *squeeze*.

#### **Layer 1: Market Regime Detection (HMM)**
*   **Algoritma**: *Hidden Markov Model* (Baum-Welch untuk training, Viterbi untuk decoding).
*   **States**: Membagi pasar menjadi 4 regime (diklasifikasi otomatis):
    1.  **Bullish**: Return positif, Volatilitas moderat.
    2.  **Bearish**: Return negatif, Volatilitas tinggi.
    3.  **Calm (Sideways)**: Volatilitas rendah, akumulasi.
    4.  **Volatile (Choppy)**: Noise tinggi, pergerakan tanpa arah yang jelas.
*   **Feature Cross**: Output regime dari L1 dikirim ke L3 sebagai fitur tambahan (*One-Hot Encoded*).

#### **Layer 2: Technical Confluence Engine**
*   **Konfirmasi Tren**: Menggunakan EMA Confluence (9, 21, 50) dan struktur Ichimoku Cloud.
*   **Logic**: Sinyal dianggap valid hanya jika harga berada di sisi yang benar dari "awan" (Cloud) dan susunan EMA menunjukkan momentum yang searah.

#### **Layer 3: AI Signal Intelligence (MLP)**
*   **Arsitektur**: *Multi-Layer Perceptron* (Neural Network).
*   **Input**: 5 fitur teknikal + 4 fitur regime dari HMM (HMM→MLP Cross).
*   **Training**: Menggunakan *Online Training* (Adam Solver, ReLU Activation). Model dilatih ulang setiap siklus untuk menangkap pola mikro terbaru.
*   **Output**: Prediksi probabilitas arah harga periode berikutnya (Softmax score).

#### **Layer 4: Decision & Risk Management (The Brain)**
*   **Confluence Score**: Menggabungkan probabilitas dari L1, L2, dan L3 menjadi satu angka (0–100).
*   **Risk Engine**:
    *   **SL/TP**: Berbasis **ATR** (*Average True Range*) untuk adaptasi terhadap volatilitas.
    *   **Sizing**: Menggunakan **Kelly Criterion** untuk memaksimalkan pertumbuhan akun tanpa risiko berlebihan.
    *   **Leverage**: Dinamis (2x – 7x) berdasarkan rasio volatilitas pasar saat ini.

#### **Layer 5: Narrative & Truth Enforcer**
*   **Narrative Engine**: LLM (OpenAI/Kimi) bertindak sebagai analis strategis.
*   **Truth Enforcer**: Mekanisme keamanan untuk mencegah halusinasi LLM.
    *   Jika Skor < 40: Dipaksa **NEUTRAL**.
    *   Jika Skor > 80: Dipaksa **STRONG** (Arah sesuai trend).
*   **Input**: Menerima data mentah dan *Decision Result* dari Layer 4 sebagai konteks utama narasi.
