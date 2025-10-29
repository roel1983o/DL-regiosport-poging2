# app/processors/pipeline_b.py
from __future__ import annotations
import os, pathlib, shutil, subprocess, tempfile, textwrap, glob
from typing import Dict, Any

VERSION = "pipeline_b-notebook-subproc-runner-2025-10-30"

RUNNER_CODE = r"""
import os, sys, nbformat
from nbclient import NotebookClient

if __name__ == "__main__":
    nb_path = sys.argv[1]
    exec_out = sys.argv[2]
    # Door de parent (onze webapp) gezet:
    #   - CWD = tijdelijke map
    #   - env['INPUT_XLSX'] = pad naar upload
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    client = NotebookClient(nb, timeout=600, kernel_name="python3", allow_errors=False)
    client.execute()
    with open(exec_out, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
"""

def process(input_xlsx_path: str, options: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Draait het originele notebook DL_amateursport_overig.ipynb in een apart Python-subprocess
    (met nbclient, maar niet via 'python -m nbclient'). Zo krijgen we weer jouw exacte CUE-output.
    """
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = options.get("out_name") or "cue_overig.txt"
    out_path = out_dir / out_name

    base_dir = pathlib.Path(__file__).resolve().parent.parent  # app/
    nb_path = base_dir / "notebooks" / "DL_amateursport_overig.ipynb"
    if not nb_path.exists():
        raise FileNotFoundError(f"Notebook niet gevonden: {nb_path}. Plaats het in app/notebooks/")

    # Draai alles in een tijdelijke werkmap, zodat relatieve paden/uitvoer netjes bij elkaar staan
    with tempfile.TemporaryDirectory(prefix="nb_run_overig_") as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # Schrijf een mini-runner die nbclient programmatic aanroept
        runner_py = tmp / "runner.py"
        runner_py.write_text(RUNNER_CODE, encoding="utf-8")

        # Zorg dat het Excelpad beschikbaar is voor het notebook (zoals voorheen)
        env = os.environ.copy()
        env["INPUT_XLSX"] = str(input_xlsx_path)

        # Voer het runner-script uit
        exec_out = tmp / "executed.ipynb"
        cmd = [sys_executable(), str(runner_py), str(nb_path), str(exec_out)]
        result = subprocess.run(
            cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=900
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Notebook uitvoer mislukt:\n"
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        # Zoek de .txt(s) die het notebook heeft gemaakt
        txt_files = list(tmp.rglob("*.txt"))
        if not txt_files:
            # Toon debuginformatie als het notebook wel draaide maar niks schreef
            raise RuntimeError(
                "Notebook draaide, maar er is geen .txt-output gevonden in de tijdelijke map."
            )

        # voorkeur: bestand met 'opmaakscript' in de naam
        target = next((p for p in txt_files if "opmaakscript" in p.name.lower()), txt_files[0])
        shutil.copyfile(target, out_path)

    # Lees voor preview
    try:
        with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
            text_output = f.read()
    except Exception:
        text_output = "(Bestand gemaakt, maar preview kon niet worden gelezen.)"

    return {
        "text_output": text_output,
        "attachments": [{"name": out_name, "path": str(out_path)}],
    }

def sys_executable() -> str:
    """
    Retourneert het huidige Python-executable pad (compatibel met Render/venv).
    """
    import sys
    return sys.executable
