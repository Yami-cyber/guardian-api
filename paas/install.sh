#!/bin/sh
# Perintah install untuk template Python platform DeployFlow (kolom "Perintah install": sh paas/install.sh).
# Model (IndoBERTweet dasar + bobot fine-tune) TIDAK dimasukkan ke image: image torch + model
# membuat Kaniko kehabisan memori saat snapshot. Keduanya diunduh saat container start (paas/start.sh).
set -e

# torch CPU dulu (tanpa CUDA ~2,5 GB); PyPI jadi indeks cadangan untuk dependensinya.
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
pip install --no-cache-dir -r requirements.txt
