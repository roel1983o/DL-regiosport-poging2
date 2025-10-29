# app/processors/pipeline_b.py
from __future__ import annotations
from typing import Dict, Any, List
import os
import pathlib
import pandas as pd

def _first_nonempty_sheet(xlsx_path: str) -> pd.DataFrame:
    """Pak het eerste niet-lege werkblad als DataFrame."""
    try:
        # Lees alle sheets in 1x
        sheets = pd.read_excel(xlsx_path, sheet_name=None, engine="openpyxl")
    except Exception as e:
        raise RuntimeError(f"Kon Excel niet openen: {e}")

    if not sheets:
        raise RuntimeError("Het Excelbestand bevat geen bladen.")

    # Kies eerste niet-lege sheet (na trimming)
    for name, df in sheets.items():
        if isinstance(df, pd.DataFrame):
            df2 = _trim_df(df)
            if not df2.empty:
                return df2

    # Als alle bladen leeg lijken: geef het eerste blad intact terug voor diagnose
    first_name = next(iter(sheets))
    df_first = _trim_df(sheets[first_name])
    if df_first.empty:
        raise RuntimeError("Alle bladen lijken leeg of bevatten alleen lege rijen/kolommen.")
    return df_first


def _trim_df(df: pd.DataFrame) -> pd.DataFrame:
    """Verwijder volledig lege rijen/kolommen en reset index, zonder op vaste header-rij te vertrouwen."""
    # verwijder rijen/kolommen die volledig leeg zijn
    df2 = df.copy()
    df2 = df2.dropna(how="all").dropna(axis=1, how="all")
    # Als er geen kolomnamen zijn (of numeriek), laat ze zo; we itereren gewoon cellen
    df2 = df2.reset_index(drop=True)
    return df2


def _guess_teams_and_score(row: pd.Series) -> str:
    """Maak een nette regel van een willekeurige rij."""
    # Probeer veelvoorkomende kolomnamen te herkennen (hoofdletterongevoelig)
    lower_map = {str(k).strip().lower(): k for k in row.index}

    def pick(*candidates: str) -> str:
        for c in candidates:
            key = c.lower()
            if key in lower_map:
                val = row[lower_map[key]]
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        return ""

    thuis = pick("thuis", "home", "team1", "team a", "team_a", "team-a")
    uit   = pick("uit", "away", "team2", "team b", "team_b", "team-b")
    hs    = pick("hs", "homescore", "score1", "h", "goals home", "goals_home")
    as_   = pick("as", "awayscore", "score2", "a", "goals away", "goals_away")
    score = ""
    if hs or as_:
        score = f"{hs}-{as_}".strip("-")

    # als we geen standaardkolommen vinden: bouw iets bruikbaars van de eerste 3–4 niet-lege cellen
    if not (thuis or uit or score):
        values = [str(v).strip() for v in row.tolist() if pd.notna(v) and str(v).strip()]
        if not values:
            return ""
        # heuristisch: "val1 - val2 val3" etc.
        if len(values) >= 3:
            return f"{values[0]} - {values[1]} {values[2]}"
        elif len(values) == 2:
            return f"{values[0]} - {values[1]}"
        else:
            return values[0]

    line_core = " ".join(part for part in [f"{thuis} - {uit}".strip(" -"), score] if part).strip()
    return line_core


def process(input_xlsx_path: str, options: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Robuuste processor voor 'amateursport overig'.
    - Geen vaste iloc-indexen meer (voorkomt 'index out of bounds').
    - Pakt eerste niet-lege sheet.
    - Bouwt per rij een regel; slaat lege rijen over.
    - Schrijft altijd een tekstbestand weg (desnoods met waarschuwing).
    """
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = options.get("out_name") or "cue_overig.txt"
    out_path = out_dir / out_name

    try:
        df = _first_nonempty_sheet(input_xlsx_path)
    except Exception as e:
        msg = f"(FOUT) Kan het Excelbestand niet verwerken: {e}"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(msg + "\n")
        return {"text_output": msg, "attachments": [{"name": out_name, "path": str(out_path)}]}

    # Eventueel trim header-achtige rijen: als eerste rij alleen 1 cel heeft en verder leeg → overslaan
    lines: List[str] = []
    for _, row in df.iterrows():
        line = _guess_teams_and_score(row)
        if line:
            lines.append(line)

    if not lines:
        # Geef diagnose terug (vormt geen crash meer)
        shape_info = f"{df.shape[0]} rijen × {df.shape[1]} kolommen"
        sample = " / ".join([str(x) for x in df.columns.tolist()[:6]])
        text_output = (
            "(WAARSCHUWING) Er zijn geen regels gegenereerd.\n"
            f"Geparst blad had {shape_info}.\n"
            f"Kolommen (eerste 6): {sample or '(geen)'}\n"
            "Controleer of je het juiste invulbestand gebruikt en of rijen niet volledig leeg zijn."
        )
    else:
        text_output = "\n".join(lines)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text_output)

    return {"text_output": text_output, "attachments": [{"name": out_name, "path": str(out_path)}]}
