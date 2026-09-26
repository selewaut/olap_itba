# Plan: simple PostgreSQL data warehouse

## Goal

Load the generated fund facts, fund dimensions, and index quotations into a small PostgreSQL relational model. Keep the first version simple enough for a master's assignment.

No tables or SQL objects are created by this plan.

## Source files

| CSV | PostgreSQL table |
|---|---|
| `data/processed/fact_fondos_sbs.csv` | `fact_fondos_sbs` |
| `data/processed/fact_fondos_competencia.csv` | `fact_fondos_competencia` |
| `data/processed/dim_fondo.csv` | `dim_fondo` |
| `data/processed/dim_fondo_clase.csv` | `dim_fondo_clase` |
| `data/processed/fact_cotizacion.csv` | `fact_cotizacion_indice` |
| `data/processed/dim_indice.csv` | `dim_indice` |
| `data/processed/dim_indice_detalle.csv` | `dim_indice_detalle` |

## Final tables

### `dim_fecha`

One row per date.

| Column | Type | Rule |
|---|---|---|
| `fecha` | `DATE` | Primary key |
| `anio` | `SMALLINT` | Derived |
| `mes` | `SMALLINT` | Derived |
| `dia` | `SMALLINT` | Derived |
| `trimestre` | `SMALLINT` | Derived |
| `semana_anio` | `SMALLINT` | Derived |
| `nombre_mes` | `VARCHAR(15)` | Derived |

For this assignment, use the real `DATE` as the date key. No integer `fecha_key` is required.

### `dim_mes`

One row per month.

| Column | Type | Rule |
|---|---|---|
| `periodo_mes` | `DATE` | First day of month, primary key |
| `anio` | `SMALLINT` | Derived |
| `mes` | `SMALLINT` | Derived |
| `nombre_mes` | `VARCHAR(15)` | Derived |

### `dim_indice`

One row per index, at the generic level. An index can be expressed more than one
way (in another currency, or as a monthly variation); those are separate rows in
`dim_indice_detalle`, so this table is the parent of 11 indices covering 13 series.

| Column | Type | Source |
|---|---|---|
| `codigo_indice` | `VARCHAR(40)` | `codigo_indice`, primary key |
| `nombre_indice` | `VARCHAR(120)` | `nombre_indice` |
| `region` | `VARCHAR(40)` | `region`; same vocabulary as `dim_fondo.region` |
| `tipo_indice` | `VARCHAR(40)` | `tipo_indice` |
| `frecuencia` | `CHAR(1)` | `D` or `M`; inherited by all of the index's details |

`tipo_indice` has five values:

| Value | Indices |
|---|---|
| `Indice de precios` | IPC, IPIM, IPIB |
| `Cambio` | DOLAR_OFICIAL, DOLAR_CCL |
| `Indice bursatil` | MERVAL, BOVESPA |
| `Indice oficial` | CER, UVA |
| `Tasa` | TAMAR, BADLAR |

### `dim_indice_detalle`

One row per concrete series, at the leaf level. This is the grain of
`fact_cotizacion_indice`. Two indices have more than one detail:

- `MERVAL` -> `MERVAL_ARS`, `MERVAL_USD` (same unit, two currencies)
- `IPC` -> `IPC`, `IPC_VAR` (same currency, two units)

| Column | Type | Source |
|---|---|---|
| `indice_detalle_key` | `VARCHAR(40)` | `indice_detalle_key`, primary key |
| `codigo_indice` | `VARCHAR(40)` | foreign key to `dim_indice` |
| `nombre` | `VARCHAR(120)` | index name plus currency or variant |
| `moneda` | `CHAR(3)` | `moneda` |
| `unidad` | `VARCHAR(40)` | `unidad` |
| `fuente` | `VARCHAR(120)` | `fuente` |

`unidad` and `moneda` live here rather than on `dim_indice` because they describe
the series, not the index. The two `IPC` details have different units
(`Puntos de indice` vs `Porcentaje`), which a parent-level column could not express.

`unidad` has three values: `Tasa de cambio`, `Puntos de indice`, `Porcentaje`.

### `dim_fondo`

One SCD2 version row per base fund.

| Column | Type | Source |
|---|---|---|
| `sk_fondo` | `VARCHAR(40)` | `sk_fondo`, primary key |
| `id_fondo` | `VARCHAR(200)` | Business key, not unique across SCD2 versions |
| `valid_from` | `DATE` | SCD2 start |
| `valid_to` | `DATE` | SCD2 end, nullable |
| `is_current` | `BOOLEAN` | Current-version flag |
| `nombre_fondo` | `VARCHAR(200)` | Fund name |
| `region` | `VARCHAR(80)` | Region |
| `tipo_fondo` | `VARCHAR(40)` | Fund type |
| `tipo_renta` | `VARCHAR(80)` | Income type |
| `tipo_renta_mixta` | `VARCHAR(40)` | Nullable |
| `moneda` | `VARCHAR(10)` | Majority class currency |
| `benchmark` | `VARCHAR(80)` | Benchmark |
| `sociedad_gestora` | `VARCHAR(200)` | Manager |
| `cantidad_clases` | `INTEGER` | Number of classes |

Restrictions:

- `UNIQUE (id_fondo, valid_from)`.
- `valid_to >= valid_from` when `valid_to` is not null.
- One `is_current = TRUE` row per `id_fondo`.

### `dim_fondo_clase`

One SCD2 version row per fund/class.

| Column | Type | Source |
|---|---|---|
| `sk_fondo_clase` | `VARCHAR(40)` | `sk_fondo_clase`, primary key |
| `id_fondo_clase_dim` | `VARCHAR(300)` | Fund/class business key |
| `id_fondo` | `VARCHAR(200)` | Base fund business key |
| `id_codigo_fondo_clase` | `VARCHAR(80)` | CAFCI traceability |
| `nombre_fondo_clase_origen` | `VARCHAR(250)` | Original source name |
| `nombre_fondo` | `VARCHAR(200)` | Base fund name |
| `nombre_clase` | `VARCHAR(120)` | Class name |
| `valid_from` | `DATE` | SCD2 start |
| `valid_to` | `DATE` | SCD2 end, nullable |
| `is_current` | `BOOLEAN` | Current-version flag |
| `calificacion` | `VARCHAR(80)` | Rating |
| `tipo_cliente` | `VARCHAR(40)` | Client/category type |
| `comision_ingreso` | `NUMERIC(12,6)` | Entry fee |
| `honorarios_adm_sg` | `NUMERIC(12,6)` | Manager fee |
| `honorarios_adm_sd` | `NUMERIC(12,6)` | Depositary fee |
| `otros_gastos` | `NUMERIC(12,6)` | Other expenses |
| `comision_rescate` | `NUMERIC(12,6)` | Redemption fee |
| `moneda` | `VARCHAR(10)` | Actual class currency |

Restrictions:

- `UNIQUE (id_fondo_clase_dim, valid_from)`.
- `valid_to >= valid_from` when `valid_to` is not null.
- One `is_current = TRUE` row per `id_fondo_clase_dim`.

### `fact_fondos_sbs`

The fact table keeps the 34 normalized CSV columns so the CSV can be loaded directly. Important measures are:

- `patrimonio_neto_actual`
- `patrimonio_neto_anterior`
- `flujo_neto`
- `vcp_actual`
- `vcp_anterior`
- `cantidad_cuotaparte_actual`
- `cantidad_cuotaparte_anterior`
- `variacion_diaria`
- `variacion_mensual`
- `variacion_anual`
- `reexpresion_pesos`

`flujo_neto` is the only measure not present in the source workbook. It is
materialized in the CSV using `ΔIngresos = (CP₁ − CP₀) × VCP₁`, that is
`(cantidad_cuotaparte_actual - cantidad_cuotaparte_anterior) * vcp_actual`, with a
missing previous quantity treated as zero.

Identity columns are:

- `fecha`
- `id_fondo_clase_dim`
- `id_fondo`
- `id_codigo_fondo_clase`

Use `PRIMARY KEY (fecha, id_fondo_clase_dim)`.

The fact also keeps current denormalized attributes (`benchmark`, `moneda`, `sociedad_gestora`) because the current load is intentionally simple.

### `fact_fondos_competencia`

Use the same 34 columns as `fact_fondos_sbs`, loaded from the monthly competition CSV.

Add or derive:

- `periodo_mes` as the first day of the month from `fecha`.
- Use `PRIMARY KEY (periodo_mes, id_fondo_clase_dim)`.

### `fact_cotizacion_indice`

One row per date and per detail series.

| Column | Type | Source |
|---|---|---|
| `fecha` | `DATE` | `fecha` |
| `indice_detalle_key` | `VARCHAR(40)` | `indice_detalle_key`, foreign key to `dim_indice_detalle` |
| `valor` | `NUMERIC(24,6)` | `valor` |
| `frecuencia` | `CHAR(1)` | `D` or `M` |

Use `PRIMARY KEY (fecha, indice_detalle_key)`.

`frecuencia` is redundant with `dim_indice.frecuencia` and is present so the fact
can be filtered without joining. Validate the two always agree.

Scale note: `IPC_VAR` arrives from INDEC as a fraction (`0.0347` = 3.47%) and is
stored already scaled to percent, so every `Porcentaje` series in the fact reads on
the same 0-100 scale. See `A_PORCENTAJE` in `src/preprocessing/clean.py`.

## Compatibility with the draft model

| Draft table | PostgreSQL table | Compatibility |
|---|---|---|
| Fondos SBS | `fact_fondos_sbs` | Direct match |
| Fondos Competencia | `fact_fondos_competencia` | Direct match; monthly period derived from `fecha` |
| Cotizacion Indices | `fact_cotizacion_indice` | Direct match |
| Detalle Fondos Total | `dim_fondo` | Direct match for available fund attributes |
| Detalle Fondos Clase | `dim_fondo_clase` | Direct match for available class attributes |
| Indice | `dim_indice` | Generic level; 11 indices |
| Detalle Indice | `dim_indice_detalle` | Leaf level; 13 series, one per fact row |
| Mes | `dim_mes` | Derived from dates |
| Time | `dim_fecha` | Simplified to date key |

Not available in the generated data:

- `monto_minimo`
- separate `flujos` (partially covered by the derived `flujo_neto` measure)
- separate `rendimientos`
- a separate fund `pais` field; use `region`
- a separate index-detail table

## Setting up the database

Two scripts, run in this order. The whole load takes about two seconds.

```bash
brew services start postgresql@18          # o el servicio de Postgres que uses
cd /ruta/al/repo
uv run python -m src.preprocessing.clean   # genera data/processed/*.csv
uv run python -m src.preprocessing.vd_datasets
uv run python -m src.preprocessing.vd_dimensions

createdb fci_dw
psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/tablas_fondos.sql
psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/dw_load.sql
```

`tablas_fondos.sql` creates the nine tables, keys, restrictions and indexes.
`dw_load.sql` fills them and finishes with the validation queries, which must
all return zero.

To connect DBeaver: driver PostgreSQL, host `localhost`, port `5432`, database
`fci_dw`, user = your local username, password empty. The local `pg_hba.conf`
uses `trust`, so no password is asked for.

## Loading approach

- `sql/tablas_fondos.sql`: creates the final tables, keys, restrictions, and indexes.
- `sql/dw_load.sql`: loads the CSVs and runs the validation queries.

The load is not idempotent: it inserts, so it expects empty tables. To reload,
drop and recreate the database rather than adding a `TRUNCATE`, because
`TRUNCATE ... CASCADE` on one dimension silently empties the facts.

```bash
dropdb --force fci_dw
createdb fci_dw
psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/tablas_fondos.sql
psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/dw_load.sql
```

`--force` is needed while a GUI client holds a session open; without it the
drop fails with `database is being accessed by other users`.

Every CSV is copied into a `TEMP` staging table that mirrors its header, then
projected into the final table. The final tables keep fewer columns than the
fact CSVs, and the staging table exists to absorb the difference: `\copy` maps
columns by position, so the staging table must carry the full header in the
CSV's exact order.

No staging tables are needed for this assignment. The final fact tables are intentionally shaped like their normalized CSVs so `\\copy` can load them directly.

## Joins

### Fund fact to fund dimension

```text
fact_fondos_*.id_fondo
    -> dim_fondo.id_fondo

fact_fondos_*.id_fondo_clase_dim
    -> dim_fondo_clase.id_fondo_clase_dim
```

Because the dimensions are SCD2, add the date condition:

```text
fact.fecha BETWEEN dimension.valid_from
              AND COALESCE(dimension.valid_to, DATE '9999-12-31')
```

### Date and month joins

```text
fact_fondos_*.fecha -> dim_fecha.fecha
fact_fondos_competencia.periodo_mes -> dim_mes.periodo_mes
```

### Index quotation joins

```text
fact_cotizacion_indice.indice_detalle_key -> dim_indice_detalle.indice_detalle_key
dim_indice_detalle.codigo_indice -> dim_indice.codigo_indice
fact_cotizacion_indice.fecha -> dim_fecha.fecha
```

## Validation

The load is successful when:

1. Fact row counts match the generated CSV row counts.
2. No fact primary keys are duplicated.
3. Every fact date exists in `dim_fecha`.
4. Every monthly period exists in `dim_mes`.
5. Every `indice_detalle_key` in the quotation fact exists in `dim_indice_detalle`.
6. Every `codigo_indice` in `dim_indice_detalle` exists in `dim_indice`.
7. The fact's `frecuencia` always matches `dim_indice.frecuencia` for the parent index.
8. Every fact `id_fondo` exists in the fund dimension business-key set.
9. Every fact `id_fondo_clase_dim` exists in the class dimension business-key set.
10. SCD2 intervals have `valid_to >= valid_from`.
11. Each SCD2 business key has exactly one current row.
12. Financial values load as `NUMERIC` without conversion errors.

## Sharing the database with the professor

Use two kinds of SQL artifacts:

1. `sql/tablas_fondos.sql`: version-controlled schema script without local data. It is the reproducible definition of the tables, keys, indexes, and restrictions.
2. `sql/dw_full.sql`: generated self-contained dump containing both schema and data. This is the easiest artifact for the professor to restore.

Generate the full dump after loading and validating the local database:

```zsh
pg_dump --format=plain --no-owner --no-privileges --inserts \\
  --file=sql/dw_full.sql fci_dw
```

The professor restores it with:

```zsh
createdb fci_dw
psql -d fci_dw -f sql/dw_full.sql
```

`dw_full.sql` should be generated with the same PostgreSQL major version used for the assignment. The dump should not contain local usernames, passwords, ownership commands, or machine-specific absolute paths.

For reproducibility, share:

- `sql/tablas_fondos.sql`
- `sql/dw_load.sql`
- `sql/dw_full.sql`
- the generated CSV files, if the professor needs to rebuild from raw data

The full dump is the quickest option; the schema plus load scripts demonstrate the data-loading process.

## Status

Done:

1. Two-level index dimension: `Indice` (11 rows) and `DetalleIndice` (13).
2. `CotizacionIndices` with mixed granularity: `Fecha` for daily series, `MesAno` for monthly, enforced by `chk_xor` plus one unique index per granularity.
3. SCD2 fund and class dimensions, with class versions cut at the fund's version boundaries so every class version sits inside exactly one fund version.
4. The two fund facts, keyed on the class version surrogate resolved by date containment.
5. `sql/tablas_fondos.sql` and `sql/dw_load.sql`, loadable in about two seconds.

