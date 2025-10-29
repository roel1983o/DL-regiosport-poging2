# app/main.py
from __future__ import annotations

import json
import os
import pathlib
import shutil
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---- Processors (Optie 1: Python-modules) ----
from app.processors import pipeline_a, pipeline_b

# ---- (Optioneel) Notebook-runner beschikbaar houden ----
# from app.utils.nb_runner import run_notebook_blackbox


# === Padconfiguratie ===
BASE_DIR = pathlib.Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
OUTPUT_DIR = ROOT_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
NOTEBOOKS_DIR = BASE_DIR / "notebooks"  # alleen nodig als je alsnog notebooks wilt draaien

for p in (UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATE_DIR):
    p.mkdir(parents=True, exist_ok=True)

# Indien je lege invulbestanden onder /app/static/templates/ bewaart,
# kun je daar direct naar linken vanuit de UI:
#   /static/templates/Invulbestand_amateursport_voetbal.xlsx
#   /static/templates/Invulbestand_amateursport_overig.xlsx


# === FastAPI-app ===
# max_request_size helpt tegen "stil" afgebroken uploads; pas aan naar wens.
app = FastAPI(title="Sportuitslagen App", max_request_size=25 * 1024 * 1024)

# CORS (vrij zetten is handig bij testen of embedden)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# === Routes ===
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Render de UI (twee losse formulieren: voetbal & overig).
    De HTML staat in app/templates/index.html.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
async def process(
    request: Request,
    # Welke pipeline? "A" = voetbal, "B" = overig
    pipeline: str = Form(...),

    # Optionele velden (niet verplicht voor jouw UI, maar handig als je wilt uitbreiden)
    competition: Optional[str] = Form(None),
    match_date: Optional[str] = Form(None),
    extra_options: Optional[str] = Form(None),

    # === BELANGRIJK: drie mogelijke file-velden ===
    # - file_voetbal → formulier 1 (voetbal)
    # - file_overig  → formulier 2 (overig)
    # - file         → fallback (oude naam; blijft werken)
    file: UploadFile | None = File(None),
    file_voetbal: UploadFile | None = File(None),
    file_overig: UploadFile | None = File(None),
):
    """
    Verwerkt het geüploade Excel-bestand met de gekozen pipeline.
    Ondersteunt drie bestandsveld-namen zodat Edge/Chrome geen conflict geeft
    wanneer er twee file inputs op dezelfde pagina staan.
    """
    # Kies het daadwerkelijk geüploade bestand, ongeacht welk formulier gebruikt is.
    uploaded = file_voetbal or file_overig or file
    if uploaded is None:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": "Geen bestand ontvangen."},
            status_code=400,
        )

    # Maak job-specifieke upload/output mappen
    job_id = str(uuid.uuid4())[:8]
    this_upload_dir = UPLOAD_DIR / job_id
    this_output_dir = OUTPUT_DIR / job_id
    this_upload_dir.mkdir(parents=True, exist_ok=True)
    this_output_dir.mkdir(parents=True, exist_ok=True)

    # Sla de upload op
    safe_name = uploaded.filename or "input.xlsx"
    input_xlsx_path = this_upload_dir / safe_name
    with open(input_xlsx_path, "wb") as f_out:
        shutil.copyfileobj(uploaded.file, f_out)

    # Bouw options-dict
    opts = {}
    if competition:
        opts["competition"] = competition
    if match_date:
        opts["match_date"] = match_date
    if extra_options:
        try:
            extra = json.loads(extra_options)
            if isinstance(extra, dict):
                opts.update(extra)
        except Exception:
            # Als de JSON niet klopt, negeren we 'm stil; UI blijft schoon.
            pass

    # Verwerkingsmodus (standaard Optie 1: Python-processors)
    # Je kunt "NB_RUN_MODE=notebook" zetten als je per se een .ipynb wil draaien.
    mode = os.environ.get("NB_RUN_MODE", "python").lower()

    try:
        # ---- Pipeline A: voetbal ----
        if pipeline == "A":
            if mode == "python":
                result = pipeline_a.process(str(input_xlsx_path), opts, str(this_output_dir))
            else:
                # (optioneel) notebook-variant:
                nb_path = NOTEBOOKS_DIR / "pipeline_a.ipynb"
                if not nb_path.exists():
                    raise RuntimeError("Notebook voor pipeline A niet gevonden.")
                from app.utils.nb_runner import run_notebook_blackbox
                result = run_notebook_blackbox(str(nb_path), str(input_xlsx_path), str(this_output_dir))

        # ---- Pipeline B: overig ----
        elif pipeline == "B":
            if mode == "python":
                result = pipeline_b.process(str(input_xlsx_path), opts, str(this_output_dir))
            else:
                nb_path = NOTEBOOKS_DIR / "pipeline_b.ipynb"
                if not nb_path.exists():
                    raise RuntimeError("Notebook voor pipeline B niet gevonden.")
                from app.utils.nb_runner import run_notebook_blackbox
                result = run_notebook_blackbox(str(nb_path), str(input_xlsx_path), str(this_output_dir))

        else:
            return JSONResponse({"error": "Onbekende pipeline."}, status_code=400)

    except Exception as e:
        # Toon nette foutmelding in de UI
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"Er ging iets mis: {e}"},
            status_code=500,
        )

    # Verwerk resultaat → verzamel downloads
    attachments = result.get("attachments", []) or []
    files = []
    for att in attachments:
        p = pathlib.Path(att.get("path", ""))
        if p.exists():
            files.append(
                {
                    "name": att.get("name") or p.name,
                    "url": f"/download/{job_id}/{p.name}",
                }
            )

    preview = (result.get("text_output") or "")[:20000]  # cap voor veiligheid/UX

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "preview": preview,
            "job_id": job_id,
            "files": files,
            "ok": True,
        },
    )


@app.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    """
    Download endpoint voor gegenereerde bestanden.
    """
    path = OUTPUT_DIR / job_id / filename
    if not path.exists():
        return JSONResponse({"error": "Bestand niet gevonden."}, status_code=404)
    return FileResponse(str(path), filename=filename)
