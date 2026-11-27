# Deploy lewat platform DeployFlow (template Python)

Kode aplikasi tidak diubah. Folder ini hanya menambah perintah install dan start untuk template Python.

| Kolom komponen | Isi |
|---|---|
| Perintah install | `sh paas/install.sh` |
| Perintah start | `sh paas/start.sh` |
| Port | 8000 |
| Health path | `/health` |

Secret env (diketik admin di halaman komponen, tidak pernah di-commit):

| Nama | Isi |
|---|---|
| `HF_TOKEN` | token read Hugging Face (repo bobot masih gated) |
| `GEMINI_API_KEY` | kunci Gemini (tanpa ini penjelasan memakai template bawaan) |
| `FIREBASE_CREDENTIALS_JSON` | isi lengkap `serviceAccountKey.json` (tanpa ini endpoint selain `/health` gagal) |

Model dasar IndoBERTweet dan bobot `best_weights.pt` diunduh di latar belakang saat container start
(tidak masuk image: torch + model membuat Kaniko kehabisan memori), jadi `/health` langsung menjawab;
model dimuat saat request klasifikasi pertama setelah unduhan selesai.
