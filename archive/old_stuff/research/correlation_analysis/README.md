# Correlation Analysis — BTC vs Altcoins

Riset korelasi harga antara BTC dan token lainnya (ETH, DOGE, LINK, dll.)
sebagai dasar pengambilan keputusan sinyal trading.

## Tujuan

- Mengukur seberapa kuat pergerakan altcoin mengikuti BTC
- Identifikasi lag/lead relationship antar aset
- Analisis perubahan korelasi antar regime pasar (bull/bear/sideways)
- Potensi integrasi sebagai fitur tambahan pada signal engine BTC-QUANT

## Struktur Folder

```
correlation_analysis/
├── notebooks/      ← Jupyter notebook eksplorasi & visualisasi
├── scripts/        ← script Python: fetch data, hitung korelasi, export
├── data/           ← price data CSV (raw & processed)
└── reports/        ← hasil analisis Markdown/PDF
```

## Aset Target

| Aset | Pair | Keterangan |
|------|------|-----------|
| BTC | BTC/USDT | Base asset |
| ETH | ETH/USDT | Market cap #2, korelasi tinggi |
| DOGE | DOGE/USDT | Sentiment-driven, korelasi fluktuatif |
| LINK | LINK/USDT | DeFi oracle, korelasi mid-tier |
| SOL | SOL/USDT | Kandidat tambahan |
| BNB | BNB/USDT | Kandidat tambahan |

## Data Source

- Binance REST API (OHLCV 4H/1D)
- Periode analisis: 2022–2026
