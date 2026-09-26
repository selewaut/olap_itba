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

### `dim_time`

One row per calendar date, 2010-03-01 to 2026-12-31.

| Column | Type | Notes |
|---|---|---|
| `date_key` | `DATE` | Primary key |
| `mes_anio` | `INTEGER NOT NULL` | FK to `dim_mes` |
| `anio` | `SMALLINT NOT NULL` | |
| `trimestre` | `SMALLINT NOT NULL` | `CHECK BETWEEN 1 AND 4` |
| `semana_anio` | `SMALLINT NOT NULL` | ISO week, `CHECK BETWEEN 1 AND 53` |
| `es_dia_habil` | `BOOLEAN NOT NULL` | Weekday. Not the same as a market holiday |

The real `DATE` is the key; no integer `fecha_key` is needed. The range covers
the competition fact, which reaches back to 2010, not just the 2024-onward
window the daily facts use.

`semana_anio` is `NOT NULL` on purpose. A `CHECK` passes on NULL, so a nullable
week column would make the range constraint do nothing at all.

### `dim_mes`

One row per month, `YYYYMM` as an integer.

| Column | Type | Notes |
|---|---|---|
| `mes_anio` | `INTEGER` | Primary key, e.g. `202607` |
| `nombre_mes` | `VARCHAR(20) NOT NULL` | |

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

One SCD2 version row per base fund. Named `DetalleFondosTotal` in the schema.

| Column | Type | Notes |
|---|---|---|
| `FondoKey` | `INT` | Surrogate, primary key |
| `IdFondo` | `VARCHAR(80)` | Business key, not unique across versions |
| `ValidoDesde` | `DATE NOT NULL` | SCD2 start |
| `ValidoHasta` | `DATE` | SCD2 end, null while still reported |
| `EsActual` | `BOOLEAN NOT NULL` | TRUE only while the fund is still reported |
| `NombreFondo` | `VARCHAR(80)` | |
| `Region` | `VARCHAR(20)` | Same vocabulary as `dim_fondo.region` in the CSV |
| `TipoFondo` | `VARCHAR(20)` | |
| `TipoRenta` | `VARCHAR(30)` | |
| `TipoRentaMixta` | `VARCHAR(30)` | Nullable |
| `Moneda` | `CHAR(3)` | Majority class currency |
| `Benchmark` | `VARCHAR(20)` | Raw source label, kept next to the resolved key |
| `ObjetivoKey` | `INT` | FK to `DetalleIndice`, null when the label has no matching series |
| `SociedadGestora` | `VARCHAR(80)` | |
| `CantidadClases` | `SMALLINT` | |

`ObjetivoKey` is resolved from `Benchmark` at load time, by matching the label
against the index catalogue. It resolves 248 of 1925 versions. The unmapped
labels are the informative part: `No Registrado` (1095) and `Otro` (509) carry
no benchmark, `30%+70%` is a blend, `MSCI Latam` is not in the catalogue,
`Rofex 20` is a different index we do not carry, and `IAMC` is a bond index.
`A3500` is the dolar oficial code, not an equity index.

Restrictions:

- `UNIQUE (IdFondo, ValidoDesde)`.
- `ValidoHasta >= ValidoDesde` when `ValidoHasta` is not null.
- At most one `EsActual = TRUE` row per `IdFondo`. A fund that stopped being
  reported has none: its last version is closed on its last observed date, so
  324 of 1474 funds have no current row.

### `dim_fondo_clase`

One SCD2 version row per fund/class. Named `dim_detalle_fondo_clase` in the
schema.

| Column | Type | Notes |
|---|---|---|
| `FondoClaseKey` | `INT` | Surrogate, primary key |
| `IdFondoClaseDim` | `VARCHAR(100)` | Business key, not unique across versions |
| `IdFondo` | `VARCHAR(80)` | Base fund business key |
| `IdCodigoFondoClase` | `VARCHAR(20)` | CAFCI traceability |
| `NombreFondoClaseOrigen` | `VARCHAR(90)` | Original source name |
| `NombreFondo` | `VARCHAR(80)` | |
| `NombreClase` | `VARCHAR(50)` | |
| `ValidoDesde` | `DATE NOT NULL` | SCD2 start |
| `ValidoHasta` | `DATE` | SCD2 end, null while still reported |
| `EsActual` | `BOOLEAN NOT NULL` | TRUE only while the class is still reported |
| `Calificacion` | `VARCHAR(20)` | Nullable, 147 distinct source values |
| `TipoCliente` | `VARCHAR(20)` | |
| `ComisionIngreso` | `NUMERIC(12,4)` | |
| `HonorariosAdmSg` | `NUMERIC(12,4)` | |
| `HonorariosAdmSd` | `NUMERIC(12,4)` | |
| `OtrosGastos` | `NUMERIC(12,4)` | |
| `ComisionRescate` | `NUMERIC(12,4)` | |
| `Moneda` | `CHAR(3)` | The class's actual currency |
| `FondoKey` | `INT` | FK to `DetalleFondosTotal` |

A class version is cut wherever its fund changes version, so a class version
never spans two fund versions. That makes the parent unambiguous: every class
version resolves to exactly one fund version by date containment, which is what
lets the facts carry a surrogate instead of a date-range join.

Restrictions:

- `UNIQUE (IdFondoClaseDim, ValidoDesde)`.
- `ValidoHasta >= ValidoDesde` when `ValidoHasta` is not null.
- At most one `EsActual = TRUE` row per `IdFondoClaseDim`. 1275 of 5166
  classes have none, for the same reason as their funds.

### `fact_fondos_sbs`

Daily grain, one row per class version per business day. 41034 rows.

| Column | Type | Notes |
|---|---|---|
| `FondoClaseKey` | `INT NOT NULL` | FK to the class version valid on that date |
| `IdFondoClaseDim` | `VARCHAR(100) NOT NULL` | Business key, degenerate dimension, no FK |
| `IdFondo` | `VARCHAR(80) NOT NULL` | |
| `Fecha` | `DATE NOT NULL` | FK to `dim_time` |
| `VcpActual` / `VcpAnterior` | `NUMERIC(20,3)` | |
| `ReexpresionPesos` | `NUMERIC(20,3)` | |
| `VariacionDiaria` / `Mensual` / `Anual` | `NUMERIC(14,3)` | Percent |
| `CantidadCuotaparteActual` / `Anterior` | `NUMERIC(20,4)` | |
| `PatrimonioNetoActual` / `Anterior` | `NUMERIC(20,2)` | |
| `FlujoNeto` | `DOUBLE PRECISION` | Derived, see below |

`PRIMARY KEY (FondoClaseKey, Fecha)`.

`FondoClaseKey` is resolved at load time by finding the class version whose
`[ValidoDesde, ValidoHasta]` contains the row's date, so a historical row keeps
pointing at the attributes that were true then. Every one of the 41034 rows
resolves to exactly one version.

`FlujoNeto` is the only measure not in the source workbook:
`(cantidad_cuotaparte_actual - cantidad_cuotaparte_anterior) * vcp_actual`, with
a missing previous quantity treated as zero. It reaches 1.6e14 with 15 decimal
places, which needs 30 digits, so it is stored as `DOUBLE PRECISION`; the extra
decimals are float noise from the multiplication. Rounding it in preprocessing
would allow `NUMERIC(20,2)`.

The fact keeps 15 of the 34 CSV columns. The 18 descriptive ones (`tipo_fondo`,
`region`, `benchmark`, `moneda`, the fees, `plazo_liquidacion_dias`, and the
names) live in the class dimension and are reachable by join.

### `fact_fondos_competencia`

Monthly grain, same 16 columns plus `MesAno`. 85871 rows.

| Column | Type | Notes |
|---|---|---|
| `FondoClaseKey` | `INT NOT NULL` | As above |
| `IdFondoClaseDim` | `VARCHAR(100) NOT NULL` | |
| `IdFondo` | `VARCHAR(80) NOT NULL` | |
| `Fecha` | `DATE NOT NULL` | FK to `dim_time` |
| `MesAno` | `INTEGER NOT NULL` | FK to `dim_mes`, derived from `Fecha` |
| *measures* | as in `fact_fondos_sbs` | |

`PRIMARY KEY (FondoClaseKey, MesAno)`.

`Fecha` is not part of the key. A month holds up to 14 different `Fecha` values,
because the source reports the competition on varying days; the fact keeps one
row per class per month and records which of those dates it came from. `MesAno`
is derived from `Fecha` at load time, so the two cannot disagree.

### `CotizacionIndices`

One row per date and per detail series, at two granularities. 4995 rows.

| Column | Type | Notes |
|---|---|---|
| `CotizacionKey` | `BIGINT` | Identity, primary key |
| `Fecha` | `DATE` | Null for monthly series, FK to `dim_time` |
| `MesAno` | `INTEGER` | Null for daily series, FK to `dim_mes` |
| `IndiceDetalladoKey` | `INT NOT NULL` | FK to `DetalleIndice` |
| `Valor` | `NUMERIC(24,16)` | |
| `Frecuencia` | `CHAR(1) NOT NULL` | `D` or `M` |

`CONSTRAINT chk_xor CHECK ((Fecha IS NULL) <> (MesAno IS NULL))` enforces that a
row carries exactly one period. The grain cannot live in the primary key for
this reason: PK columns are implicitly `NOT NULL`, which contradicts the XOR.

So the grain is enforced by two unique indexes instead, one per granularity:

```sql
CREATE UNIQUE INDEX uq_cot_diario  ON CotizacionIndices (Fecha, IndiceDetalladoKey);
CREATE UNIQUE INDEX uq_cot_mensual ON CotizacionIndices (MesAno, IndiceDetalladoKey);
```

This works because Postgres treats NULLs as distinct in a unique index, so each
index skips the rows belonging to the other granularity. Do not add
`NULLS NOT DISTINCT`; it would make every monthly row collide with the next.

`Frecuencia` is redundant with `Indice.Frecuencia` and is present so the fact can
be filtered without joining. Validate that the two always agree.

Scale note: `IPC_VAR` arrives from INDEC as a fraction (`0.0347` = 3.47%) and is
stored already scaled to percent, so every `Porcentaje` series reads on the same
0-100 scale. See `A_PORCENTAJE` in `src/preprocessing/clean.py`.

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
| Time | `dim_time` | Simplified to a real DATE key |

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

## Joins

### Fund fact to fund dimension

The facts carry the class version surrogate, so no date-range join is needed
for the class dimension:

```text
fact_fondos_*.FondoClaseKey  -> dim_detalle_fondo_clase.FondoClaseKey
dim_detalle_fondo_clase.FondoKey -> DetalleFondosTotal.FondoKey
```

To go from a class to its fund's descriptive attributes, join the surrogate and
then use `EsActual`, keeping in mind that a key which stopped being reported has
no current row. For a historical view, join on the validity interval instead:

```text
dimension.ValidoDesde <= fact.Fecha
  AND (dimension.ValidoHasta >= fact.Fecha OR dimension.ValidoHasta IS NULL)
```

### Date and month joins

```text
fact_fondos_*.Fecha     -> dim_time.date_key
CotizacionIndices.Fecha -> dim_time.date_key
CotizacionIndices.MesAno, fact_fondos_competencia.MesAno -> dim_mes.mes_anio
```

### Index quotation joins

```text
CotizacionIndices.IndiceDetalladoKey -> DetalleIndice.IndiceDetalladoKey
DetalleIndice.IndiceKey              -> Indice.IndiceKey
DetalleFondosTotal.ObjetivoKey       -> DetalleIndice.IndiceDetalladoKey
```

## Validation

`sql/dw_load.sql` runs these at the end of the load. Each must return zero.

1. Fact row counts match the generated CSV row counts.
2. No fact primary keys are duplicated.
3. Every `Fecha` exists in `dim_time`, and every `MesAno` in `dim_mes`.
4. Every `IndiceDetalladoKey` in the facts and in `DetalleFondosTotal` exists
   in `DetalleIndice`.
5. `DetalleIndice.IndiceKey` exists in `Indice`.
6. The degenerate `IdFondoClaseDim` on each fact row matches the class version
   the surrogate points at. This is the check that catches a bad load join.
7. `SCD2 intervals have ValidoHasta >= ValidoDesde`.
8. Each SCD2 key has at most one current row.
9. Every class version resolves to exactly one fund version, so
   `dim_detalle_fondo_clase.FondoKey` is null only where no fund version covers
   the class period.
10. `CotizacionIndices` holds exactly one of `Fecha` or `MesAno` per row, and no
    duplicate within a granularity.

Current results on the generated data: 85871 competition rows, 41034 SBS rows,
11945 class versions, 1925 fund versions, 4995 quotation rows, 248 fund
versions with a resolved `ObjetivoKey`, 0 orphans, 0 duplicate keys.

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

