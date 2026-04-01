# Orderflow Analysis

Folder ini khusus untuk riset/analisa *orderflow* (mis. footprint, delta, imbalance, volume profile, liquidity sweep, dll) agar terpisah dari komponen eksekusi.

## Rekomendasi Struktur

- `data/` : raw/export data (csv/parquet). (Opsional; kalau data besar, jangan di-commit)
- `notebooks/` : eksplorasi cepat.
- `scripts/` : pipeline analisa yang bisa di-run ulang.
- `results/` : output (chart, report, metrics).

## Catatan

- Simpan referensi sumber data & timeframe di setiap eksperimen.
- Usahakan setiap script punya entrypoint yang jelas (mis. `python scripts/run_*.py`).

