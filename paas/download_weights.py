"""Unduh best_weights.pt dari Hugging Face ke folder tujuan (argumen 1). Token dari env HF_TOKEN bila ada."""

import os
import sys

from huggingface_hub import hf_hub_download

REPO = os.getenv("HF_WEIGHTS_REPO", "ayundaacnt/guardian-bullying-bilstm")
FILE = os.getenv("MODEL_FILE", "best_weights.pt")

target = sys.argv[1] if len(sys.argv) > 1 else "models"
os.makedirs(target, exist_ok=True)
path = hf_hub_download(REPO, FILE, local_dir=target, token=os.getenv("HF_TOKEN") or None)
print(f"Bobot siap: {path}")
