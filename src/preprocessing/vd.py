"""Convierte las planillas diarias de ``VD.zip`` en un CSV acotado.

El archivo de Excel usa la fecha del nombre del archivo como fecha del reporte.
La columna ``Fecha`` de cada planilla es metadata del fondo y no se usa para
seleccionar la ventana temporal. El preprocessing agrega ``fecha_reporte``
para que cada fila pueda relacionarse con el snapshot diario del que proviene.
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from src.config import PROCESSED_DIR, RAW_DIR


_ARCHIVE_DATE = re.compile(r"(?<!\d)(\d{8})_")
_ARCHIVE_DEFAULT = "VD.zip"
_OUTPUT_DEFAULT = "vd_daily.csv"


def _member_date(member: str) -> date:
    """Extrae del nombre de un miembro del zip la fecha del reporte.

    Los nombres esperados tienen el formato ``YYYYMMDD_Planilla_Diaria_F4.xlsx``.
    """
    match = _ARCHIVE_DATE.search(Path(member).name)
    if match is None:
        raise ValueError(f"No se encontro una fecha en el archivo: {member}")
    return date.fromisoformat(f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:]}")


def _subtract_years(value: date, years: int) -> date:
    """Resta años calendario conservando una fecha válida para el 29 de febrero."""
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def select_recent_members(archive_path: str | Path, years: int = 2) -> tuple[list[str], date, date]:
    """Selecciona las planillas de una ventana rolling terminada en la última fecha.

    Args:
        archive_path: Ruta al archivo ``.zip`` con las planillas diarias.
        years: Cantidad de años calendario a conservar, contando el último
            snapshot como parte de la ventana.

    Returns:
        Una tupla con los miembros ordenados cronológicamente, la fecha inicial
        inclusiva y la fecha final inclusiva.

    Raises:
        ValueError: Si ``years`` es menor que uno o el zip no contiene planillas
            ``.xlsx`` con una fecha reconocible en el nombre.
    """
    archive_path = Path(archive_path)
    if years < 1:
        raise ValueError("years debe ser mayor o igual a 1")
    with ZipFile(archive_path) as archive:
        members = [
            member
            for member in archive.namelist()
            if member.lower().endswith(".xlsx") and _ARCHIVE_DATE.search(Path(member).name)
        ]
        if not members:
            raise ValueError(f"El archivo no contiene planillas .xlsx con fecha: {archive_path}")
        dated = [(member, _member_date(member)) for member in members]
        latest = max(value for _, value in dated)
        start = _subtract_years(latest, years)
        selected = [member for member, value in dated if start <= value <= latest]
    return sorted(selected, key=_member_date), start, latest


def build_vd_daily(
    archive_path: str | Path = RAW_DIR / _ARCHIVE_DEFAULT,
    output_path: str | Path = PROCESSED_DIR / _OUTPUT_DEFAULT,
    years: int = 2,
) -> Path:
    """Lee las planillas seleccionadas y las concatena en un CSV.

    Cada workbook aporta sus filas al mismo CSV. Se agregan ``fecha_reporte``,
    extraída del nombre del archivo, y ``archivo``, que identifica el workbook
    de origen. La escritura usa un archivo temporal y solo reemplaza el
    resultado final cuando todas las planillas fueron procesadas correctamente.

    Args:
        archive_path: Ruta al zip de entrada.
        output_path: Ruta del CSV de salida.
        years: Ventana rolling en años calendario.

    Returns:
        La ruta del CSV generado.
    """
    archive_path = Path(archive_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)
    members, start, latest = select_recent_members(archive_path, years)
    written = False
    try:
        with ZipFile(archive_path) as archive:
            for member in members:
                with archive.open(member) as source:
                    frame = pd.read_excel(BytesIO(source.read()), sheet_name=0)
                frame.insert(0, "fecha_reporte", _member_date(member).isoformat())
                frame.insert(1, "archivo", Path(member).name)
                frame.to_csv(temporary_path, mode="a", index=False, header=not written)
                written = True
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    print(
        f"VD: {len(members)} archivos, {start.isoformat()} -> {latest.isoformat()} -> {output_path}"
    )
    return output_path


def main() -> None:
    """Ejecuta la conversión VD usando los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Convierte las planillas VD de los ultimos N anos")
    parser.add_argument("--archive", type=Path, default=RAW_DIR / _ARCHIVE_DEFAULT)
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR / _OUTPUT_DEFAULT)
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()
    build_vd_daily(args.archive, args.output, args.years)


if __name__ == "__main__":
    main()
