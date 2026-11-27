#!/bin/sh
# Perintah start untuk template Python platform DeployFlow (kolom "Perintah start": sh paas/start.sh).
set -e

export PORT="${PORT:-8000}"
export HF_HOME="${HF_HOME:-/tmp/hf-cache}"
export MODEL_FILE="${MODEL_FILE:-best_weights.pt}"
export MODEL_DIR="${MODEL_DIR:-/tmp/models}"
# Model belum ada saat start; dimuat saat request klasifikasi pertama setelah unduhan selesai.
export PRELOAD_MODEL="${PRELOAD_MODEL:-false}"

# Kunci Firebase dikirim sebagai secret env berisi JSON (platform tidak memasang file rahasia).
if [ -n "$FIREBASE_CREDENTIALS_JSON" ] && [ -z "$FIREBASE_CREDENTIALS_PATH" ]; then
    umask 077
    printf '%s' "$FIREBASE_CREDENTIALS_JSON" > /tmp/firebase-sa.json
    umask 022
    export FIREBASE_CREDENTIALS_PATH=/tmp/firebase-sa.json
fi

# Unduh di latar belakang supaya /health langsung menjawab: model dasar IndoBERTweet lalu bobot fine-tune.
if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
    (python -c "from huggingface_hub import snapshot_download; snapshot_download('indolem/indobertweet-base-uncased')" \
        && python paas/download_weights.py "$MODEL_DIR.part" \
        && mkdir -p "$MODEL_DIR" && mv "$MODEL_DIR.part/$MODEL_FILE" "$MODEL_DIR/$MODEL_FILE" \
        && echo "Model siap di $MODEL_DIR/$MODEL_FILE." \
        || echo "Unduh model gagal: periksa secret env HF_TOKEN." >&2) &
fi

exec gunicorn -c gunicorn.conf.py "app:create_app()"
