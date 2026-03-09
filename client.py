#!/usr/bin/env python3
"""
Homework Agent Client
Scans current directory, lets you pick files, uploads to server, saves result.

Usage:
    python3 client.py [--server http://HOST:5500] [--format pdf|tex] [--out OUTPUT_PATH]
"""

import argparse
import os
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------

SUPPORTED_EXTS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".doc"}

DEFAULT_SERVER = os.environ.get("HOMEWORK_SERVER", "http://127.0.0.1:5500")


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def scan_files(directory: Path) -> list[Path]:
    """Return all supported files in directory (non-recursive)."""
    files = []
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            files.append(p)
    return files


def prompt_selection(files: list[Path]) -> list[Path]:
    """Interactive file selector. Returns chosen files."""
    if not files:
        print("No supported files found in current directory.")
        print(f"Supported types: {', '.join(sorted(SUPPORTED_EXTS))}")
        sys.exit(0)

    print("\nFound the following files:\n")
    for i, f in enumerate(files, 1):
        size_kb = f.stat().st_size / 1024
        print(f"  [{i:2d}] {f.name}  ({size_kb:.1f} KB)")

    print("\nEnter file numbers to upload (e.g. 1 3 4), or 'all', or 'q' to quit:")
    while True:
        raw = input("> ").strip()
        if raw.lower() == "q":
            print("Cancelled.")
            sys.exit(0)
        if raw.lower() == "all":
            return files
        try:
            indices = [int(x) for x in raw.split()]
            chosen = []
            for idx in indices:
                if 1 <= idx <= len(files):
                    chosen.append(files[idx - 1])
                else:
                    print(f"  Invalid index: {idx}  (valid: 1–{len(files)})")
                    chosen = []
                    break
            if chosen:
                return chosen
        except ValueError:
            print("  Please enter numbers separated by spaces, 'all', or 'q'.")


# ---------------------------------------------------------------------------
# Upload & receive
# ---------------------------------------------------------------------------

def upload(files: list[Path], server: str, fmt: str, out_path: Path) -> None:
    url = f"{server.rstrip('/')}/homework"
    file_handles = []
    try:
        for f in files:
            file_handles.append(("files", (f.name, open(f, "rb"))))

        print(f"\nUploading {len(files)} file(s) to {url} ...")
        resp = requests.post(
            url,
            files=file_handles,
            data={"format": fmt},
            timeout=180,  # LLM + LaTeX can take a while
        )
    finally:
        for _, (_, fh) in file_handles:
            fh.close()

    if resp.status_code != 200:
        try:
            err = resp.json().get("error", resp.text)
        except Exception:
            err = resp.text
        print(f"\nServer error ({resp.status_code}): {err}")
        sys.exit(1)

    out_path.write_bytes(resp.content)
    print(f"\nDone! Answer saved to: {out_path.resolve()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Homework Agent Client")
    parser.add_argument("--server", default=DEFAULT_SERVER,
                        help=f"Server URL (default: {DEFAULT_SERVER}, or set HOMEWORK_SERVER env)")
    parser.add_argument("--format", choices=["pdf", "tex"], default="pdf",
                        help="Output format: pdf (default) or tex source")
    parser.add_argument("--out", default=None,
                        help="Output file path (default: answer.pdf or answer.tex in current dir)")
    args = parser.parse_args()

    cwd = Path.cwd()
    files = scan_files(cwd)
    chosen = prompt_selection(files)

    ext = f".{args.format}"
    out_path = Path(args.out) if args.out else cwd / f"answer{ext}"

    # Health check
    try:
        health = requests.get(f"{args.server.rstrip('/')}/health", timeout=5)
        health.raise_for_status()
    except Exception as e:
        print(f"Cannot reach server at {args.server}: {e}")
        sys.exit(1)

    upload(chosen, args.server, args.format, out_path)


if __name__ == "__main__":
    main()
