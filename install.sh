#!/bin/sh
# Perintah install untuk template Python platform (isi kolom "Perintah install": sh install.sh).
# torch versi CPU diambil dari index PyTorch supaya image tidak membawa CUDA (beberapa GB).
set -e
# PyPI tetap jadi indeks cadangan untuk dependensi torch yang tidak ada di index CPU.
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
pip install --no-cache-dir -r requirements.txt
python download_model.py model
