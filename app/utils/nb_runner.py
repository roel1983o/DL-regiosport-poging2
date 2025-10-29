import os, tempfile, nbformat, pathlib
from nbclient import NotebookClient

def run_notebook_blackbox(nb_path: str, input_xlsx: str, output_dir: str, exec_timeout_s: int = 300):
    """Voert een notebook uit als blackbox.
    Het notebook moet zelf `os.environ['INPUT_XLSX']` en `os.environ['OUTPUT_DIR']` lezen
    en bestanden wegschrijven in `OUTPUT_DIR` (bijv. 'codes.txt').

    Retourneert een dict in hetzelfde formaat als de Python-processors.
    """
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    os.environ["INPUT_XLSX"] = input_xlsx
    os.environ["OUTPUT_DIR"] = output_dir

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    client = NotebookClient(nb, timeout=exec_timeout_s, kernel_name="python3", allow_errors=False)
    client.execute()

    # verzamel bekende outputs
    attachments = []
    for name in ("codes.txt", "codes_pipeline_a.txt", "codes_pipeline_b.txt", "output.txt"):
        p = pathlib.Path(output_dir) / name
        if p.exists():
            attachments.append({"name": p.name, "path": str(p)})

    text_output = ""
    if attachments:
        # lees de eerste als preview
        try:
            with open(attachments[0]["path"], "r", encoding="utf-8") as f:
                text_output = f.read()
        except Exception:
            text_output = "(Kan preview niet lezen, maar bestanden zijn geproduceerd.)"

    return {"text_output": text_output, "attachments": attachments}
