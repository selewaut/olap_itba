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
    codigo: str       # PK natural usada en Dim_Indice
    nombre: str
    frecuencia: str   # D=diaria, M=mensual
    moneda_unidad: str
    fuente: str


@dataclass(frozen=True)
class SerieDescarga:
    """Una serie descargable: codigo de dim_indice + archivo raw + id en la fuente."""
    codigo: str
    source: str                 # bcra | ccl | merval | bovespa | indec | derivado
    filename: str               # relativo a RAW_DIR
    source_id: int | str | None = None
    value_column: str = "valor"
    fuente: str = ""


# Los 11 indices pedidos. Nota: 6 y 11 son ambos Brasil/Bovespa -> se modelan
# como uno solo (BVSP) + alias, ver SOURCES.md seccion 6.
# IPC_VAR e IPIB salen de la misma API INDEC y se cargan al fact.
INDICES = [
    Indice("USD_OFICIAL_MINORISTA", "Dolar Oficial minorista vendedor", "D", "ARS/USD", "BCRA v4 id=4"),
    Indice("USD_OFICIAL_MAYORISTA", "Dolar Oficial mayorista referencia", "D", "ARS/USD", "BCRA v4 id=5"),
    Indice("USD_CCL", "Dolar Contado con Liquidacion (CCL)", "D", "ARS/USD", "ArgentinaDatos/DolarAPI"),
    Indice("MERVAL_ARS", "S&P Merval en pesos", "D", "ARS index", "Yahoo ^MERV / BYMA"),
    Indice("MERVAL_USD", "S&P Merval en dolares (derivado)", "D", "USD index", "MERVAL_ARS / USD_CCL"),
    Indice("CER", "Indice CER", "D", "index 02/02/2002=1", "BCRA v4 id=30"),
    Indice("UVA", "Indice UVA", "D", "ARS 31/03/2016=14.05", "BCRA v4 id=31"),
    Indice("IPC", "IPC Nivel General INDEC", "M", "index", "INDEC"),
    Indice("IPC_VAR", "IPC Nivel General var. mensual", "M", "%", "INDEC"),
    Indice("IPM_IPIM", "IPM / IPIM precios mayoristas INDEC", "M", "index", "INDEC SIPM"),
    Indice("IPIB", "IPIB Nivel general INDEC", "M", "index", "INDEC SIPM"),
    Indice("TAMAR", "Tasa TAMAR privada", "D", "% n.a.", "BCRA v4 id=44"),
    Indice("BADLAR", "Tasa BADLAR privada", "D", "% n.a.", "BCRA v4 id=7"),
    Indice("BOVESPA", "Bovespa / Ibovespa Brasil", "D", "BRL index", "Yahoo ^BVSP / B3"),
]

# Catalogo de descarga: run_all y clean leen filenames / source_id de aca.
# IDs BCRA verificados contra /estadisticas/v4.0/Monetarias el 2026-09-23.
SERIES = [
    SerieDescarga("USD_OFICIAL_MINORISTA", "bcra", "bcra_dolar_oficial_minorista.csv", 4, fuente="BCRA"),
    SerieDescarga("USD_OFICIAL_MAYORISTA", "bcra", "bcra_dolar_oficial_mayorista.csv", 5, fuente="BCRA"),
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


def series_of(*sources: str) -> list[SerieDescarga]:
    wanted = set(sources)
    return [s for s in SERIES if s.source in wanted]


def serie_by_codigo(codigo: str) -> SerieDescarga:
    for s in SERIES:
        if s.codigo == codigo:
            return s
    raise KeyError(codigo)
