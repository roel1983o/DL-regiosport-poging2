# app/processors/pipeline_b.py
from __future__ import annotations
from typing import Dict, Any, List
import os, pathlib, tempfile, shutil, glob
import nbformat
from nbclient import NotebookClient

VERSION = "pipeline_b-notebook-bridge-1"

def _run_notebook(nb_path: str, input_xlsx: str, workdir: str, exec_timeout_s: int = 600) -> str:
    """
    Voert het .ipynb uit in een tijdelijke werkmap.
    We zetten de CWD naar die map en geven INPUT_XLSX via env mee.
    Retourneert het pad naar het belangrijkste .txt-bestand dat het notebook produceerde.
    """
    # Zorg dat werkmap bestaat en wordt gebruikt als CWD
    cwd_before = os.getcwd()
    os.makedirs(workdir, exist_ok=True)
    os.chdir(workdir)

    # Zet env variabelen die jouw notebook (indien gewenst) zou kunnen lezen
    os.environ["INPUT_XLSX"] = input_xlsx

    try:
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)

        client = NotebookClient(
            nb,
            timeout=exec_timeout_s,
            kernel_name="python3",
            allow_errors=False
        )
        client.execute()

        # Zoek het door het notebook weggeschreven .txt bestand
        # (het heette eerder vaak 'opmaakscript_V27_sorted_ijrule.txt';
        #  we pakken het meest waarschijnlijke .txt-bestand)
        candidates = []
        for pat in ("*.txt", "**/*.txt"):
            candidates.extend(glob.glob(pat, recursive=True))
        # kies voorkeur op naam 'opmaakscript' als aanwezig
        preferred = [p for p in candidates if "opmaakscript" in pathlib.Path(p).name.lower()]
        target = (preferred[0] if preferred else (candidates[0] if candidates else None))
        if not target:
            raise RuntimeError("Notebook draaide, maar ik vond geen .txt-output.")

        return os.path.abspath(target)

    finally:
        # herstel CWD
        os.chdir(cwd_before)

def process(input_xlsx_path: str, options: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Bridge die jouw originele notebook 'DL_amateursport_overig.ipynb' 1:1 uitvoert.
    Output wordt hernoemd naar 'cue_overig.txt' voor de webapp.
    """
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = options.get("out_name") or "cue_overig.txt"
    out_path = out_dir / out_name

    # Pad naar jouw notebook in de repo (zet dit bestand in app/notebooks/)
    base_dir = pathlib.Path(__file__).resolve().parent.parent
    nb_path = base_dir / "notebooks" / "DL_amateursport_overig.ipynb"
    if not nb_path.exists():
        raise FileNotFoundError(
            f"Notebook niet gevonden op {nb_path}. "
            f"Zet jouw 'DL_amateursport_overig.ipynb' in 'app/notebooks/'."
        )

    # Draai notebook in een tempmap zodat relatieve paden daar terechtkomen
    with tempfile.TemporaryDirectory(prefix="nb_run_overig_") as tmp:
        produced_txt = _run_notebook(str(nb_path), str(input_xlsx_path), tmp)

        # Kopieer/hernomeer naar de app-outputmap
        shutil.copyfile(produced_txt, out_path)

    # Lees voor de preview
    try:
        with open(out_path, "r", encoding="utf-8") as f:
            text_output = f.read()
    except Exception:
        text_output = "(Bestand gemaakt, maar preview kon niet worden gelezen.)"

    return {
        "text_output": text_output,
        "attachments": [{"name": out_name, "path": str(out_path)}],
    }
