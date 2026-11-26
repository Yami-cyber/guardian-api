"""GUARDIAN API: deteksi perundungan (bullying) pada teks berbahasa Indonesia.

Arsitektur dibaca dari best_weights.pt (kode training tidak tersedia):
  encoder    = IndoBERT base (indolem/indobert-base-uncased, 12 lapis, hidden 768)
  lstm       = LSTM(768 -> 128, bidirectional)
  classifier = Linear(256 -> 2)
Cara mengambil vektor dari BiLSTM (POOLING) dan urutan label (LABELS) belum dikonfirmasi dari kode training.
"""

import os
import threading
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from torch import nn
from transformers import BertConfig, BertModel, BertTokenizerFast

from download_model import download_tokenizer, download_weights

torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "1")))

BUILD_DIR = Path(os.environ.get("MODEL_DIR", "/app/model"))
RUNTIME_DIR = Path("/tmp/model")  # /app tidak bisa ditulis user non-root
MAX_LEN = int(os.environ.get("MAX_LEN", "128"))
POOLING = os.environ.get("POOLING", "last")  # last | mean | first
LABELS = [s.strip() for s in os.environ.get("LABELS", "bukan_bullying,bullying").split(",")]


class Guardian(nn.Module):
    def __init__(self, vocab_size: int, hidden: int, num_labels: int):
        super().__init__()
        self.encoder = BertModel(BertConfig(vocab_size=vocab_size))
        self.lstm = nn.LSTM(768, hidden, batch_first=True, bidirectional=True)
        self.classifier = nn.Linear(hidden * 2, num_labels)

    def forward(self, input_ids, attention_mask):
        seq = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        out, (h, _) = self.lstm(seq)
        if POOLING == "mean":
            mask = attention_mask.unsqueeze(-1).float()
            x = (out * mask).sum(1) / mask.sum(1).clamp(min=1)
        elif POOLING == "first":
            x = out[:, 0]
        else:
            x = torch.cat([h[-2], h[-1]], dim=1)
        return self.classifier(x)


state = {"model": None, "tokenizer": None, "error": None}
app = FastAPI(title="GUARDIAN API")


def find(name: str) -> Path | None:
    for base in (BUILD_DIR, RUNTIME_DIR):
        if (base / name).exists():
            return base / name
    return None


def load():
    try:
        tok_dir = find("tokenizer/vocab.txt")
        tok_dir = tok_dir.parent if tok_dir else download_tokenizer(RUNTIME_DIR)
        weights = find("best_weights.pt") or download_weights(RUNTIME_DIR)
        sd = torch.load(weights, map_location="cpu", weights_only=True)
        sd = sd.get("state_dict", sd.get("model_state_dict", sd))
        # Pooler BERT tidak dipakai jalur BiLSTM, tapi ikut tersimpan; muat apa adanya.
        model = Guardian(
            vocab_size=sd["encoder.embeddings.word_embeddings.weight"].shape[0],
            hidden=sd["lstm.weight_hh_l0"].shape[1],
            num_labels=sd["classifier.weight"].shape[0],
        )
        model.load_state_dict(sd, strict=False)
        missing, unexpected = [k for k in model.state_dict() if k not in sd], [k for k in sd if k not in model.state_dict()]
        if any(not k.endswith("position_ids") for k in missing + unexpected):
            raise ValueError(f"state_dict tidak cocok: hilang={missing[:5]} lebih={unexpected[:5]}")
        model.eval()
        state["tokenizer"] = BertTokenizerFast(str(tok_dir / "vocab.txt"), do_lower_case=True)
        state["model"] = model
        print("Model GUARDIAN dimuat", flush=True)
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        print(f"Model gagal dimuat: {state['error']}", flush=True)


@app.on_event("startup")
def startup():
    # Dimuat di thread lain supaya server langsung menjawab /health selama unduh/muat model.
    threading.Thread(target=load, daemon=True).start()


def predict_text(text: str):
    if state["model"] is None:
        raise HTTPException(503, state["error"] or "Model masih dimuat")
    enc = state["tokenizer"](text, truncation=True, max_length=MAX_LEN, return_tensors="pt")
    with torch.inference_mode():
        logits = state["model"](enc["input_ids"], enc["attention_mask"])[0]
    probs = torch.softmax(logits, dim=0).tolist()
    labels = LABELS if len(LABELS) == len(probs) else [f"kelas_{i}" for i in range(len(probs))]
    best = max(range(len(probs)), key=probs.__getitem__)
    return {"label": labels[best], "scores": {labels[i]: round(p, 4) for i, p in enumerate(probs)}}


class PredictIn(BaseModel):
    text: str


@app.get("/")
def index():
    return {"app": "GUARDIAN API", "endpoints": ["/health", "/predict?text=..."]}


@app.get("/health")
def health():
    # Selalu 200 selama server hidup; status model dilaporkan di isi jawaban.
    return {"status": "ok", "model_loaded": state["model"] is not None, "error": state["error"]}


@app.get("/predict")
def predict_get(text: str = "kamu bodoh sekali"):
    return predict_text(text)


@app.post("/predict")
def predict_post(body: PredictIn):
    return predict_text(body.text)
