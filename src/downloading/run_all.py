"""Orquestador: descarga ultimos 2 anios de los indices a data/raw/.

Uso:
  uv run python -m src.downloading.run_all
  uv run python -m src.downloading.run_all --desde 2024-09-23 --hasta 2026-09-23
  uv run python -m src.downloading.run_all --only bcra,merval

Notas:
- BCRA: rapido (~6 series x 730 dias). Sin auth.
- CCL: ~dias habiles requests a ArgentinaDatos, ~3-5 min. Reanuda si ccl.csv existe.
- Merval/Bovespa: requiere `yfinance`.
- INDEC: datos.gob.ar Series API (mensual, rapido). Sin auth.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR, default_range, serie_by_codigo, series_of
from src.downloading.bcra_client import fetch_all_bcra
from src.downloading.common import save_csv
from src.downloading.dolar_ccl import fetch_ccl_range
from src.downloading.indec_client import fetch_all_indec
from src.downloading.market_yfinance import fetch_bovespa, fetch_merval, merval_usd

VALID_ONLY = ("bcra", "ccl", "merval", "bovespa", "indec")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default=None)
    ap.add_argument("--hasta", default=None)
    ap.add_argument("--outdir", type=Path, default=RAW_DIR)
    ap.add_argument("--only", default="all",
                    help="all | coma: " + ",".join(VALID_ONLY))
    ap.add_argument("--ccl-sleep", type=float, default=0.15)
    a = ap.parse_args()

    dflt_desde, dflt_hasta = default_range()
    desde, hasta = a.desde or dflt_desde, a.hasta or dflt_hasta
    a.outdir.mkdir(parents=True, exist_ok=True)
    if a.only == "all":
        only = set(VALID_ONLY)
    else:
        only = {x.strip() for x in a.only.split(",") if x.strip()}
        unknown = only - set(VALID_ONLY)
        if unknown:
            ap.error(f"--only desconocido: {sorted(unknown)}. Validos: {VALID_ONLY}")
    print(f"Ventana: {desde} -> {hasta} | modulos: {sorted(only)}")
    failed: list[str] = []

    if "bcra" in only:
        frames = fetch_all_bcra(desde, hasta)
        for s in series_of("bcra"):
            df = frames[s.codigo]
            p = save_csv(df, a.outdir / s.filename)
            print(f"  BCRA {s.codigo}: {len(df)} filas -> {p}")
            if df.empty:
                failed.append(s.codigo)

    ccl_s = serie_by_codigo("USD_CCL")
    ccl_path = a.outdir / ccl_s.filename
    ccl_df: pd.DataFrame | None = None
    if "ccl" in only:
        ccl_df = fetch_ccl_range(desde, hasta, sleep_s=a.ccl_sleep, cache_path=ccl_path)
        print(f"  CCL: {len(ccl_df)} filas -> {ccl_path}")
        if ccl_df.empty:
            failed.append(ccl_s.codigo)
    elif "merval" in only and ccl_path.exists():
        ccl_df = pd.read_csv(ccl_path)

    if "merval" in only:
        m_s = serie_by_codigo("MERVAL_ARS")
        m = fetch_merval(desde, hasta)
        save_csv(m, a.outdir / m_s.filename)
        print(f"  MERVAL ARS: {len(m)} filas -> {m_s.filename}")
        if m.empty:
            failed.append(m_s.codigo)
        usd_s = serie_by_codigo("MERVAL_USD")
        if ccl_df is not None and not ccl_df.empty:
            mu = merval_usd(m, ccl_df)
            save_csv(mu, a.outdir / usd_s.filename)
            print(f"  MERVAL USD (derivado): {len(mu)} filas -> {usd_s.filename}")
        else:
            print("  MERVAL USD omitido: no hay ccl.csv")

    if "bovespa" in only:
        b_s = serie_by_codigo("BOVESPA")
        b = fetch_bovespa(desde, hasta)
        save_csv(b, a.outdir / b_s.filename)
        print(f"  BOVESPA: {len(b)} filas -> {b_s.filename}")
        if b.empty:
            failed.append(b_s.codigo)

    if "indec" in only:
        try:
            desde_m = pd.to_datetime(desde).to_period("M").to_timestamp().date().isoformat()
            frames = fetch_all_indec(desde_m)
            for s in series_of("indec"):
                df = frames[s.codigo]
                p = save_csv(df, a.outdir / s.filename)
                print(f"  INDEC {s.codigo}: {len(df)} filas -> {p}")
                if df.empty:
                    failed.append(s.codigo)
        except Exception as e:  # noqa: BLE001 - se quiere mensaje accionable
            print(f"  INDEC fallo: {e} -> ver docs/SOURCES.md")
            failed.append("indec")

    if failed:
        print(f"FAIL: series vacias o con error: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
