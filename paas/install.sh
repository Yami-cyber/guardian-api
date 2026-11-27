#!/bin/sh
# Perintah install untuk template Python platform DeployFlow (kolom "Perintah install": sh paas/install.sh).
set -e

# torch CPU dulu (tanpa CUDA ~2,5 GB); PyPI jadi indeks cadangan untuk dependensinya.
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
pip install --no-cache-dir -r requirements.txt

# Model dasar IndoBERTweet ikut masuk image, supaya container tidak mengunduh ~400 MB saat start.
export HF_HOME=/app/.hf-cache
python -c "from transformers import AutoModel, AutoTokenizer; m='indolem/indobertweet-base-uncased'; AutoTokenizer.from_pretrained(m); AutoModel.from_pretrained(m)"

# Bobot fine-tune: repo HF masih gated, jadi tanpa token unduhan ini gagal dan dilakukan saat start (HF_TOKEN).
python paas/download_weights.py models || echo "Bobot belum ikut image; akan diunduh saat start dengan HF_TOKEN."
