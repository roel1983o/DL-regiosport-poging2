# app/processors/pipeline_b.py
from __future__ import annotations
import os, sys, json, pathlib, shutil, subprocess, tempfile
from typing import Dict, Any

VERSION = "pipeline_b-notebook-exec-2025-10-30"

# De runner voert een .ipynb uit door alle code-cellen te "exec'en" (geen Jupyter-kernel nodig).
RUNNER_CODE = r"""
import os, sys, json, types, io
from pathlib import Path

def run_notebook(ipynb_path: str):
    with open(ipynb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    # Verzamel code uit alle code-cellen in volgorde
    code_pieces = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            code_pieces.append(src)

    code_all = "\n\n# --- cell separator ---\n\n".join(code_pieces)

    # Voer uit in een schone module-namespace
    mod = types.ModuleType("__nbexec__")
    # Geef env-variabele INPUT_XLSX door aan deze namespace (optioneel)
    mod.INPUT_XLSX = os.environ.get("INPUT_XLSX", "")
    # Zet een current working directory op de temp-map (is al zo, maar expliciet is netjes)
    mod.__dict__["__name__"] = "__nbexec__"

    compiled = compile(code_all, filename=str(ipynb_path), mode="exec")
    exec(compiled, mod.__dict__)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: runner.py <notebook.ipynb>", file=sys.stderr)
        sys.exit(2)
    run_notebook(sys.argv[1])
"""

def _python_exe() -> str:
    # Render gebruikt een venv; sys.executable wijst naar de juiste interpreter
    return sys.executable

def process(input_xlsx_path: str, options: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Draait het originele notebook DL_amateursport_overig.ipynb door code-cellen te executen
    in een los Python-subprocess (zonder Jupyter kernel). Zo krijg je dezelfde CUE-output.
    """
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = options.get("out_name") or "cue_overig.txt"
    out_path = out_dir / out_name

    base_dir = pathlib.Path(__file__).resolve().parent.parent  # app/
    nb_path = base_dir / "notebooks" / "DL_amateursport_overig.ipynb"
    if not nb_path.exists():
        raise FileNotFoundError(f"Notebook niet gevonden: {nb_path}. Plaats het in app/notebooks/")

    # Draai in een tijdelijke map; het notebook schrijft hier z'n .txt naartoe
    with tempfile.TemporaryDirectory(prefix="nb_exec_overig_") as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # Runner-script wegschrijven
        runner_py = tmp / "runner.py"
        runner_py.write_text(RUNNER_CODE, encoding="utf-8")

        # Omgeving meegeven aan notebook-code
        env = os.environ.copy()
        env["INPUT_XLSX"] = str(input_xlsx_path)
        # Eventueel extra envs toevoegen als je notebook die verwacht:
        # env["OUTPUT_DIR"] = str(tmp)  # als je notebook dat gebruikt

        # Voer runner uit
        cmd = [_python_exe(), str(runner_py), str(nb_path)]
        result = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=900)

        if result.returncode != 0:
            raise RuntimeError(
                "Notebook uitvoer mislukt:\n"
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        # Zoek de .txt die het notebook produceert
        txt_files = list(tmp.rglob("*.txt"))
        if not txt_files:
            # Geen txt gevonden? Geef debughulp terug.
            raise RuntimeError(
                "Notebook draaide, maar er is geen .txt-output gevonden in de tijdelijke map.\n"
                "Controleer in het notebook waar het outputbestand wordt weggeschreven.\n"
                f"Temp map: {tmp}"
            )

        # Kies bij voorkeur een bestand met 'opmaakscript' in de naam, anders de eerste
        target = next((p for p in txt_files if "opmaakscript" in p.name.lower()), txt_files[0])
        shutil.copyfile(target, out_path)

    # Preview lezen
    try:
        with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
            text_output = f.read()
    except Exception:
        text_output = "(Bestand gemaakt, maar preview kon niet worden gelezen.)"

    return {
        "text_output": text_output,
        "attachments": [{"name": out_name, "path": str(out_path)}],
    }
