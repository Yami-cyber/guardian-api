# GUARDIAN API

API FastAPI untuk model deteksi perundungan `ayundaacnt/guardian-bullying-bilstm` (`best_weights.pt`, PyTorch).

## Model

Arsitektur dibaca dari isi `best_weights.pt` (kode training tidak tersedia):

| Bagian | Isi |
|---|---|
| `encoder` | IndoBERT base, 12 lapis, hidden 768, vocab 31923 (= `indolem/indobert-base-uncased`) |
| `lstm` | LSTM 768 ke 128, bidirectional |
| `classifier` | Linear 256 ke 2: indeks 0 = `bukan_bullying`, 1 = `bullying` |

Pooling default `last` (gabungan hidden state akhir maju dan mundur). Diuji dengan kalimat contoh:
kalimat kasar/menghina mendapat skor bullying 0,92 sampai 0,96, kalimat sopan 0,05 sampai 0,11.
Pooling dan label bisa diubah lewat env `POOLING` (`last`/`mean`/`first`) dan `LABELS` kalau kode training berkata lain.

`install.sh` mengunduh tokenizer IndoBERT dan `best_weights.pt` saat build, dikunci ke revisi tertentu, supaya ikut
masuk image. Kalau repo bobot masih **gated**, unduhan bobot saat build gagal (build tetap lanjut), lalu aplikasi
mengunduhnya saat start dengan secret env `HF_TOKEN`. Disarankan: matikan gating di HF.

## Endpoint

| Endpoint | Isi |
|---|---|
| `GET /health` | selalu 200 selama server hidup; `model_loaded` dan `error` menunjukkan status model |
| `GET /predict?text=...` | prediksi (dipakai uji beban k6, yang hanya mengirim GET) |
| `POST /predict` `{"text": "..."}` | prediksi |

Contoh jawaban: `{"label": "bullying", "scores": {"bukan_bullying": 0.054, "bullying": 0.946}}`

## Isian wizard Tambah Aplikasi (komponen `api`)

| Kolom | Isi |
|---|---|
| Template | Python (FastAPI) |
| Repo / branch | URL repo ini / `main` |
| Perintah install | `sh install.sh` |
| Perintah start | kosong (default `uvicorn main:app`) |
| Port | 8000 |
| Path ingress | `/` |
| Health path | `/health` |
| Path uji beban | `/predict?text=kamu%20bodoh%20sekali` |
| Database | tidak perlu |
| Ukuran resource pod | Besar |
| Replika min / maks | 1 / 2 |
| Secret env (hanya kalau masih gated) | `HF_TOKEN` = token read HF |

Catatan beban: satu prediksi butuh kira-kira 80 ms CPU (laptop, 1 thread). Dengan limit 2 CPU per pod,
throughput per pod hanya puluhan request/detik, jadi uji performa sebaiknya memakai VU kecil.
