"""Merval (ARS + USD) y Bovespa via Yahoo Finance (yfinance).

- MERVAL ARS: ticker ^MERV (diario, 2 anios). Fuente oficial alternativa: BYMA
  (https://www.byma.com.ar, sin API publica -> scraping o Investing.com).
- MERVAL USD: derivado = MERVAL_ARS close / CCL venta del mismo dia
  (forward-fill CCL para feriados). Asi se obtiene la serie 4 del pedido
  "Merval (USD, pesos)" sin depender de un ticker USD poco liquido.
- BOVESPA: ticker ^BVSP (Ibovespa BRL). Alternativa oficial: B3
  (https://www.b3.com.br) / Investing.com.

Requiere: pip install yfinance
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import RAW_DIR, default_range, serie_by_codigo
from src.downloading.common import save_csv

MERVAL_TICKER = str(serie_by_codigo("MERVAL_ARS").source_id)
BOVESPA_TICKER = str(serie_by_codigo("BOVESPA").source_id)


def _dl(ticker: str, desde: str, hasta: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(ticker, start=desde, end=hasta, auto_adjust=False,
                     progress=False, threads=True)
    if df.empty:
        return pd.DataFrame(columns=["fecha", "open", "high", "low", "close", "volume"])
    # yfinance >=0.2 devuelve columnas MultiIndex (Price, Ticker); aplanar
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    rename = {"date": "fecha", "adj_close": "adj_close"}
    df = df.rename(columns=rename)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    keep = [c for c in ["fecha", "open", "high", "low", "close", "volume", "adj_close"] if c in df.columns]
    return df[keep].sort_values("fecha").reset_index(drop=True)


def fetch_merval(desde: str, hasta: str) -> pd.DataFrame:
    df = _dl(MERVAL_TICKER, desde, hasta)
    df["fuente"] = "Yahoo ^MERV"
    return df


def fetch_bovespa(desde: str, hasta: str) -> pd.DataFrame:
    df = _dl(BOVESPA_TICKER, desde, hasta)
    df["fuente"] = "Yahoo ^BVSP"
    return df


def merval_usd(merval_ars: pd.DataFrame, ccl: pd.DataFrame) -> pd.DataFrame:
    """Cruza Merval ARS con CCL venta (ffill) para serie en USD."""
    m = merval_ars.copy()
    c = ccl[["fecha", "venta"]].copy().rename(columns={"venta": "ccl_venta"})
    m["fecha"] = pd.to_datetime(m["fecha"])
    c["fecha"] = pd.to_datetime(c["fecha"])
    m = m.sort_values("fecha").merge(c.sort_values("fecha"), on="fecha", how="left")
    m["ccl_venta"] = m["ccl_venta"].ffill()
    m["close_usd"] = m["close"] / m["ccl_venta"]
    m["fuente"] = "derivado MERVAL_ARS/CCL"
    return m


if __name__ == "__main__":
    import argparse
    dflt_desde, dflt_hasta = default_range()
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default=dflt_desde)
    ap.add_argument("--hasta", default=dflt_hasta)
    ap.add_argument("--outdir", type=Path, default=RAW_DIR)
    a = ap.parse_args()
    merval = serie_by_codigo("MERVAL_ARS")
    bovespa = serie_by_codigo("BOVESPA")
    save_csv(fetch_merval(a.desde, a.hasta), a.outdir / merval.filename)
    save_csv(fetch_bovespa(a.desde, a.hasta), a.outdir / bovespa.filename)
    print(f"ok: {merval.filename}, {bovespa.filename}")
