"""Build SCD Type 2 dimensions from the normalized VD fact datasets.

The script reads ``fact_fondos_sbs.csv`` and ``fact_fondos_competencia.csv``,
then creates one shared class dimension and one shared fund dimension. SCD2 rows
are created when a tracked dimension attribute changes.
"""
from __future__ import annotations

import argparse
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


def _close_final_versions(
    versions: pd.DataFrame, comparison: pd.DataFrame, key: str
) -> None:
    """Close a key's last version on its last observed date, in place.

    ``valid_to`` is derived from the next version, so the final version would
    otherwise stay open forever. An open version claims the key is still
    reported, which is false for the classes and funds that dropped out of the
    source. A version stays open only when it reaches the last date of the
    dataset, so ``is_current`` means "still being reported".
    """
    last_observed = comparison.groupby(key, sort=False)["fecha"].transform("max")
    # La ultima version es la de mayor valid_from del grupo. Su valid_from es la
    # fecha del ultimo cambio de atributos, que no coincide con la ultima
    # observacion: por eso se cierra contra la observacion, no contra valid_from.
    final = versions["fecha"].eq(
        versions.groupby(key, sort=False)["fecha"].transform("max")
    )
    closed = pd.to_datetime(last_observed.loc[versions.index]).dt.strftime("%Y-%m-%d")
    versions.loc[final, "valid_to"] = closed[final]
    at_end = final & last_observed.loc[versions.index].eq(comparison["fecha"].max())
    versions.loc[at_end, "valid_to"] = pd.NA
    versions["is_current"] = versions["valid_to"].isna()


def _add_fund_boundaries(source: pd.DataFrame, fund_dimension: pd.DataFrame) -> pd.DataFrame:
    """Insert a row per fund version boundary so class versions cannot straddle one.

    A class version must live inside a single fund version, otherwise there is no
    parent row to reference. Some classes have no observation on the date their
    fund changed, so the boundary row is added and the class attributes are
    carried forward. Returns the source with a ``_es_corte_fondo`` flag.
    """
    boundaries = fund_dimension.loc[
        fund_dimension.duplicated("id_fondo", keep="first"), ["id_fondo", "valid_from"]
    ].rename(columns={"valid_from": "fecha"})
    source = source.copy()
    source["_es_corte_fondo"] = False
    if boundaries.empty:
        return source

    classes = source[["id_fondo_clase_dim", "id_fondo", "fecha"]].drop_duplicates()
    first_last = classes.groupby("id_fondo_clase_dim")["fecha"].agg(["min", "max"])
    extra = boundaries.merge(
        classes[["id_fondo_clase_dim", "id_fondo"]].drop_duplicates(), on="id_fondo"
    ).merge(first_last, left_on="id_fondo_clase_dim", right_index=True)
    extra = extra[(extra.fecha > extra["min"]) & (extra.fecha <= extra["max"])]
    if extra.empty:
        return source

    added = extra[["id_fondo_clase_dim", "id_fondo", "fecha"]].drop_duplicates()
    carried = _CLASS_ATTRIBUTES + [
        "id_codigo_fondo_clase",
        "nombre_fondo_clase_origen",
        "nombre_fondo",
        "nombre_clase",
    ]
    # Descarta los cortes que la clase ya tiene observados: solo se agrega la
    # fila cuando el hecho no tiene registro en esa fecha.
    existing = set(zip(source["id_fondo_clase_dim"], source["fecha"]))
    added = added[
        [pair not in existing for pair in zip(added["id_fondo_clase_dim"], added["fecha"])]
    ]
    added = added.assign(**{column: pd.NA for column in carried})
    padded = pd.concat([source, added.reindex(columns=source.columns)], ignore_index=True)
    padded = padded.sort_values(["id_fondo_clase_dim", "fecha"])
    padded[carried] = padded.groupby("id_fondo_clase_dim", sort=False)[carried].ffill()
    # Se marca todo row que cae en un corte del fondo, no solo los agregados:
    # la clase suele tener observacion en la fecha del corte.
    cortes = set(zip(boundaries["id_fondo"], boundaries["fecha"]))
    padded["_es_corte_fondo"] = [
        pair in cortes for pair in zip(padded["id_fondo"], padded["fecha"])
    ]
    return padded


def _build_class_scd(source: pd.DataFrame) -> pd.DataFrame:
    """Create class dimension versions when a class or its fund version changes."""
    comparison = source.copy()
    for attribute in _CLASS_ATTRIBUTES:
        comparison[attribute] = _normalize(comparison[attribute])
    comparison = comparison.sort_values(["id_fondo_clase_dim", "fecha"])
    previous = comparison.groupby("id_fondo_clase_dim", sort=False)[
        _CLASS_ATTRIBUTES
    ].shift()
    is_new = comparison[_CLASS_ATTRIBUTES].ne(previous).any(axis=1)
    is_new = is_new | comparison.get("_es_corte_fondo", False)
    is_new.loc[
        comparison.groupby("id_fondo_clase_dim", sort=False).head(1).index
    ] = True
    versions = comparison.loc[is_new].copy()
    versions["valid_from"] = versions["fecha"]
    next_dates = pd.to_datetime(
        versions.groupby("id_fondo_clase_dim", sort=False)["fecha"].shift(-1)
    )
    versions["valid_to"] = (next_dates - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    _close_final_versions(versions, comparison, "id_fondo_clase_dim")
    columns = [
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
    _close_final_versions(versions, comparison, "id_fondo")
    class_counts = source.groupby("id_fondo")["id_fondo_clase_dim"].nunique()
    versions["cantidad_clases"] = versions["id_fondo"].map(class_counts)
    columns = [
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
    fund_source, fund_conflicts = _prepare_fund_source(class_source)
    fund_dimension = _build_fund_scd(fund_source)
    # El fund se construye primero: sus cortes de version son los que alinean
    # las versiones de clase, para que ninguna clase abarque dos versiones de
    # su fondo.
    aligned_source = _add_fund_boundaries(class_source, fund_dimension)
    fund_boundary_rows = len(aligned_source) - len(class_source)
    class_dimension = _build_class_scd(aligned_source)
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
        "fund_boundary_rows_added": fund_boundary_rows,
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
