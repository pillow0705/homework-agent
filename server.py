#!/usr/bin/env python3
"""
Homework Agent Server
Receives homework files, uses LLM to generate human-like answers in LaTeX format.
Port: 5500
"""

import os
import re
import uuid
import subprocess
import tempfile
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, request, send_file, jsonify
import anthropic
import pdfplumber
import docx

app = Flask(__name__)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "homework_agent"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------------------------------------------------------------------------
# File parsers
# ---------------------------------------------------------------------------

def parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_pdf(path: Path) -> str:
    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
    return "\n\n".join(texts)


def parse_docx(path: Path) -> str:
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


PARSERS = {
    ".txt": parse_txt,
    ".md": parse_md,
    ".markdown": parse_md,
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".doc": parse_docx,
}


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    parser = PARSERS.get(suffix)
    if parser is None:
        # Fallback: try reading as plain text
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return f"[Unsupported file type: {suffix}]"
    return parser(path)


# ---------------------------------------------------------------------------
# LLM: generate LaTeX answer
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a diligent university student completing homework assignments.
Your task:
1. Read the provided homework questions carefully.
2. Write complete, thoughtful answers — not too verbose, not too brief. Aim for the depth a well-prepared student would produce.
3. Output ONLY a complete, compilable LaTeX document (article class). Do NOT add any markdown fences or explanations outside the LaTeX source.
4. Use \\documentclass{article} with standard packages. Include \\usepackage{amsmath,amssymb,geometry,hyperref,enumitem,graphicx}.
5. Set geometry: margin=1in.
6. Write in the same language as the homework (Chinese questions → Chinese answers; English → English).
7. Structure: title/author section, then answer each question clearly with appropriate section headers.
8. Show work for math problems (derivations, not just final answers).
9. Cite no external sources unless the question requires it.
10. Author name: Student"""

def generate_latex(content: str, filenames: list[str]) -> str:
    file_list = ", ".join(filenames)
    user_msg = f"Homework files: {file_list}\n\n---\n\n{content}"

    message = ANTHROPIC_CLIENT.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": user_msg}],
        system=SYSTEM_PROMPT,
    )
    raw = message.content[0].text.strip()

    # Strip markdown code fences if the model wrapped the output
    raw = re.sub(r"^```(?:latex|tex)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# LaTeX → PDF compilation
# ---------------------------------------------------------------------------

def compile_latex(tex_source: str, work_dir: Path) -> Path:
    tex_path = work_dir / "answer.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(work_dir), str(tex_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Run twice for cross-references
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(work_dir), str(tex_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    pdf_path = work_dir / "answer.pdf"
    if not pdf_path.exists():
        log = (work_dir / "answer.log").read_text(errors="replace") if (work_dir / "answer.log").exists() else result.stderr
        raise RuntimeError(f"LaTeX compilation failed:\n{log[-3000:]}")
    return pdf_path


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "homework-agent"})


@app.route("/homework", methods=["POST"])
def homework():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded. Use field name 'files'."}), 400

    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "Empty file list."}), 400

    fmt = request.form.get("format", "pdf").lower()  # "pdf" or "tex"
    job_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True)

    try:
        # Save and parse files
        all_text_parts = []
        filenames = []
        for f in uploaded:
            filename = Path(f.filename).name
            save_path = job_dir / filename
            f.save(save_path)
            filenames.append(filename)
            text = extract_text(save_path)
            all_text_parts.append(f"=== {filename} ===\n{text}")

        combined_content = "\n\n".join(all_text_parts)

        # Generate LaTeX via LLM
        latex_source = generate_latex(combined_content, filenames)

        if fmt == "tex":
            tex_path = job_dir / "answer.tex"
            tex_path.write_text(latex_source, encoding="utf-8")
            return send_file(
                str(tex_path),
                as_attachment=True,
                download_name="answer.tex",
                mimetype="text/plain",
            )

        # Compile to PDF
        pdf_path = compile_latex(latex_source, job_dir)
        return send_file(
            str(pdf_path),
            as_attachment=True,
            download_name="answer.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up after response is sent
        # (Flask sends file before cleanup since we use send_file path)
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("HOMEWORK_PORT", 5500))
    print(f"[homework-agent] Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
