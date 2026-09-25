"""Build normalized SBS and competition fact datasets from ``vd_daily.csv``.

The input contains one row for each fund/class observation in a daily VD
workbook. Source columns are renamed to normalized names immediately after
loading, dates are converted to ISO format, repeated observations are removed,
and the following outputs are written:

- ``fact_fondos_sbs.csv``: open SBS funds at the available daily grain.
- ``fact_fondos_competencia.csv``: latest available monthly observation for each
  open non-SBS fund/class.

The source ``data/processed/vd_daily.csv`` and ``data/raw/VD.zip`` are not
modified.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd

from src.config import PROCESSED_DIR

_INPUT_DEFAULT = PROCESSED_DIR / "vd_daily.csv"
_DAILY_DEFAULT = PROCESSED_DIR / "fact_fondos_sbs.csv"
_MONTHLY_DEFAULT = PROCESSED_DIR / "fact_fondos_competencia.csv"
_SBS_MANAGER = "SBS Asset Management S.A.S.G.F.C.I."
_CLASS_MARKER = re.compile(r"\bClase\b", re.IGNORECASE)
_DATE_YYYY = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")
_COLUMN_NAMES = {
    "Fecha": "fecha",
    "FondoClase": "nombre_clase",
    "fondoId": "nombre_fondo",
    "idCodigoFondoClase": "id_codigo_fondo_clase",
    "Fondos": "nombre_fondo_clase_origen",
    "Tipo de Fondo": "tipo_fondo",
    "Tipo de Renta": "tipo_renta",
    "Región": "region",
    "Tipo de Renta Mixta": "tipo_renta_mixta",
    "Duration": "duracion",
    "Benchmark": "benchmark",
    "Moneda": "moneda",
    "Clase de Cuota": "tipo_cliente",
    "VCP Actual": "vcp_actual",
    "VCP Anterior": "vcp_anterior",
    "Variación diaria": "variacion_diaria",
    "Reexp.Pesos": "reexpresion_pesos",
    "Variación mensual": "variacion_mensual",
    "Variación anual": "variacion_anual",
    "Cantidad de Cuotaparte Actual": "cantidad_cuotaparte_actual",
    "Cantidad de Cuotaparte Anterior": "cantidad_cuotaparte_anterior",
    "Patrimonio Neto Actual": "patrimonio_neto_actual",
    "Patrimonio Neto Anterior": "patrimonio_neto_anterior",
    "Calificacion": "calificacion",
    "Sociedad Gerente": "sociedad_gestora",
    "Comisión Ingreso": "comision_ingreso",
    "Honorarios Adm. SG": "honorarios_adm_sg",
    "Honorarios Adm. SD": "honorarios_adm_sd",
    "Otros Gastos": "otros_gastos",
    "Comisión Rescate": "comision_rescate",
    "Plazo Liq (Dias)": "plazo_liquidacion_dias",
    "Código Fondo CAFCI": "codigo_fondo_cafci",
    "Código Clase CAFCI": "codigo_clase_cafci",
}
_FINAL_COLUMNS = [
    "fecha",
    "id_fondo_clase_dim",
    "id_fondo",
    "id_codigo_fondo_clase",
    "nombre_fondo_clase_origen",
    "nombre_fondo",
    "nombre_clase",
    "tipo_fondo",
    "tipo_renta",
    "region",
    "tipo_renta_mixta",
    "duracion",
    "benchmark",
    "moneda",
    "tipo_cliente",
    "vcp_actual",
    "vcp_anterior",
    "variacion_diaria",
    "reexpresion_pesos",
    "variacion_mensual",
    "variacion_anual",
    "cantidad_cuotaparte_actual",
    "cantidad_cuotaparte_anterior",
    "patrimonio_neto_actual",
    "patrimonio_neto_anterior",
    "calificacion",
    "sociedad_gestora",
    "comision_ingreso",
    "honorarios_adm_sg",
    "honorarios_adm_sd",
    "otros_gastos",
    "comision_rescate",
    "plazo_liquidacion_dias",
]


def parse_dates(values: pd.Series) -> pd.Series:
    """Parse source dates and return normalized ISO dates.

    The current source uses ``DD/MM/YY``. Four-digit ``YYYY/MM/DD`` values are
    also accepted. Two-digit years use the standard ``%y`` convention:
    ``00-68`` map to ``2000-2068`` and ``69-99`` map to ``1969-1999``.
    """
    text = values.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    yyyy_mask = text.str.match(_DATE_YYYY, na=False)
    parsed.loc[yyyy_mask] = pd.to_datetime(
        text.loc[yyyy_mask], format="%Y/%m/%d", errors="coerce"
    )
    parsed.loc[~yyyy_mask] = pd.to_datetime(
        text.loc[~yyyy_mask], format="%d/%m/%y", errors="coerce"
    )
    return parsed.dt.strftime("%Y-%m-%d")


def add_fund_identity_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized fund identity and traceability columns."""
    out = df.copy()
    out["nombre_fondo_clase_origen"] = out["nombre_fondo_clase_origen"].astype("string").str.strip()
    has_class = out["nombre_fondo_clase_origen"].str.contains(_CLASS_MARKER, na=False)
    class_part = out["nombre_fondo_clase_origen"].str.extract(
        r"(\bClase\b.*)$", flags=re.IGNORECASE
    )[0]
    out["nombre_clase"] = class_part.where(
        has_class, out["nombre_fondo_clase_origen"]
    ).str.strip()
    base_fondo = out["nombre_fondo_clase_origen"].str.split(
        _CLASS_MARKER, n=1
    ).str[0].str.strip()
    out["nombre_fondo"] = base_fondo.where(
        ~has_class,
        base_fondo.str.replace(r"\s*-\s*$", "", regex=True),
    )
    out["id_fondo"] = out["nombre_fondo"]
    out["id_fondo_clase_dim"] = out["id_fondo"] + "|" + out["nombre_clase"]
    fund_code = out["codigo_fondo_cafci"].astype("string").str.strip()
    class_code = out["codigo_clase_cafci"].astype("string").str.strip()
    has_codes = (
        fund_code.notna()
        & fund_code.ne("")
        & class_code.notna()
        & class_code.ne("")
    )
    identifier = pd.Series(pd.NA, index=out.index, dtype="string")
    identifier.loc[has_codes] = (
        "CAFCI-" + fund_code.loc[has_codes] + "-" + class_code.loc[has_codes]
    )
    fallback_key = (out["id_fondo"] + "|" + out["nombre_clase"]).fillna("")
    identifier.loc[~has_codes] = fallback_key.loc[~has_codes].map(
        lambda value: "NO-CODE-" + hashlib.sha256(value.encode("utf-8")).hexdigest()
    )
    out["id_codigo_fondo_clase"] = identifier
    return out


def _output_columns(df: pd.DataFrame) -> list[str]:
    missing = [column for column in _FINAL_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas finales requeridas: {missing}")
    return _FINAL_COLUMNS.copy()


def _validate_daily(df: pd.DataFrame) -> None:
    """Validate the normalized daily SBS output before writing it."""
    if df["fecha"].isna().any():
        raise ValueError("La salida diaria contiene fecha missing")
    if not df["tipo_fondo"].eq("Abierto").all():
        raise ValueError("La salida diaria contiene fondos que no son Abierto")
    if not df["sociedad_gestora"].eq(_SBS_MANAGER).all():
        raise ValueError("La salida diaria contiene managers distintos de SBS")
    if df.duplicated(["fecha_reporte", "nombre_fondo_clase_origen"]).any():
        raise ValueError("La salida diaria tiene filas duplicadas por fecha_reporte y fondo")


def _validate_monthly(df: pd.DataFrame) -> None:
    """Validate the normalized monthly competition output before writing it."""
    if df["fecha"].isna().any():
        raise ValueError("La salida mensual contiene fecha missing")
    if not df["tipo_fondo"].eq("Abierto").all():
        raise ValueError("La salida mensual contiene fondos que no son Abierto")
    if df["sociedad_gestora"].eq(_SBS_MANAGER).any():
        raise ValueError("La salida mensual contiene managers SBS")
    month = pd.to_datetime(df["fecha"]).dt.to_period("M")
    if pd.DataFrame({"fondo": df["nombre_fondo_clase_origen"], "month": month}).duplicated().any():
        raise ValueError("La salida mensual tiene más de una fila por fondo y mes")


def build_datasets(
    input_path: str | Path = _INPUT_DEFAULT,
    daily_output: str | Path = _DAILY_DEFAULT,
    monthly_output: str | Path = _MONTHLY_DEFAULT,
) -> dict[str, int]:
    """Build both normalized fact outputs and return validation counts."""
    input_path = Path(input_path)
    daily_output = Path(daily_output)
    monthly_output = Path(monthly_output)
    df = pd.read_csv(input_path, dtype="string").rename(columns=_COLUMN_NAMES)
    required = {
        "fecha_reporte",
        "fecha",
        "nombre_fondo_clase_origen",
        "tipo_fondo",
        "sociedad_gestora",
        "codigo_fondo_cafci",
        "codigo_clase_cafci",
    }
    missing_columns = sorted(required - set(df.columns))
    if missing_columns:
        raise ValueError(f"Faltan columnas requeridas: {missing_columns}")

    original_rows = len(df)
    df = df.drop_duplicates(keep="first").copy()
    full_duplicates_removed = original_rows - len(df)

    df["fecha_original"] = df["fecha"].astype("string").str.strip()
    normalized_dates = parse_dates(df["fecha_original"])
    invalid_mask = normalized_dates.isna() & df["fecha_original"].ne("")
    invalid_dates_removed = int(invalid_mask.sum())
    missing_mask = df["fecha_original"].isna() | df["fecha_original"].eq("")
    missing_dates_removed = int(missing_mask.sum())
    df["fecha"] = normalized_dates
    df = df[df["fecha"].notna()].copy()

    df = add_fund_identity_columns(df)
    rows_before_final_full_dedup = len(df)
    df = df.drop_duplicates(keep="first").copy()
    final_full_duplicates_removed = rows_before_final_full_dedup - len(df)

    rows_before_report_key_dedup = len(df)
    df = df.drop_duplicates(
        ["fecha_reporte", "nombre_fondo_clase_origen"], keep="first"
    ).copy()
    report_key_duplicates_removed = rows_before_report_key_dedup - len(df)

    df = df.sort_values(["nombre_fondo_clase_origen", "fecha", "fecha_reporte"])
    rows_before_repeated_date_dedup = len(df)
    df = df.drop_duplicates(["nombre_fondo_clase_origen", "fecha"], keep="first").copy()
    repeated_date_duplicates_removed = rows_before_repeated_date_dedup - len(df)

    open_mask = df["tipo_fondo"].eq("Abierto")
    sbs_mask = df["sociedad_gestora"].eq(_SBS_MANAGER)
    daily = df.loc[open_mask & sbs_mask].copy()
    monthly_source = df.loc[open_mask & ~sbs_mask].copy()
    monthly_source["_month"] = pd.to_datetime(monthly_source["fecha"]).dt.to_period("M")
    monthly = (
        monthly_source.sort_values(["nombre_fondo_clase_origen", "_month", "fecha"])
        .drop_duplicates(["nombre_fondo_clase_origen", "_month"], keep="last")
        .drop(columns="_month")
    )
    daily = daily.sort_values(["fecha_reporte", "nombre_fondo_clase_origen"])
    monthly = monthly.sort_values(["nombre_fondo_clase_origen", "fecha"])

    _validate_daily(daily)
    _validate_monthly(monthly)
    daily_output.parent.mkdir(parents=True, exist_ok=True)
    monthly_output.parent.mkdir(parents=True, exist_ok=True)
    daily[_output_columns(daily)].to_csv(daily_output, index=False)
    monthly[_output_columns(monthly)].to_csv(monthly_output, index=False)

    counts = {
        "input_rows": original_rows,
        "full_duplicates_removed": full_duplicates_removed,
        "invalid_dates_removed": invalid_dates_removed,
        "missing_dates_removed": missing_dates_removed,
        "final_full_duplicates_removed": final_full_duplicates_removed,
        "report_key_duplicates_removed": report_key_duplicates_removed,
        "repeated_date_duplicates_removed": repeated_date_duplicates_removed,
        "daily_sbs_rows": len(daily),
        "monthly_competencia_rows": len(monthly),
    }
    for name, value in counts.items():
        print(f"{name}: {value}")
    print(f"daily_output: {daily_output}")
    print(f"monthly_output: {monthly_output}")
    return counts


def main() -> None:
    """Run the normalized fact builder from the command line."""
    parser = argparse.ArgumentParser(
        description="Genera fact_fondos_sbs y fact_fondos_competencia"
    )
    parser.add_argument("--input", type=Path, default=_INPUT_DEFAULT)
    parser.add_argument("--daily-output", type=Path, default=_DAILY_DEFAULT)
    parser.add_argument("--monthly-output", type=Path, default=_MONTHLY_DEFAULT)
    args = parser.parse_args()
    build_datasets(args.input, args.daily_output, args.monthly_output)


if __name__ == "__main__":
    main()
