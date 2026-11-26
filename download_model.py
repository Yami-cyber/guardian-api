"""Unduh file model GUARDIAN dari Hugging Face, dikunci ke revisi (commit) tertentu supaya image selalu sama.

- Bobot fine-tune: ayundaacnt/guardian-bullying-bilstm / best_weights.pt (IndoBERT + BiLSTM + classifier).
- Tokenizer: indolem/indobert-base-uncased (vocab 31923, sama dengan embedding di best_weights.pt).

Dipanggil saat build (install.sh) dan, kalau file belum ada, saat aplikasi start (main.py).
Repo bobot yang gated butuh HF_TOKEN; tanpa gating cukup tanpa token.
"""

import os
import sys
import urllib.request
from pathlib import Path

WEIGHTS_REPO = os.environ.get("MODEL_REPO", "ayundaacnt/guardian-bullying-bilstm")
WEIGHTS_REVISION = os.environ.get("MODEL_REVISION", "a8c1ee68de3b18eeeafa9358fb03d9a41eba45cb")
TOKENIZER_REPO = "indolem/indobert-base-uncased"
TOKENIZER_REVISION = "7ccb3cd0f5b08ffbaa465aade22328e8600e23eb"
TOKENIZER_FILES = ["vocab.txt", "tokenizer_config.json", "special_tokens_map.json"]


def fetch(repo: str, revision: str, filename: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
    req = urllib.request.Request(url, headers={"User-Agent": "guardian-api"})
    token = os.environ.get("HF_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    tmp = dest.with_name(dest.name + ".part")
    print(f"Mengunduh {url} ...", flush=True)
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    tmp.replace(dest)
    print(f"Selesai: {dest} ({dest.stat().st_size / 1e6:.1f} MB)", flush=True)
    return dest


def download_tokenizer(model_dir: Path) -> Path:
    for name in TOKENIZER_FILES:
        fetch(TOKENIZER_REPO, TOKENIZER_REVISION, name, model_dir / "tokenizer" / name)
    return model_dir / "tokenizer"


def download_weights(model_dir: Path) -> Path:
    return fetch(WEIGHTS_REPO, WEIGHTS_REVISION, "best_weights.pt", model_dir / "best_weights.pt")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "model")
    download_tokenizer(target)  # repo publik tanpa gating: wajib berhasil
    try:
        download_weights(target)
    except Exception as exc:  # build tetap lanjut; main.py mencoba lagi saat start
        print(f"PERINGATAN: gagal mengunduh best_weights.pt saat build: {exc}", file=sys.stderr)
        print("Kemungkinan repo model masih gated. Matikan gating atau isi HF_TOKEN (secret env).", file=sys.stderr)
