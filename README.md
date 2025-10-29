# Sportuitslagen webapp (FastAPI + Render)

Een simpele webapp om Excel-bestanden te verwerken naar opmaakcodes voor de krant.
De UI bedient twee pipelines (A & B). Je kunt jouw bestaande Colab-notebooks integreren
door ze om te zetten naar Python-functies **of** ze rechtstreeks uit te voeren.

## Snelle start (lokaal)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open vervolgens http://127.0.0.1:8000

## Deploy op Render

1. Push dit project naar een nieuwe GitHub-repo.
2. Ga naar Render.com → New → Web Service → link jouw repo.
3. Render gebruikt `render.yaml` automatisch. Zo niet, zet:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Deployen en klaar.

## Jouw notebooks integreren

### Optie 1: Snel en robuust (aanrader)
Zet jouw notebook om naar een `.py` en maak een `process()` functie.

In `app/processors/pipeline_a.py` en `pipeline_b.py` staan voorbeelden.
Plak de door ChatGPT/Colab gegenereerde logica daar in en zorg dat er een
functie is met signatuur:

```python
def process(input_xlsx_path: str, options: dict) -> dict:
    # return {"text_output": "...", "attachments": [{"name": "codes.txt", "path": "/abs/path/to/codes.txt"}]}
```

> Tip: In Colab kun je je notebook downloaden als `.py` (bestandsinhoud kopiëren)
> of via `jupyter nbconvert --to script mynotebook.ipynb`.

### Optie 2: Notebook-als-blackbox draaien
Plaats de `.ipynb` in `app/notebooks/` en gebruik `NB_RUN_MODE=notebook`
(omgevingvariabele). De runner zet `INPUT_XLSX` en `OUTPUT_DIR` als env vars
en voert het notebook uit met `nbclient`. Jouw notebook moet die env vars lezen
en zelf een `codes.txt` (of andere bestanden) schrijven in `OUTPUT_DIR`.

Voorbeeld (in jouw notebook):

```python
import os, pandas as pd
input_xlsx = os.environ["INPUT_XLSX"]
output_dir = os.environ["OUTPUT_DIR"]
df = pd.read_excel(input_xlsx)
# ... doe je ding ...
with open(os.path.join(output_dir, "codes.txt"), "w", encoding="utf-8") as f:
    f.write("...gegenereerde codes...")
```

Configureer welk notebook hoort bij pipeline A/B in `app/main.py` (variabelen `NB_A_PATH`/`NB_B_PATH`).

## UI (globaal)
- Upload Excel
- Kies pipeline A of B
- (optioneel) invoervelden (competitie, datum, format e.d.)
- Klik "Verwerk"
- Preview + download van outputbestanden, plus Copy-knop

## Bestanden die je wilt aanpassen
- `app/processors/pipeline_a.py` en `pipeline_b.py`
- `app/templates/index.html` (UI lay-out)
- `app/main.py` (keuze: Python processor of notebook-runner)

## Troubleshooting
- Render logging zie je in het dashboard (stdout).
- Grote Excel? Verhoog body-size limiet in `app/main.py` (Starlette config).
- Notebook-tijdslimieten? Pas `exec_timeout_s` in `app/utils/nb_runner.py` aan.
