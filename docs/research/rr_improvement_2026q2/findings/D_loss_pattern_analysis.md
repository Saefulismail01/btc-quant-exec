# Empirical loss pattern (proxy dari export Lighter)

**Area:** D — Empirical Loss Pattern Analysis  
**Status:** Partial — **bukan** `live_trades`; episode = agregasi FIFO fill (`aggregate_lighter_roundtrips.py`)  
**Updated:** 2026-04-24

## TL;DR

Dari **27** episode round-trip **lengkap** (export `lighter-trade-export-2026-04-24T01_03_31.715Z-UTC.csv`), win rate **74.1%**, total PnL teragregasi **+$6.23** (kolom `Closed PnL` per fill). Ada **7** kerugian dengan pola **wins-before-loss** bervariasi (0–7); **sample kecil** → tidak membuktikan/menolak hipotesis “loss setelah streak win besar”.

## Konteks intervensi (laporan sebelumnya)

`performance_logbook_mar_apr_2026.qmd` mendokumentasikan **intervensi manual** (geser SL/TP / tutup dari dashboard) pada beberapa tanggal April (**3, 4, 7, 10, 12 Apr**), plus isu **sizing** 12–14 Apr — dan menekankan lesson learned: hindari intervensi; EV potensi ~\$35 vs aktual setelah adjustment.

**Pembaruan operasional:** rentang **tanpa intervensi manual = 20–24 April 2026** (inklusif), per operator. Episode di CSV **2026-04-02 … 2026-04-24** masih mencampur hari dengan intervensi terdokumentasi di logbook; analisis “murni bot” harus **membatasi** ke episode yang close (dan idealnya open) di **20 Apr–24 Apr** ke atas.

## Methodology

- Script: `docs/research/rr_improvement_2026q2/scripts/aggregate_lighter_roundtrips.py`  
- Sumber fill: `lighter-trade-export-2026-04-24T01_03_31.715Z-UTC.csv` (root repo)  
- Episode **incomplete** (posisi masih terbuka di akhir file): 1 baris (`complete=False`) — **dikecualikan** dari statistik utama.  
- Output per episode: `docs/research/rr_improvement_2026q2/data/episodes_lighter_2026-04-24.csv`

## Findings

### Subset “tanpa intervensi” **20–24 Apr 2026** (UTC, definisi ketat)

Definisi dipakai di skrip: episode **`complete=True`** dan **`t_open` ≥ 2026-04-20 00:00 UTC** serta **`t_close` ≤ 2026-04-24 23:59:59.999 UTC** (hari kalender inklusif). Perintah:

`python scripts/aggregate_lighter_roundtrips.py --episode-window-utc 2026-04-20 2026-04-24`

| Metrik | Nilai |
|--------|--------|
| n episode | **5** |
| Win rate | **60%** (3W / 2L) |
| Total PnL USD | **-2.21** |
| Median hold (jam) | **5.51** |

Episode yang masuk: indeks global **23–27** pada agregasi penuh (buka 21–22 Apr, tutup ≤ 22 Apr — tidak ada episode yang sepenuhnya jatuh hanya pada 20 Apr; **20 Apr** tidak punya episode lengkap di file ini). Buka **24 Apr** (indeks 28) **tidak** `complete` → tidak masuk subset.

**Interpretasi:** **n=5** → tidak signifikan; subset ini saja **tidak** mendukung generalisasi WR tinggi Mar–Apr logbook.

### D.1 Distribusi loss vs posisi dalam streak (wins sebelum loss)

Urutan menurut **`t_close`** episode lengkap. Untuk setiap loss, hitung jumlah win berturut-turut sejak loss sebelumnya.

| `n_wins_before_loss` | Jumlah loss | Catatan |
|----------------------|---------------|---------|
| 0 | 1 | Loss tanpa win sebelumnya (langsung setelah loss lain / awal rantai) |
| 1 | 2 | |
| 2 | 1 | |
| 4 | 1 | |
| 5 | 1 | |
| 7 | 1 | |

**Daftar nilai per kejadian loss (kronologis):** `[5, 1, 7, 0, 4, 1, 2]` — dihitung dengan skrip satu-pass sesi 2026-04-24.

`avg_loss_pct`: **TIDAK TERSEDIA** — export tidak menyimpan margin per episode; hanya **USD** (`pnl_usd`). Dari `data/episodes_lighter_2026-04-24.csv` (`complete=True`): rata-rata PnL **loss** = **-5.25 USD** (n=7), rata-rata **win** = **+2.15 USD** (n=20) — dihitung `mean(pnl_usd)` per kelompok `win`.

**Signifikansi statistik:** **n=7 loss** → README: flag **tidak signifikan** untuk inferensi “cluster di puncak”.

### D.2 Holding time distribution

| Kelompok | n | median hold (jam) | p25 | p75 |
|----------|---|-------------------|-----|-----|
| Winner | 20 | 4.81 | ≈1.60 | ≈6.88 |
| Loser | 7 | 5.20 | ≈2.01 | ≈6.88 |

(Perhitungan: `describe()` pada kolom `hold_hours` episode lengkap, dipisah `win` True/False.)

### D.3 MFE / MAE

**TIDAK TERSEDIA** — export tidak berisi path harga intraday per posisi.

### D.4 Time-of-day (UTC) — exit hour

Agregasi per **jam UTC** dari `t_close` (n per jam kecil):

| hour_UTC | n | WR |
|----------|---|-----|
| 1 | 2 | 0.50 |
| 2 | 2 | 1.00 |
| 4 | 1 | 1.00 |
| 6 | 1 | 0.00 |
| 7 | 1 | 1.00 |
| 8 | 2 | 1.00 |
| 9 | 3 | 1.00 |
| 13 | 5 | 1.00 |
| 16 | 1 | 1.00 |
| 17 | 4 | 0.75 |
| 22 | 3 | 0.33 |
| 23 | 2 | 0.00 |

Jam **22–23 UTC** menunjukkan WR rendah pada contoh ini — **n≤3 per sel** → tidak signifikan.

### D.5 Side bias

| side | n | WR |
|------|---|-----|
| LONG | 23 | 0.739 |
| SHORT | 4 | 1.000 |

SHORT **n=4** → tidak signifikan.

## Gaps & Limitations

- Bukan **`live_trades`** + `exit_type` (TP/SL) bot.  
- Tidak ada **MFE/MAE**, tidak ada **%** loss relatif margin.  
- Plot `findings/plots/D_*.png` **tidak** dihasilkan (sampel kecil + prioritas waktu).

## Raw Sources

- `lighter-trade-export-2026-04-24T01_03_31.715Z-UTC.csv`  
- `scripts/aggregate_lighter_roundtrips.py`  
- `data/episodes_lighter_2026-04-24.csv`  
- `docs/reports/live_trading/performance_logbook_mar_apr_2026.qmd` (§ intervensi, tbl April)  
- Pernyataan operasional: **tanpa intervensi 20–24 Apr 2026** — **catatan sesi 2026-04-24** (user), tidak tersimpan di logbook PDF/qmd.
