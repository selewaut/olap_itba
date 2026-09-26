# OLAP ITBA - DB Connection Guide

Database from `pollutant.sql`: tables `station`, `item`, `measurement`.

## 1. Prerequisites

- macOS + `zsh`
- PostgreSQL installed (Homebrew or Postgres.app)
- This repo: `pollutant.sql`

Verify install:
```zsh
psql --version
pg_isready
```

## 2. Start server

pgAdmin **cannot** start/stop the server, only connect/disconnect. Use terminal:

Homebrew:
```zsh
brew services start postgresql
brew services stop postgresql
brew services restart postgresql
```

Postgres.app: use Start/Stop button in the app.

Check:
```zsh
pg_isready
# expected: /tmp:5432 - accepting connections
```

## 3. Create database and load data

```zsh
createdb olap
psql -d olap -f "/Users/selewaut/Code Projects/master/olap_itba/pollutant.sql"
```

With explicit user/host:
```zsh
psql -U selewaut -h localhost -d olap -f "/Users/selewaut/Code Projects/master/olap_itba/pollutant.sql"
```
Note: Homebrew default user is your macOS username. Postgres.app / EDB default is `postgres`.

Verify via CLI:
```zsh
psql -d olap -c "\dt" -c "SELECT count(*) FROM station; SELECT count(*) FROM item; SELECT count(*) FROM measurement;"
```
Expected: 3 stations, 8 items, ~50+ measurements.

## 4. Connect with psql (CLI)

```zsh
psql -d olap
```

Useful commands:
```sql
\dt
\d station
SELECT * FROM station LIMIT 10;
```

## 5. Connect with pgAdmin 4 (GUI)

1. Left panel > Right-click `Servers` > `Register` > `Server`
2. `General` tab: Name = `Local`
3. `Connection` tab:
   - Host: `localhost`
   - Port: `5432`
   - Maintenance database: `postgres`
   - Username: `selewaut` (Homebrew) or `postgres` (Postgres.app)
   - Password: blank for Homebrew default, or what you set
4. `Save`
5. Browse: `Servers > Local > Databases > olap > Schemas > public > Tables`
6. Right-click `olap` > `Query Tool`:
```sql
SELECT * FROM station LIMIT 10;
SELECT * FROM item;
SELECT * FROM measurement LIMIT 10;
```

## Troubleshooting

- `connection refused`: server not running or wrong port. Run `brew services list` + `pg_isready`.
- `database does not exist`: run `psql -l` to list DBs, re-run `createdb olap`.
- `password authentication failed`: wrong username. Try your macOS username vs `postgres`.

## Data warehouse (`fci_dw`)

Star schema for the index quotes and the fund data. Schema in
`sql/tablas_fondos.sql`, load in `sql/dw_load.sql`.

```zsh
uv run python -m src.preprocessing.clean
uv run python -m src.preprocessing.vd_datasets
uv run python -m src.preprocessing.vd_dimensions

createdb fci_dw
psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/tablas_fondos.sql
psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/dw_load.sql
```

Nine tables, and the load takes about two seconds. `dw_load.sql` ends with
validation queries that must all return zero:

```zsh
psql -d fci_dw -c "\dt"
```

DBeaver: driver PostgreSQL, host `localhost`, port `5432`, database
`fci_dw`, username = your macOS username, password blank (local
`pg_hba.conf` uses `trust`).

To reload, drop and recreate the database. The load is not idempotent.

## VD daily preprocessing

El proyecto incluye un preprocesador para los fondos comunes de inversión del archivo `data/raw/VD.zip`. El zip contiene un workbook `.xlsx` por cada snapshot diario disponible.

### Qué selecciona

El preprocesador no usa la fecha actual del sistema. Primero lee las fechas de los nombres de archivo, calcula la fecha más reciente y conserva la ventana inclusiva de los últimos dos años calendario. Por ejemplo, si el último snapshot es `20260923_Planilla_Diaria_F4.xlsx`, incluye desde `20240923_Planilla_Diaria_F4.xlsx` hasta ese snapshot.

La columna `Fecha` original de cada workbook contiene metadata del fondo y no determina la ventana. El preprocesamiento agrega `fecha_reporte` para distinguir la fecha del snapshot de esa metadata.

### Ejecución

Desde la raíz del repositorio:

```zsh
uv run python -m src.preprocessing.vd
```

El resultado se escribe en `data/processed/vd_daily.csv`. El archivo original `data/raw/VD.zip` no se modifica.

Para usar otra ruta, otra cantidad de años o un destino distinto:

```zsh
uv run python -m src.preprocessing.vd \
  --archive data/raw/VD.zip \
  --output data/processed/vd_daily.csv \
  --years 2
```

### Formato de salida

El CSV conserva todas las columnas de la primera hoja de cada workbook y agrega:

- `fecha_reporte`: fecha del snapshot, en formato `YYYY-MM-DD`.
- `archivo`: nombre del workbook de origen.

Los registros se escriben en orden cronológico por workbook. La conversión usa un archivo temporal y reemplaza el CSV final solo si todos los workbooks se pudieron leer, por lo que una ejecución fallida no deja un resultado parcial.

### Comprobación rápida

```zsh
uv run python - <<'PY'
import pandas as pd

df = pd.read_csv("data/processed/vd_daily.csv", usecols=["fecha_reporte", "archivo"])
print(df["fecha_reporte"].min())
print(df["fecha_reporte"].max())
print(df["archivo"].nunique())
PY
```

Para este archivo, el rango esperado es `2024-09-23` a `2026-09-23` y hay
483 snapshots diarios.

### SBS daily and non-SBS monthly datasets

The assignment datasets are generated from `data/processed/vd_daily.csv` with:

```zsh
uv run python -m src.preprocessing.vd_datasets
```

The command performs the following steps in order:

1. Renames source columns to normalized names immediately after loading.
2. Parses `fecha` from `DD/MM/YY` to ISO `YYYY-MM-DD`.
3. Excludes rows with missing `fecha` under the no-quota assumption.
4. Adds normalized `id_fondo`, `id_fondo_clase_dim`, and `id_codigo_fondo_clase`.
5. Adds the derived `flujo_neto` measure.
6. Removes duplicate `fecha_reporte` + `nombre_fondo_clase_origen` rows.
7. Keeps only the earliest report for each `nombre_fondo_clase_origen` + `fecha` pair.
8. Writes open SBS rows at the daily grain to `data/processed/fact_fondos_sbs.csv`.
9. Writes open non-SBS rows at the latest available date per month to
   `data/processed/fact_fondos_competencia.csv`.

`id_codigo_fondo_clase` is `CAFCI-<codigo_fondo_cafci>-<codigo_clase_cafci>`
and is retained for source traceability. The monthly grouping key is
`nombre_fondo_clase_origen`, so different classes remain separate.

Both output files contain these 34 normalized columns:

```text
fecha, id_fondo_clase_dim, id_fondo, id_codigo_fondo_clase,
nombre_fondo_clase_origen, nombre_fondo, nombre_clase, tipo_fondo,
tipo_renta, region, tipo_renta_mixta, duracion, benchmark, moneda,
tipo_cliente, vcp_actual, vcp_anterior, variacion_diaria,
reexpresion_pesos, variacion_mensual, variacion_anual,
cantidad_cuotaparte_actual, cantidad_cuotaparte_anterior,
patrimonio_neto_actual, patrimonio_neto_anterior, flujo_neto,
calificacion, sociedad_gestora, comision_ingreso, honorarios_adm_sg,
honorarios_adm_sd, otros_gastos, comision_rescate,
plazo_liquidacion_dias
```

`flujo_neto` is the one derived measure. It follows the workbook definition
`ΔIngresos = (CP₁ − CP₀) × VCP₁`, using the change in `cantidad_cuotaparte_*`
times `vcp_actual`. A missing `cantidad_cuotaparte_anterior` is treated as zero
previous cuotapartes.

### SCD2 fund dimensions

Build the shared class and fund dimensions from both finalized fact datasets:

```zsh
uv run python -m src.preprocessing.vd_dimensions
```

The command writes:

- `data/processed/dim_fondo_clase.csv`: one SCD2 version per class when a class attribute changes.
- `data/processed/dim_fondo.csv`: one SCD2 version per base fund when a fund attribute changes.

Each dimension includes a stable business key, a generated version key, `valid_from`, `valid_to`, and `is_current`. `dim_fondo_clase` keeps each class's actual `moneda`; `dim_fondo` uses the majority class currency for each fund/date. The builder reports any remaining fund-level conflicts.
