"""Dolar CCL historico.

Problema: DolarAPI (https://dolarapi.com) da spot, no historial masivo.
Solucion backfill 2 anios: ArgentinaDatos API (gratuita, fuente DolarApi):
  GET https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}/{fecha}
  casa = contadoconliqui | bolsa | oficial | blue | mayorista ...
  fecha = YYYY/MM/DD
Hay que loopear dia por dia (~730 requests). Es lento pero viable; se cachea a CSV.
Alternativas evaluadas en docs/SOURCES.md: Bluelytics (spot + evolucion),
Ambito Financiero scraping, dolarblu.com historico.

Salida: DataFrame [fecha, compra, venta, fuente].
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from src.config import RAW_DIR, as_date, default_range, serie_by_codigo
from src.downloading.common import TIMEOUT, get, save_csv, session

CASA_CCL = str(serie_by_codigo("USD_CCL").source_id)
BASE = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
COLS = ["fecha", "compra", "venta", "fuente"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLS)
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["fecha"]).dt.date
    out["compra"] = pd.to_numeric(out["compra"], errors="coerce")
    out["venta"] = pd.to_numeric(out["venta"], errors="coerce")
    if "fuente" not in out.columns:
        out["fuente"] = "ArgentinaDatos"
    return (out[COLS]
            .sort_values("fecha")
            .drop_duplicates("fecha", keep="last")
            .reset_index(drop=True))


def fetch_ccl_day(d: date, sess: requests.Session) -> dict | None:
    url = f"{BASE}/{CASA_CCL}/{d.strftime('%Y/%m/%d')}"
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = sess.get(url, timeout=TIMEOUT)
            if r.status_code == 404:
                return None
            if 400 <= r.status_code < 500:
                print(f"  CCL {d}: HTTP {r.status_code}")
                return None
            r.raise_for_status()
            j = r.json()
            if isinstance(j, list):
                j = j[0] if j else None
            if not j:
                return None
            return {
                "fecha": pd.to_datetime(j.get("fecha")).date(),
                "compra": pd.to_numeric(j.get("compra"), errors="coerce"),
                "venta": pd.to_numeric(j.get("venta"), errors="coerce"),
                "fuente": "ArgentinaDatos",
            }
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    print(f"  CCL {d}: fallo {last_err}")
    return None


def fetch_ccl_range(desde: str | date, hasta: str | date,
                    sleep_s: float = 0.15,
                    cache_path: str | Path | None = None) -> pd.DataFrame:
    """Descarga CCL dia a dia. Si `cache_path` existe, solo pide fechas faltantes
    (incluye huecos) y va grabando cada 20 dias habiles para poder retomar."""
    desde_d = as_date(desde)
    hasta_d = as_date(hasta)
    cache = Path(cache_path) if cache_path else None

    existing = pd.DataFrame(columns=COLS)
    if cache and cache.exists():
        existing = _normalize(pd.read_csv(cache))
    have = set(existing["fecha"])

    needed = []
    d = desde_d
    while d <= hasta_d:
        if d.weekday() < 5 and d not in have:
            needed.append(d)
        d += timedelta(days=1)

    if not needed:
        print(f"  CCL: cache completo ({len(existing)} filas)")
        return existing

    print(f"  CCL: {len(needed)} dias habiles pendientes "
          f"(cache {len(existing)} filas, {desde_d}..{hasta_d})")
    new_rows: list[dict] = []
    with session() as s:
        for i, day in enumerate(needed, 1):
            row = fetch_ccl_day(day, s)
            if row:
                new_rows.append(row)
            if i % 20 == 0 or i == len(needed):
                print(f"  CCL {i}/{len(needed)} habiles...")
                if cache and new_rows:
                    partial = _normalize(pd.concat(
                        [existing, pd.DataFrame(new_rows)], ignore_index=True))
                    save_csv(partial, cache)
            time.sleep(sleep_s)

    out = _normalize(pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
                     if new_rows else existing)
    if cache:
        save_csv(out, cache)
    return out


def fetch_ccl_spot() -> dict:
    """Cotizacion actual via DolarAPI (rapida, para chequeo)."""
    r = get("https://dolarapi.com/v1/dolares/contadoconliqui", timeout=20)
    return r.json()


if __name__ == "__main__":
    import argparse
    dflt_desde, dflt_hasta = default_range()
    default_out = RAW_DIR / serie_by_codigo("USD_CCL").filename
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default=dflt_desde)
    ap.add_argument("--hasta", default=dflt_hasta)
    ap.add_argument("--out", type=Path, default=default_out)
    ap.add_argument("--sleep", type=float, default=0.15)
    a = ap.parse_args()
    df = fetch_ccl_range(a.desde, a.hasta, sleep_s=a.sleep, cache_path=a.out)
    print(f"CCL: {len(df)} filas -> {a.out}")
