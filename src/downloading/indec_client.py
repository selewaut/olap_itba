"""INDEC via datos.gob.ar Series API (recomendado) + fallback XLS.

Series en `src.config.SERIES` (source=indec), verificadas 2026-09-23
(base dic-2016, mensuales):
- IPC Nivel General Nacional (indice)
- IPC Nivel General Nacional (var mensual)
- IPIM Nivel general
- IPIB Nivel general

Endpoint: https://apis.datos.gob.ar/series/api/series/?ids={id}&start_date=YYYY-MM-DD&format=json/csv
Sin auth. El fallback XLS original se conserva abajo.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR, as_date, default_range, series_of
from src.downloading.common import get, save_csv

DATOS_SERIES_BASE = "https://apis.datos.gob.ar/series/api/series/"

# --- Fallback: URLs XLS INDEC directo (layout inestable, requiere limpieza manual) ---
# URLs patron (pueden cambiar de mes a mes; pasar --url explicita del ultimo informe).
INDEC_SIPM_XLS = "https://www.indec.gob.ar/ftp/cuadros/economia/series_sipm_dic2015.xls"
INDEC_IPC_SEARCH = "https://www.indec.gob.ar/ftp/cuadros/economia/"  # ver docs/SOURCES.md


def fetch_serie(serie_id: str, desde: str = "2024-09-01") -> pd.DataFrame:
    """Una serie datos.gob.ar -> DataFrame [fecha, valor, serie_id]."""
    r = get(DATOS_SERIES_BASE,
            params={"ids": serie_id, "start_date": as_date(desde).isoformat(), "limit": 5000})
    data = r.json().get("data", [])
    df = pd.DataFrame(data, columns=["fecha", "valor"])
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["serie_id"] = serie_id
    return df.sort_values("fecha").reset_index(drop=True)


def fetch_all_indec(desde: str = "2024-09-01") -> dict[str, pd.DataFrame]:
    """Clave = codigo de dim_indice."""
    return {s.codigo: fetch_serie(str(s.source_id), desde) for s in series_of("indec")}


def download_xls(url: str, timeout: int = 60) -> bytes:
    r = get(url, timeout=timeout)
    return r.content


def parse_sipm_xls(content: bytes) -> pd.DataFrame:
    """Extrae serie IPIM nivel general. Tolerante a cambios de layout INDEC."""
    xls = pd.ExcelFile(io.BytesIO(content))
    target = next((s for s in xls.sheet_names if "ipim" in s.lower() or "mayor" in s.lower()),
                  xls.sheet_names[0])
    df = xls.parse(target, header=None)
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    df["fuente_sheet"] = target
    return df


def parse_ipc_xls(content: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(content))
    target = next((s for s in xls.sheet_names if "ipc" in s.lower() or "consum" in s.lower()),
                  xls.sheet_names[0])
    df = xls.parse(target, header=None)
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    df["fuente_sheet"] = target
    return df


if __name__ == "__main__":
    import argparse
    dflt_desde, _ = default_range()
    ap = argparse.ArgumentParser(description="INDEC via datos.gob.ar (defecto) o XLS fallback.")
    ap.add_argument("--fuente", choices=["api", "xls"], default="api")
    ap.add_argument("--desde", default=dflt_desde,
                    help="start_date mensual YYYY-MM-DD (solo api)")
    ap.add_argument("--outdir", type=Path, default=RAW_DIR)
    ap.add_argument("--url", default=INDEC_SIPM_XLS)
    ap.add_argument("--tipo", choices=["sipm", "ipc"], default="sipm")
    a = ap.parse_args()
    if a.fuente == "api":
        frames = fetch_all_indec(a.desde)
        for s in series_of("indec"):
            p = save_csv(frames[s.codigo], a.outdir / s.filename)
            print(f"INDEC {s.codigo}: {len(frames[s.codigo])} filas -> {p}")
    else:
        content = download_xls(a.url)
        df = parse_sipm_xls(content) if a.tipo == "sipm" else parse_ipc_xls(content)
        p = save_csv(df, a.outdir / f"indec_{a.tipo}_raw.csv")
        print(f"INDEC {a.tipo} (xls crudo): {df.shape} -> {p} (requiere limpieza manual)")
