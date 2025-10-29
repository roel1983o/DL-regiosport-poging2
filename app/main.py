from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, uuid, pathlib, json
from app.processors import pipeline_a, pipeline_b
from app.utils.nb_runner import run_notebook_blackbox

# Configure paths
BASE_DIR = pathlib.Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / ".." / "uploads"
OUTPUT_DIR = BASE_DIR / ".." / "outputs"
for p in (UPLOAD_DIR, OUTPUT_DIR):
    p.mkdir(parents=True, exist_ok=True)

NB_A_PATH = BASE_DIR / "notebooks" / "pipeline_a.ipynb"
NB_B_PATH = BASE_DIR / "notebooks" / "pipeline_b.ipynb"

app = FastAPI(title="DL regiosport codefixer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process")
async def process(
    request: Request,
    pipeline: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    extra_options: str = Form(""),
    file: UploadFile = File(...),
):
    # Save upload
    job_id = str(uuid.uuid4())[:8]
    this_upload_dir = UPLOAD_DIR / job_id
    this_output_dir = OUTPUT_DIR / job_id
    this_upload_dir.mkdir(parents=True, exist_ok=True)
    this_output_dir.mkdir(parents=True, exist_ok=True)

    input_xlsx_path = this_upload_dir / (file.filename or f"input.xlsx")
    with open(input_xlsx_path, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)

    # Parse options
    opts = {
        "competition": competition,
        "match_date": match_date,
    }
    if extra_options.strip():
        try:
            extra = json.loads(extra_options)
            if isinstance(extra, dict):
                opts.update(extra)
        except Exception:
            pass

    # Choose processing mode
    mode = os.environ.get("NB_RUN_MODE", "python")  # "python" or "notebook"
    try:
        if pipeline == "A":
            if mode == "notebook" and NB_A_PATH.exists():
                result = run_notebook_blackbox(str(NB_A_PATH), str(input_xlsx_path), str(this_output_dir))
            else:
                result = pipeline_a.process(str(input_xlsx_path), opts, str(this_output_dir))
        elif pipeline == "B":
            if mode == "notebook" and NB_B_PATH.exists():
                result = run_notebook_blackbox(str(NB_B_PATH), str(input_xlsx_path), str(this_output_dir))
            else:
                result = pipeline_b.process(str(input_xlsx_path), opts, str(this_output_dir))
        else:
            return JSONResponse({"error": "Unknown pipeline"}, status_code=400)
    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": f"Er ging iets mis: {e}",
            },
            status_code=500,
        )

    # Collect attachments present on disk
    attachments = result.get("attachments", [])
    files = []
    for att in attachments:
        p = pathlib.Path(att.get("path", ""))
        if p.exists():
            files.append({
                "name": att.get("name") or p.name,
                "url": f"/download/{job_id}/{p.name}"
            })

    preview = (result.get("text_output") or "")[:20000]  # safety cap
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
    path = OUTPUT_DIR / job_id / filename
    if not path.exists():
        return JSONResponse({"error": "Bestand niet gevonden"}, status_code=404)
    return FileResponse(str(path), filename=filename)

@app.get("/template/{kind}")
async def download_template(kind: str):
    fname_map = {
        "voetbal": "Invulbestand_amateursport_voetbal.xlsx",
        "overig": "Invulbestand_amateursport_overig.xlsx",
    }
    fname = fname_map.get(kind)
    if not fname:
        return JSONResponse({"error": "Onbekend template"}, status_code=404)
    path = BASE_DIR / "static" / "templates" / fname
    if not path.exists():
        return JSONResponse({"error": "Template niet gevonden"}, status_code=404)
    return FileResponse(str(path), filename=fname)
