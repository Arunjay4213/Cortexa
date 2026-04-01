"""
Download pre-exported DeBERTa-v3-base NLI ONNX model from HuggingFace.

Usage:
    python scripts/download_model.py

Downloads:
  - onnx/model.onnx (base ONNX model)
  - tokenizer.json (HuggingFace fast tokenizer)

No torch or transformers needed — uses pre-exported ONNX from HuggingFace Hub.
"""

import os
import urllib.request
from pathlib import Path

REPO = "cross-encoder/nli-deberta-v3-base"
HF_BASE = f"https://huggingface.co/{REPO}/resolve/main"

FILES = {
    "model.onnx": f"{HF_BASE}/onnx/model.onnx",
    "tokenizer.json": f"{HF_BASE}/tokenizer.json",
}


def download_file(url: str, dest: Path):
    """Download a file with progress reporting."""
    print(f"  Downloading {url}")
    print(f"    -> {dest}")
    urllib.request.urlretrieve(url, str(dest))
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"    Done ({size_mb:.1f} MB)")


def main():
    output_dir = Path("models/deberta-v3-base-nli")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading pre-exported ONNX model from {REPO}...")
    for filename, url in FILES.items():
        dest = output_dir / filename
        if dest.exists():
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  {filename} already exists ({size_mb:.1f} MB), skipping")
            continue
        download_file(url, dest)

    # Verify files exist
    for filename in FILES:
        path = output_dir / filename
        assert path.exists(), f"Missing {path}"

    print(f"\nModel ready at {output_dir}/")
    for f in sorted(output_dir.iterdir()):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name}: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
