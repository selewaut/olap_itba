"""Build SCD Type 2 dimensions from the normalized VD fact datasets.

The script reads ``fact_fondos_sbs.csv`` and ``fact_fondos_competencia.csv``,
then creates one shared class dimension and one shared fund dimension. SCD2 rows
are created when a tracked dimension attribute changes.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

from src.config import PROCESSED_DIR

_FACTS = (
    PROCESSED_DIR / "fact_fondos_sbs.csv",
    PROCESSED_DIR / "fact_fondos_competencia.csv",
)
_CLASS_OUTPUT = PROCESSED_DIR / "dim_fondo_clase.csv"
_FUND_OUTPUT = PROCESSED_DIR / "dim_fondo.csv"
_CLASS_ATTRIBUTES = [
    "calificacion",
    "tipo_cliente",
    "comision_ingreso",
    "honorarios_adm_sg",
    "honorarios_adm_sd",
    "otros_gastos",
    "comision_rescate",
    "moneda",
]
_FUND_ATTRIBUTES = [
    "region",
    "tipo_fondo",
    "tipo_renta",
    "tipo_renta_mixta",
    "moneda",
    "benchmark",
    "sociedad_gestora",
]


def _normalize(value: pd.Series) -> pd.Series:
    """Normalize text and numeric-like values for change comparisons."""
    text = value.astype("string").str.strip()
    numeric = pd.to_numeric(text, errors="coerce")
    numeric_mask = text.notna() & numeric.notna()
    text.loc[numeric_mask] = numeric.loc[numeric_mask].map(lambda x: f"{x:.12g}")
    return text.mask(text.eq("") | text.isna(), "")


def _majority_currency(values: pd.Series) -> str:
    """Return the most common non-empty currency for a fund/date group."""
    text = values.astype("string").str.strip()
    text = text[text.notna() & text.ne("")]
    if text.empty:
        return pd.NA
    counts = text.value_counts()
    most_common = counts[counts.eq(counts.max())].index.tolist()
    return sorted(most_common)[0]


def _hash_key(*values: str) -> str:
    """Create a deterministic version key from dimension values."""
    source = "|".join(values)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]


def _read_facts(paths: tuple[Path, ...] = _FACTS) -> pd.DataFrame:
    """Read and concatenate the two normalized fact datasets."""
    frames = [pd.read_csv(path, dtype="string") for path in paths]
    return pd.concat(frames, ignore_index=True)


def _prepare_class_source(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Prepare one source row per class and analytical date."""
    source = df.copy()
    for column in [
        "id_fondo_clase_dim",
        "id_fondo",
        "id_codigo_fondo_clase",
        "nombre_fondo_clase_origen",
        "nombre_fondo",
        "nombre_clase",
    ]:
        source[column] = source[column].astype("string").str.strip()
    source = source.sort_values(["id_fondo_clase_dim", "fecha", "id_codigo_fondo_clase"])
    duplicate_count = int(source.duplicated(["id_fondo_clase_dim", "fecha"]).sum())
    source = source.drop_duplicates(["id_fondo_clase_dim", "fecha"], keep="first")
    return source, duplicate_count


def _build_class_scd(source: pd.DataFrame) -> pd.DataFrame:
    """Create class dimension versions when a class attribute changes."""
    comparison = source.copy()
    for attribute in _CLASS_ATTRIBUTES:
        comparison[attribute] = _normalize(comparison[attribute])
    comparison = comparison.sort_values(["id_fondo_clase_dim", "fecha"])
    previous = comparison.groupby("id_fondo_clase_dim", sort=False)[
        _CLASS_ATTRIBUTES
    ].shift()
    is_new = comparison[_CLASS_ATTRIBUTES].ne(previous).any(axis=1)
    is_new.loc[
        comparison.groupby("id_fondo_clase_dim", sort=False).head(1).index
    ] = True
    versions = comparison.loc[is_new].copy()
    versions["valid_from"] = versions["fecha"]
    next_dates = pd.to_datetime(
        versions.groupby("id_fondo_clase_dim", sort=False)["fecha"].shift(-1)
    )
    versions["valid_to"] = (next_dates - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    versions["is_current"] = versions["valid_to"].isna()
    versions["sk_fondo_clase"] = versions.apply(
        lambda row: "FC-" + _hash_key(row["id_fondo_clase_dim"], row["valid_from"]),
        axis=1,
    )
    columns = [
        "sk_fondo_clase",
        "id_fondo_clase_dim",
        "id_fondo",
        "id_codigo_fondo_clase",
        "nombre_fondo_clase_origen",
        "nombre_fondo",
        "nombre_clase",
        "valid_from",
        "valid_to",
        "is_current",
        *_CLASS_ATTRIBUTES,
    ]
    return versions[columns]


def _prepare_fund_source(source: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Aggregate class rows to one deterministic source row per fund/date."""
    fund_source = source.sort_values(
        ["id_fondo", "fecha", "id_fondo_clase_dim"]
    ).copy()
    conflict_keys = ["id_fondo", "fecha"]
    fund_source["moneda"] = fund_source.groupby(conflict_keys, sort=False)[
        "moneda"
    ].transform(_majority_currency)
    conflict_columns = conflict_keys + _FUND_ATTRIBUTES
    conflict_counts = fund_source[conflict_columns].drop_duplicates().groupby(
        conflict_keys, dropna=False
    ).size()
    conflict_count = int((conflict_counts > 1).sum())
    fund_source = fund_source.drop_duplicates(conflict_keys, keep="first")
    return fund_source, conflict_count


def _build_fund_scd(source: pd.DataFrame) -> pd.DataFrame:
    """Create fund dimension versions when a fund attribute changes."""
    comparison = source.copy()
    for attribute in _FUND_ATTRIBUTES:
        comparison[attribute] = _normalize(comparison[attribute])
    comparison = comparison.sort_values(["id_fondo", "fecha"])
    previous = comparison.groupby("id_fondo", sort=False)[_FUND_ATTRIBUTES].shift()
    is_new = comparison[_FUND_ATTRIBUTES].ne(previous).any(axis=1)
    is_new.loc[comparison.groupby("id_fondo", sort=False).head(1).index] = True
    versions = comparison.loc[is_new].copy()
    versions["valid_from"] = versions["fecha"]
    next_dates = pd.to_datetime(versions.groupby("id_fondo", sort=False)["fecha"].shift(-1))
    versions["valid_to"] = (next_dates - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    versions["is_current"] = versions["valid_to"].isna()
    versions["sk_fondo"] = versions.apply(
        lambda row: "FD-" + _hash_key(row["id_fondo"], row["valid_from"]),
        axis=1,
    )
    class_counts = source.groupby("id_fondo")["id_fondo_clase_dim"].nunique()
    versions["cantidad_clases"] = versions["id_fondo"].map(class_counts)
    columns = [
        "sk_fondo",
        "id_fondo",
        "valid_from",
        "valid_to",
        "is_current",
        "nombre_fondo",
        *_FUND_ATTRIBUTES,
        "cantidad_clases",
    ]
    return versions[columns]


def build_dimensions(
    fact_paths: tuple[Path, ...] = _FACTS,
    class_output: str | Path = _CLASS_OUTPUT,
    fund_output: str | Path = _FUND_OUTPUT,
) -> dict[str, int]:
    """Build both normalized SCD2 dimension files and return counts."""
    facts = _read_facts(fact_paths)
    class_source, class_same_date_duplicates = _prepare_class_source(facts)
    class_dimension = _build_class_scd(class_source)
    fund_source, fund_conflicts = _prepare_fund_source(class_source)
    fund_dimension = _build_fund_scd(fund_source)
    class_output = Path(class_output)
    fund_output = Path(fund_output)
    class_output.parent.mkdir(parents=True, exist_ok=True)
    fund_output.parent.mkdir(parents=True, exist_ok=True)
    class_dimension.to_csv(class_output, index=False)
    fund_dimension.to_csv(fund_output, index=False)
    counts = {
        "fact_rows": len(facts),
        "class_keys": class_source["id_fondo_clase_dim"].nunique(),
        "fund_keys": fund_source["id_fondo"].nunique(),
        "class_same_date_duplicates_removed": class_same_date_duplicates,
        "fund_date_attribute_conflicts": fund_conflicts,
        "class_scd2_rows": len(class_dimension),
        "fund_scd2_rows": len(fund_dimension),
    }
    for name, value in counts.items():
        print(f"{name}: {value}")
    print(f"class_output: {class_output}")
    print(f"fund_output: {fund_output}")
    return counts


def main() -> None:
    """Run the normalized dimension builder from the command line."""
    parser = argparse.ArgumentParser(
        description="Genera dimensiones SCD2 de fondos y clases de cuenta"
    )
    parser.add_argument("--class-output", type=Path, default=_CLASS_OUTPUT)
    parser.add_argument("--fund-output", type=Path, default=_FUND_OUTPUT)
    args = parser.parse_args()
    build_dimensions(class_output=args.class_output, fund_output=args.fund_output)


if __name__ == "__main__":
    main()
