# app/processors/pipeline_b.py
from __future__ import annotations
import os, pathlib, shutil, subprocess, tempfile
from typing import Dict, Any

VERSION = "pipeline_b-notebook-subproc-2025-10-30"

def process(input_xlsx_path: str, options: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Draait DL_amateursport_overig.ipynb via een apart subprocess
    zodat nbclient geen threadingproblemen veroorzaakt.
    """
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = options.get("out_name") or "cue_overig.txt"
    out_path = out_dir / out_name

    base_dir = pathlib.Path(__file__).resolve().parent.parent
    nb_path = base_dir / "notebooks" / "DL_amateursport_overig.ipynb"
    if not nb_path.exists():
        raise FileNotFoundError(f"Notebook niet gevonden op {nb_path}")

    with tempfile.TemporaryDirectory(prefix="nb_run_overig_") as tmpdir:
        tmp = pathlib.Path(tmpdir)
        env = os.environ.copy()
        env["INPUT_XLSX"] = str(input_xlsx_path)

        cmd = [
            "python",
            "-m",
            "nbclient",
            "--execute",
            str(nb_path),
            "--to",
            "notebook",
            "--output",
            str(tmp / "executed.ipynb"),
        ]

        result = subprocess.run(
            cmd,
            cwd=tmp,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Notebook uitvoer mislukt:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        # zoek het gegenereerde txt-bestand
        txt_files = list(tmp.rglob("*.txt"))
        if not txt_files:
            raise RuntimeError(
                f"Notebook draaide maar geen .txt gevonden.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        # voorkeur: bestand met 'opmaakscript' in naam
        target = next((f for f in txt_files if "opmaakscript" in f.name.lower()), txt_files[0])
        shutil.copyfile(target, out_path)

    with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
        text_output = f.read()

    return {
        "text_output": text_output,
        "attachments": [{"name": out_name, "path": str(out_path)}],
    }
