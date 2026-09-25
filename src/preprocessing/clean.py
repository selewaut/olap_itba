"""Limpieza y normalizacion hacia el modelo del DW.

Entrada: data/raw/*.csv (formatos heterogeneos por fuente).
Salida:
  data/processed/fact_cotizacion.csv  (fecha, codigo_indice, valor, fuente)
  data/processed/dim_indice.csv       (catalogo de src/config.py)
  data/processed/fact_merval_ohlc.csv (detalle OHLC Merval/Bovespa, opcional)

Reglas:
- fechas a ISO YYYY-MM-DD; duplicados -> ultimo valor.
- series diarias monetarias: NO rellenar fines de semana con ffill para el fact
  (se preserva grano real); el ffill solo se aplica al derivar MERVAL_USD.
- IPC/IPM mensuales: periodo = ultimo dia del mes.
- outliers: flag |z|>6 en retornos log diarios (no se borra, se marca).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import INDICES, PROCESSED_DIR, RAW_DIR, SERIES


def load_raw_long(rawdir: str | Path) -> pd.DataFrame:
    """Lee todos los CSV del catalogo SERIES hacia el grano del fact."""
    rawdir = Path(rawdir)
    frames = []
    for s in SERIES:
        p = rawdir / s.filename
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["fecha"])
        if s.value_column not in df.columns:
            continue
        out = pd.DataFrame({
            "fecha": df["fecha"],
            "codigo_indice": s.codigo,
            "valor": pd.to_numeric(df[s.value_column], errors="coerce"),
            "fuente": s.fuente,
        })
        if s.source == "indec":
            out["fecha"] = pd.to_datetime(out["fecha"]) + pd.offsets.MonthEnd(0)
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=["fecha", "codigo_indice", "valor", "fuente"])
    out = pd.concat(frames, ignore_index=True)
    return (out.sort_values(["codigo_indice", "fecha"])
               .drop_duplicates(["codigo_indice", "fecha"], keep="last"))


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["codigo_indice", "fecha"]).copy()
    df["log_ret"] = df.groupby("codigo_indice")["valor"].transform(
        lambda s: np.log(s / s.shift(1)))
    z = df.groupby("codigo_indice")["log_ret"].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) or 1))
    df["flag_outlier"] = z.abs() > 6
    return df.drop(columns=["log_ret"])


def build_fact(rawdir: str | Path = RAW_DIR, outdir: str | Path = PROCESSED_DIR) -> pd.DataFrame:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fact = load_raw_long(rawdir)
    fact["fecha"] = pd.to_datetime(fact["fecha"]).dt.date
    fact = fact.dropna(subset=["valor"])
    fact = flag_outliers(fact)
    fact.to_csv(outdir / "fact_cotizacion.csv", index=False)
    pd.DataFrame([i.__dict__ for i in INDICES]).to_csv(outdir / "dim_indice.csv", index=False)
    print(f"fact_cotizacion: {len(fact)} filas, {fact['codigo_indice'].nunique()} indices")
    return fact


if __name__ == "__main__":
    build_fact()
