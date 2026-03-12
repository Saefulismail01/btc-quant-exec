# Rekap Pembaruan Arsitektur v2.1 & Analisis (Maret 2026)

## 1. Refactoring Layer 5 (Narrative & Sentiment)
- **Masalah Sebelumnya**: Layer 5 (Sentiment) berdiri sendiri mengambil data Fear & Greed dan mencampurnya secara paralel, yang berpotensi menghasilkan narasi LLM yang tidak sinkron dengan keputusan kuantitatif mesin.
- **Pembaruan Teknis**: Layer 5 kini dikonsolidasikan menjadi `narrative_service.py`. Ia secara ketat beroperasi di *downstream* Layer 4. Layer 5 menerima hasil akhir dari **Decision Engine** (Skor Konfluensi, Status HMM, Level Risiko) sebagai *Prompt Context* utama. Hal ini memastikan narasi yang dikembalikan ke UI selalu memberikan justifikasi yang selaras dengan angka teknikal.
- **Pembersihan**: File usang `sentiment_service.py` telah dihapus seluruhnya.

## 2. Peningkatan Dokumentasi Arsitektur
- **[diagram_arsitektur.md](../diagram_arsitektur.md)**: Telah ditulis ulang secara total dengan MermaidJS tingkat lanjut. Mencakup alur *subgraph* yang lebih terstruktur (L0 hingga L5), pewarnaan fungsional, dan penjelasan *deep-dive* per layer (Algoritma, Fitur, dan Output).
- **[metakonsep.md](../metakonsep.md)**: Diselaraskan dan diperbarui mengikuti standar diagram arsitektur v2.1.
- **[arsitektur_detail.html](../arsitektur_detail.html)**: Dibuat versi HTML *standalone* agar seluruh tim dapat melihat diagram arsitektur secara responsif langsung di browser tanpa ketergantungan pada ekstensi editor kode.

## 3. Catatan Analisis AI (Layer 3)
- Telah didokumentasikan evaluasi pemilihan arsitektur **MLP (Multi-Layer Perceptron)** dibandingkan kandidat lain seperti RNN/LSTM.
- **Keunggulan sistem saat ini**: MLP dipadukan dengan *One-Hot Encoding* dari hasil **HMM (Layer 1)** memungkinkan mesin untuk mengisolasi kondisi pasar (regime-aware) dan melakukan *Online Training* super cepat di CPU dalam hitungan milidetik, menjadikannya sangat ideal untuk sistem *Scalping* yang responsif.
