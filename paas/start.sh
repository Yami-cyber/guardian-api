#!/bin/sh
# Perintah start untuk template Python platform DeployFlow (kolom "Perintah start": sh paas/start.sh).
set -e

export PORT="${PORT:-8000}"
export HF_HOME="${HF_HOME:-/app/.hf-cache}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export MODEL_FILE="${MODEL_FILE:-best_weights.pt}"

# Kunci Firebase dikirim sebagai secret env berisi JSON (platform tidak memasang file rahasia).
if [ -n "$FIREBASE_CREDENTIALS_JSON" ] && [ -z "$FIREBASE_CREDENTIALS_PATH" ]; then
    umask 077
    printf '%s' "$FIREBASE_CREDENTIALS_JSON" > /tmp/firebase-sa.json
    umask 022
    export FIREBASE_CREDENTIALS_PATH=/tmp/firebase-sa.json
fi

if [ -f "/app/models/$MODEL_FILE" ]; then
    export MODEL_DIR=/app/models
    export PRELOAD_MODEL="${PRELOAD_MODEL:-true}"
else
    # Bobot tidak ikut image (repo HF gated): unduh di latar belakang supaya /health langsung menjawab.
    # Model dimuat saat request klasifikasi pertama setelah unduhan selesai.
    export MODEL_DIR=/tmp/models
    export PRELOAD_MODEL=false
    if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
        (HF_HUB_OFFLINE=0 python paas/download_weights.py "$MODEL_DIR.part" \
            && mkdir -p "$MODEL_DIR" && mv "$MODEL_DIR.part/$MODEL_FILE" "$MODEL_DIR/$MODEL_FILE" \
            || echo "Unduh bobot gagal: isi secret env HF_TOKEN." >&2) &
    fi
fi

exec gunicorn -c gunicorn.conf.py "app:create_app()"
