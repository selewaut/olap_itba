"""Limpieza y normalizacion hacia el modelo del DW.

Entrada: data/raw/*.csv (formatos heterogeneos por fuente).
Salida:
  data/processed/fact_cotizacion.csv     (fecha, indice_detalle_key, valor, frecuencia)
  data/processed/dim_indice.csv          (nivel generico, catalogo de src/config.py)
  data/processed/dim_indice_detalle.csv  (nivel detalle = moneda, es el grano del fact)

Reglas:
- fechas a ISO YYYY-MM-DD; duplicados -> ultimo valor.
- series diarias monetarias: NO rellenar fines de semana con ffill para el fact
  (se preserva grano real); el ffill solo se aplica al derivar MERVAL_USD.
- grano mixto: las series mensuales (INDEC) no llevan fecha, solo mes_anio
  (YYYYMM). El fact declara una u otra, nunca las dos.
- frecuencia: 'M' para las series mensuales, 'D' para el resto. Vive en
  dim_indice y se resuelve via dim_indice_detalle.
- escala: las series de A_PORCENTAJE llegan a la fuente como fraccion y se
  guardan ya en porcentaje, para que valor sea comparable entre series.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import (
    INDICES,
    INDICES_DETALLE,
    PROCESSED_DIR,
    RAW_DIR,
    SERIES,
    frecuencia_de_detalle,
)

FACT_COLS = ["fecha", "indice_detalle_key", "valor", "frecuencia", "mes_anio"]

# indice_detalle_key -> factor para llevar la unidad de la fuente a la del fact.
# INDEC publica la variacion mensual como fraccion (0.0347 = 3.47%); el fact la
# guarda en porcentaje, igual que TAMAR/BADLAR.
A_PORCENTAJE = {"IPC_VAR": 100.0}


def load_raw_long(rawdir: str | Path) -> pd.DataFrame:
    """Lee todos los CSV del catalogo SERIES hacia el grano del fact."""
    rawdir = Path(rawdir)
    frec = frecuencia_de_detalle()
    frames = []
    for s in SERIES:
        p = rawdir / s.filename
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["fecha"])
        if s.value_column not in df.columns:
            continue
        valor = pd.to_numeric(df[s.value_column], errors="coerce")
        if s.codigo in A_PORCENTAJE:
            valor = valor * A_PORCENTAJE[s.codigo]
        out = pd.DataFrame({
            "fecha": df["fecha"],
            "indice_detalle_key": s.codigo,
            "valor": valor,
            "frecuencia": frec.get(s.codigo),
        })
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=[c for c in FACT_COLS if c != "mes_anio"])
    out = pd.concat(frames, ignore_index=True)
    out = (out.sort_values(["indice_detalle_key", "fecha"])
              .drop_duplicates(["indice_detalle_key", "fecha"], keep="last"))
    sin_frec = sorted(set(out.loc[out["frecuencia"].isna(), "indice_detalle_key"]) - set(frec))
    if sin_frec:
        raise KeyError(f"series sin frecuencia en INDICES_DETALLE: {sin_frec}")
    return out


def build_fact(rawdir: str | Path = RAW_DIR, outdir: str | Path = PROCESSED_DIR) -> pd.DataFrame:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fact = load_raw_long(rawdir)
    fact = fact.dropna(subset=["valor"])
    fact["fecha"] = pd.to_datetime(fact["fecha"])

    # Las series mensuales se quedaban con la fecha del primer dia del mes que
    # trae la fuente. Se pasa a grano periodo: mes_anio YYYYMM y sin fecha.
    # Se hace aca, y no en load_raw_long, porque antes hay que deduplicar: con
    # la fecha en NaT las 24 observaciones de un mes colapsarian en una.
    mensual = fact["frecuencia"].eq("M")
    fact["mes_anio"] = pd.NA
    fact.loc[mensual, "mes_anio"] = fact.loc[mensual, "fecha"].dt.strftime("%Y%m")
    fact.loc[mensual, "fecha"] = pd.NaT

    fact["fecha"] = fact["fecha"].dt.date
    fact = fact[FACT_COLS]
    fact.to_csv(outdir / "fact_cotizacion.csv", index=False)
    pd.DataFrame([i.__dict__ for i in INDICES]).to_csv(outdir / "dim_indice.csv", index=False)
    pd.DataFrame([d.__dict__ for d in INDICES_DETALLE]).to_csv(
        outdir / "dim_indice_detalle.csv", index=False)
    print(f"fact_cotizacion: {len(fact)} filas, "
          f"{fact['indice_detalle_key'].nunique()} series, "
          f"{int(mensual.sum())} mensuales, {len(INDICES)} indices, {len(INDICES_DETALLE)} detalles")
    return fact


if __name__ == "__main__":
    build_fact()
