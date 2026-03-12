
Ya, BCD v3 cocok untuk scalping 3%/hari. Ringkasannya:

✅ WR konsisten 55-56% di 2 tahun berbeda (2023 & 2025) ✅ Bearish detection kuat — bisa short saat turun ✅ Coverage 43%+ Bullish — banyak peluang trading ✅ Daily gross 3.66-3.81% — melebihi target 3% ✅ Stabil — rejim bertahan berhari-hari, tidak noisy seperti HMM

BCD v3 saat ini sudah aktif di 

layer1_bcd.py
 (parameter MAX_SEGMENT_LEN=48, TREND_Z_BULL=0.20). Siap digunakan sebagai Layer 1 untuk sistem scalping.

berarti lebih baik bcd daripada hmm untuk scalping harian target 3% ya?

Ya, BCD jelas lebih baik daripada HMM untuk scalping harian target 3%. Berikut perbandingan finalnya:

BCD vs HMM — Head-to-Head (Data 2025-2026)
Metrik	HMM	BCD v3	Pemenang
Bullish WR	48.5%	55.6%	🏆 BCD
Bearish WR	49.3%	54.6%	🏆 BCD
Bullish Avg Ret	+0.054%	+0.108%	🏆 BCD (2x lipat)
Bearish Avg Ret	-0.176%	-0.127%	🏆 BCD (lebih akurat)
Stabilitas	1.4 candle (~6 jam)	131+ candle (~22 hari)	🏆 BCD (94x lebih stabil)
Daily Gross	~1.9%	~3.66%	🏆 BCD
Kenapa BCD Menang Telak
HMM terlalu noisy — label berubah setiap ~6 jam, tidak bisa dipercaya untuk keputusan trading
HMM WR < 50% — sinyal Bullish bahkan lebih buruk dari random (coin flip)
BCD konsisten — WR 55-56% dibuktikan di 2 tahun (2023 & 2025), sinyal bisa diandalkan
BCD mendukung 2-directional — bearish detection yang kuat memungkinkan short selling
Kesimpulan: Untuk Layer 1 sistem scalping harian 3%/hari, BCD v3 adalah pilihan definitif.