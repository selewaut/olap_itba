"""Central catalog for DW historico de cotizaciones + FCI.

Ventana objetivo: ultimos 2 anios (rolling). `default_range()` la calcula;
START_REF/END_REF quedan como snapshot de cuando se armo el proyecto.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

# Rango de referencia al momento del setup (2026-09-23).
START_REF = "2024-09-23"
END_REF = "2026-09-23"

BCRA_BASE = "https://api.bcra.gob.ar/estadisticas/v4.0"


def as_date(value: str | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def default_range(days: int = 730) -> tuple[str, str]:
    hasta = date.today()
    desde = hasta - timedelta(days=days)
    return desde.isoformat(), hasta.isoformat()


@dataclass(frozen=True)
class Indice:
    """Nivel generico: el indice, sin importar como se exprese.

    Es el padre de N filas de INDICES_DETALLE (una por moneda/presentacion).
    """
    codigo_indice: str  # PK natural de dim_indice
    nombre_indice: str
    region: str         # Arg | Bra; mismo vocabulario que dim_fondo.region
    tipo_indice: str    # Cambio | Indice bursatil | Indice oficial | Indice de precios | Tasa
    frecuencia: str     # D=diaria, M=mensual


@dataclass(frozen=True)
class IndiceDetalle:
    """Nivel detalle: una forma concreta de expresar el indice.

    Es la granularidad del fact: MERVAL -> (MERVAL_ARS, MERVAL_USD) e
    IPC -> (IPC nivel, IPC_VAR variacion). unidad vive aqui y no en el indice
    generico porque las dos formas del IPC no comparten unidad.
    """
    indice_detalle_key: str  # PK natural de dim_indice_detalle
    codigo_indice: str       # FK a dim_indice.codigo_indice
    nombre: str              # nombre del indice + presentacion/variante
    moneda: str              # ARS | USD | BRL
    unidad: str              # unidad fisica: Tasa de cambio | Puntos de indice | Porcentaje
    fuente: str


@dataclass(frozen=True)
class SerieDescarga:
    """Una serie descargable: indice_detalle_key + archivo raw + id en la fuente."""
    codigo: str                 # = indice_detalle_key de dim_indice_detalle
    source: str                 # bcra | ccl | merval | bovespa | indec | derivado
    filename: str               # relativo a RAW_DIR
    source_id: int | str | None = None
    value_column: str = "valor"
    fuente: str = ""


# Nivel generico (dim_indice). 11 indices; unidad y moneda son de cada detalle.
# region usa el mismo vocabulario que dim_fondo.region (vd_datasets.py).
INDICES = [
    Indice("DOLAR_OFICIAL", "Dolar Oficial", "Arg", "Cambio", "D"),
    Indice("DOLAR_CCL", "Dolar Contado con Liquidacion", "Arg", "Cambio", "D"),
    Indice("MERVAL", "S&P Merval", "Arg", "Indice bursatil", "D"),
    Indice("CER", "Indice CER", "Arg", "Indice oficial", "D"),
    Indice("UVA", "Indice UVA", "Arg", "Indice oficial", "D"),
    Indice("IPC", "IPC Nivel General", "Arg", "Indice de precios", "M"),
    Indice("IPIM", "IPM / IPIM precios mayoristas", "Arg", "Indice de precios", "M"),
    Indice("IPIB", "IPIB Nivel general", "Arg", "Indice de precios", "M"),
    Indice("TAMAR", "Tasa TAMAR privada", "Arg", "Tasa", "D"),
    Indice("BADLAR", "Tasa BADLAR privada", "Arg", "Tasa", "D"),
    Indice("BOVESPA", "Bovespa / Ibovespa", "Bra", "Indice bursatil", "D"),
]

# Nivel detalle (dim_indice_detalle). 13 series; es la granularidad del fact.
# MERVAL y IPC son los unicos indices con 2 formas de expresarse.
INDICES_DETALLE = [
    IndiceDetalle("USD_OFICIAL_MINORISTA", "DOLAR_OFICIAL", "Dolar Oficial minorista vendedor", "ARS", "Tasa de cambio", "BCRA v4 id=4"),
    IndiceDetalle("USD_CCL", "DOLAR_CCL", "Dolar Contado con Liquidacion (CCL)", "ARS", "Tasa de cambio", "ArgentinaDatos/DolarAPI"),
    IndiceDetalle("MERVAL_ARS", "MERVAL", "S&P Merval en pesos", "ARS", "Puntos de indice", "Yahoo ^MERV / BYMA"),
    IndiceDetalle("MERVAL_USD", "MERVAL", "S&P Merval en dolares (derivado)", "USD", "Puntos de indice", "MERVAL_ARS / USD_CCL"),
    IndiceDetalle("CER", "CER", "Indice CER", "ARS", "Puntos de indice", "BCRA v4 id=30"),
    IndiceDetalle("UVA", "UVA", "Indice UVA", "ARS", "Puntos de indice", "BCRA v4 id=31"),
    IndiceDetalle("IPC", "IPC", "IPC Nivel General INDEC", "ARS", "Puntos de indice", "INDEC"),
    IndiceDetalle("IPC_VAR", "IPC", "IPC Nivel General INDEC variacion mensual", "ARS", "Porcentaje", "INDEC"),
    IndiceDetalle("IPM_IPIM", "IPIM", "IPM / IPIM precios mayoristas INDEC", "ARS", "Puntos de indice", "INDEC SIPM"),
    IndiceDetalle("IPIB", "IPIB", "IPIB Nivel general INDEC", "ARS", "Puntos de indice", "INDEC SIPM"),
    IndiceDetalle("TAMAR", "TAMAR", "Tasa TAMAR privada", "ARS", "Porcentaje", "BCRA v4 id=44"),
    IndiceDetalle("BADLAR", "BADLAR", "Tasa BADLAR privada", "ARS", "Porcentaje", "BCRA v4 id=7"),
    IndiceDetalle("BOVESPA", "BOVESPA", "Bovespa / Ibovespa Brasil", "BRL", "Puntos de indice", "Yahoo ^BVSP / B3"),
]

# Catalogo de descarga: run_all y clean leen filenames / source_id de aca.
# IDs BCRA verificados contra /estadisticas/v4.0/Monetarias el 2026-09-23.
SERIES = [
    SerieDescarga("USD_OFICIAL_MINORISTA", "bcra", "bcra_dolar_oficial_minorista.csv", 4, fuente="BCRA"),
    SerieDescarga("CER", "bcra", "bcra_cer.csv", 30, fuente="BCRA"),
    SerieDescarga("UVA", "bcra", "bcra_uva.csv", 31, fuente="BCRA"),
    SerieDescarga("BADLAR", "bcra", "bcra_badlar_privada_na.csv", 7, fuente="BCRA"),
    SerieDescarga("TAMAR", "bcra", "bcra_tamar_privada.csv", 44, fuente="BCRA"),
    SerieDescarga("USD_CCL", "ccl", "ccl.csv", "contadoconliqui", "venta", "ArgentinaDatos"),
    SerieDescarga("MERVAL_ARS", "merval", "merval_ars.csv", "^MERV", "close", "Yahoo"),
    SerieDescarga("MERVAL_USD", "derivado", "merval_usd.csv", None, "close_usd", "derivado"),
    SerieDescarga("BOVESPA", "bovespa", "bovespa.csv", "^BVSP", "close", "Yahoo"),
    SerieDescarga("IPC", "indec", "indec_ipc_nivel_nacional.csv", "145.3_INGNACNAL_DICI_M_15", fuente="INDEC"),
    SerieDescarga("IPC_VAR", "indec", "indec_ipc_var_mensual_nacional.csv", "145.3_INGNACUAL_DICI_M_38", fuente="INDEC"),
    SerieDescarga("IPM_IPIM", "indec", "indec_ipim_nivel.csv", "448.1_NIVEL_GENERAL_0_0_13_46", fuente="INDEC"),
    SerieDescarga("IPIB", "indec", "indec_ipib_nivel.csv", "449.1_NIVEL_GENERAL_0_0_13_97", fuente="INDEC"),
]


def frecuencia_de_detalle() -> dict[str, str]:
    """indice_detalle_key -> frecuencia, heredada del indice padre."""
    por_codigo = {i.codigo_indice: i.frecuencia for i in INDICES}
    return {d.indice_detalle_key: por_codigo[d.codigo_indice] for d in INDICES_DETALLE}


def series_of(*sources: str) -> list[SerieDescarga]:
    wanted = set(sources)
    return [s for s in SERIES if s.source in wanted]


def serie_by_codigo(codigo: str) -> SerieDescarga:
    for s in SERIES:
        if s.codigo == codigo:
            return s
    raise KeyError(codigo)
