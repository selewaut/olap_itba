"""Cliente BCRA Estadisticas v4.0 (Principales Variables / Monetarias).

Docs: https://www.bcra.gob.ar/apis-banco-central
      https://principales-variables.bcra.apidocs.ar/
Sin auth. Rate-limit generoso; igual se usa sesion + backoff simple.

Cubre: dolar oficial (4,5), CER (30), UVA (31), BADLAR (7), TAMAR (44).
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import BCRA_BASE, RAW_DIR, as_date, default_range, series_of
from src.downloading.common import TIMEOUT, save_csv, session


def fetch_bcra_variable(id_variable: int, desde: str | date, hasta: str | date,
                        limit: int = 1000) -> pd.DataFrame:
    """Devuelve DataFrame [fecha, valor] para una variable BCRA con paginado offset/limit.

    Nota 2026-09-23: el endpoint detalle (/Monetarias/{id}) esta devolviendo
    detalle=[] aunque /Monetarias lista bien (count=1610) y /Metodologia ok.
    Parece caida/transitoria del lado BCRA. Se mantiene el cliente igual y se
    avisa con warning si viene vacio. Fallback: Informe Monetario Diario XLS
    o estadisticasbcra.com (requiere token).
    """
    desde_s = as_date(desde).isoformat()
    hasta_s = as_date(hasta).isoformat()
    out: list[dict] = []
    offset = 0
    with session() as s:
        while True:
            url = f"{BCRA_BASE}/Monetarias/{id_variable}"
            r = s.get(url, timeout=TIMEOUT,
                      params={"desde": desde_s, "hasta": hasta_s,
                              "limit": limit, "offset": offset})
            r.raise_for_status()
            payload = r.json()
            chunk = payload.get("results", [{}])[0].get("detalle", [])
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < limit:
                break
            offset += limit
            time.sleep(0.2)
    df = pd.DataFrame(out)
    if df.empty:
        import warnings
        warnings.warn(
            f"BCRA id={id_variable} devolvio 0 filas ({desde_s}..{hasta_s}). "
            "Posible caida del endpoint detalle; reintentar mas tarde o usar fallback XLS.")
        return pd.DataFrame(columns=["fecha", "valor"])
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.sort_values("fecha").reset_index(drop=True)


def fetch_all_bcra(desde: str | date, hasta: str | date) -> dict[str, pd.DataFrame]:
    """Descarga todas las series BCRA del catalogo. Clave = codigo de dim_indice."""
    return {s.codigo: fetch_bcra_variable(int(s.source_id), desde, hasta)
            for s in series_of("bcra")}


if __name__ == "__main__":
    import argparse
    dflt_desde, dflt_hasta = default_range()
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default=dflt_desde)
    ap.add_argument("--hasta", default=dflt_hasta)
    ap.add_argument("--outdir", type=Path, default=RAW_DIR)
    a = ap.parse_args()
    frames = fetch_all_bcra(a.desde, a.hasta)
    for s in series_of("bcra"):
        p = save_csv(frames[s.codigo], a.outdir / s.filename)
        print(f"{s.codigo}: {len(frames[s.codigo])} filas -> {p}")
