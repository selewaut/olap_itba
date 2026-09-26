# Plan: fund and fund/class dimension datasets

## Status

Implemented in `src/preprocessing/vd_dimensions.py`. The generated dimensions are `data/processed/dim_fondo_clase.csv` and `data/processed/dim_fondo.csv`. The source fact CSVs and raw VD archive remain unchanged.

## 1. Objective

Build two shared dimension datasets for both the SBS daily dataset and the non-SBS monthly dataset:

1. `dim_fondo_clase.csv`: one row per fund/class.
2. `dim_fondo.csv`: one row per base fund, aggregating all of its classes.

The dimensions will be built from the union of:

- `data/processed/fact_fondos_sbs.csv`
- `data/processed/fact_fondos_competencia.csv`

The same dimension row can therefore serve either fact dataset. The fact datasets remain separate because they have different grains and SBS/non-SBS populations.

## 2. Current identity fields

The current outputs provide these identity fields:

- `nombre_fondo_clase_origen`: original fund-plus-class name.
- `nombre_clase`: class suffix, such as `Clase A`; for a single-class fund it falls back to `nombre_fondo_clase_origen`.
- `id_fondo`: base fund name without the class suffix or separator.
- `id_codigo_fondo_clase`: `CAFCI-<Código Fondo CAFCI>-<Código Clase CAFCI>`.

`id_codigo_fondo_clase` is useful for traceability, but it is not unique enough to be the only dimension key: the current data contains CAFCI code pairs mapped to multiple names. The dimension key must preserve the fund/class identity without collapsing different names.

## 3. `dim_fondo_clase` proposal

### Grain

One row per unique fund/class identity across both SBS and non-SBS data.

### Proposed columns

| Column | Source or derivation | Purpose |
|---|---|---|
| `sk_fondo_clase` | Generated surrogate key for this SCD2 version | Warehouse version key. Dropped from the CSV; the warehouse assigns it at load time |
| `id_fondo_clase_dim` | Deterministic key from normalized `id_fondo` + `nombre_clase` | Stable business key across versions |
| `valid_from` | First normalized `fecha` for this version | SCD2 start date |
| `valid_to` | Day before the next version, empty while still reported | SCD2 end date |
| `is_current` | Whether the key is still being reported | SCD2 current flag |
| `id_fondo` | Link to `dim_fondo` | Fund relationship |
| `id_codigo_fondo_clase` | Existing generated column | CAFCI traceability |
| `nombre_fondo_clase_origen` | `nombre_fondo_clase_origen` | Original source label |
| `nombre_fondo` | `id_fondo` | Base fund name |
| `nombre_clase` | `nombre_clase` | Class name or single-class fallback |
| `calificacion` | `Calificacion` | Class/fund credit rating |
| `comision_ingreso` | `Comisión Ingreso` | Entry fee |
| `honorarios_adm_sg` | `Honorarios Adm. SG` | Manager fee |
| `honorarios_adm_sd` | `Honorarios Adm. SD` | Depositary fee |
| `otros_gastos` | `Otros Gastos` | Other expenses |
| `comision_rescate` | `Comisión Rescate` | Redemption fee |
| `moneda` | `Moneda` | Actual class/share currency |
| `tipo_cliente` | `Clase de Cuota` | General/No Registrada/Mayorista classification |

`tipo_cliente` is included as a class dimension attribute and is not a financial metric in the fact table.

## 4. `dim_fondo` proposal

### Grain

One row per unique base fund. All classes of the same base fund are grouped together.

### Proposed columns

| Column | Source or derivation | Purpose |
|---|---|---|
| `sk_fondo` | Generated surrogate key for this SCD2 version | Warehouse version key. Dropped from the CSV; the warehouse assigns it at load time |
| `id_fondo` | Stable fund key to be approved | Stable business key across versions |
| `valid_from` | First normalized `fecha` for this version | SCD2 start date |
| `valid_to` | Day before the next version, empty while still reported | SCD2 end date |
| `is_current` | Whether the key is still being reported | SCD2 current flag |
| `nombre_fondo` | `id_fondo` | Base fund name |
| `region` | `Región` | Geographic attribute |
| `tipo_fondo` | `Tipo de Fondo` | Open/closed classification |
| `tipo_renta` | `Tipo de Renta` | Fund income type |
| `tipo_renta_mixta` | `Tipo de Renta Mixta` | Mixed-income flag/type |
| `benchmark` | `Benchmark` | Benchmark |
| `moneda` | Majority of class `Moneda` values for each fund/date | Fund-level summary currency |
| `sociedad_gestora` | `Sociedad Gerente` | Management company |
| `cantidad_clases` | Count of distinct classes | Fund-level summary |

The fund dimension will not contain `nombre_clase` or `nombre_fondo_clase_origen` as separate attributes because those are class-level values. Those belong in `dim_fondo_clase`; the class dimension relates to the fund dimension through `id_fondo`.

## 5. Fund key decision

There are two possible fund keys:

### Option A: current name-based key

Use the current name-based `id_fondo` as `id_fondo`.

Advantages:

- Simple for this assignment.
- The current data has 1,498 unique cleaned `id_fondo` names.
- No additional raw source processing is required.

Risk:

- A future rename, spelling change, or accent change creates a new key.

### Option B: CAFCI fund-code key

Use the CAFCI fund code as `id_fondo`, preferably sourced from the original raw data before the final projection.

Advantages:

- More stable when the descriptive name changes.
- Better warehouse practice.

Risk:

- The current data contains fund/class names associated with more than one CAFCI code in some cases.
- The dimension builder must report and resolve those conflicts explicitly.

Recommended for the assignment: use a clear name-based `id_fondo` if simplicity is more important, and retain `id_codigo_fondo_clase` for traceability. Use the CAFCI code as the preferred key only if the raw source code is preserved and conflicts are handled.

## 6. Combining SBS and non-SBS data

The dimension files will be built from the union of both fact datasets:

- Do not create separate SBS and non-SBS copies of the same dimension row.
- Deduplicate the class dimension by `id_fondo_clase_dim`.
- Deduplicate the fund dimension by `id_fondo`.
- Verify that the union covers every fund/class used by either fact dataset.
- Report any attribute conflict between SBS and non-SBS rows.

`sociedad_gestora` will remain an attribute of the fund dimension. It is not necessary to add an SBS flag to the dimension because each fact dataset already has its own population.

## 7. Attribute consistency rules

Before writing the dimensions, validate that attributes expected at fund level are consistent across all classes:

- `region`
- `tipo_fondo`
- `tipo_renta`
- `tipo_renta_mixta`
- `moneda`
- `benchmark`
- `sociedad_gestora`

If the same base fund has conflicting values, the builder will:

1. Report the fund and conflicting values.
2. Avoid silently choosing a value without documenting it.
3. Use a deterministic first-value rule only if approved.

Class-level attributes such as `calificacion`, fees, `moneda`, and `tipo_cliente` remain in `dim_fondo_clase` and may differ between classes.

## 8. Validation outputs

The dimension build will report:

- Number of unioned source rows.
- Number of unique fund/class identities.
- Number of unique base funds.
- Number of classes aggregated per fund.
- CAFCI code pairs mapped to multiple names.
- Base funds with conflicting fund-level attributes.
- Fund/class rows missing a proposed dimension key.
- Rows covered by only one of the two fact datasets.

## 9. Proposed files after approval

- `data/processed/dim_fondo_clase.csv`
- `data/processed/dim_fondo.csv`

The source fact CSVs and the raw VD archive will not be modified.

## 10. SCD Type 2 impact

The current union of the daily SBS and monthly non-SBS fact datasets contains
changes in class and fund attributes. The dimension plan should therefore use
SCD Type 2: each row represents one observed attribute version, with validity
metadata such as `valid_from`, `valid_to`, and `is_current`.

Using normalized name-based keys (`id_fondo + nombre_clase` for classes and
`id_fondo` for funds), the generated SCD2 row counts are:

| Dimension | Static current rows | SCD2 version rows | Increase |
|---|---:|---:|---:|
| `dim_fondo_clase` | 5,166 | 10,637 | 5,471 (+105.9%) |
| `dim_fondo` | 1,474 | 1,925 | 451 (+30.6%) |
| **Total** | **6,640** | **12,562** | **5,922 (+89.2%)** |

The class SCD2 count compares each ordered class observation with the previous
version and creates a new version whenever a tracked class attribute changes,
including `moneda`. The fund count collapses each fund/date to one row, computes
the majority class currency, and then compares fund versions over time. With
currency handled this way, the script reports zero unresolved fund-level
attribute conflicts.

SCD2 rows are created only when a tracked dimension attribute changes; they do
not create a new row for every fact observation. The validity columns add
metadata but do not materially increase the row count.


## 11. Simple SCD2 build rule

The implementation will use a simple Type 2 history:

1. Build one shared class dimension from the union of both fact datasets.
2. Sort class rows by `id_fondo_clase_dim` and normalized `fecha`.
3. Compare each row with the previous row for that class.
4. If any class attribute changed, close the previous version and create a new
   version with the same class key.
5. Build the fund dimension at one row per base fund and `fecha`.
6. Use the majority class currency for the fund-level `moneda`; retain each
   class's actual currency in `dim_fondo_clase`.
7. Store `valid_from`, `valid_to`, and `is_current` for each version.
8. Cut a class version wherever its fund changes version, so a class version
   never spans two fund versions and always has a single parent to reference.
9. Close a key's last version on its last observed date, so `is_current` means
   "still being reported" rather than "is the last version we happen to have".

`valid_from` is the first normalized `fecha` where the attribute combination is
observed. `valid_to` is the day before the next version's `valid_from`. For a
key that is still being reported the last version stays open and `valid_to` is
empty, which is the only case where `is_current` is TRUE. A key that dropped out
of the source has its last version closed on the date it was last seen, so it
has no current row at all: 324 of 1474 funds and 1275 of 5166 classes. The
dimension key remains stable across versions; a new version gets a separate
dimension-version key.

Queries that need "the attributes as of today" must therefore test both
`is_current` and the key's presence, and queries that need the attributes as of
a past date should join on the validity interval rather than on `is_current`.

The fact CSVs do carry the SCD surrogate key. Each fact row resolves the class
version that was valid on that row's `fecha`, so a historical fact row keeps
pointing at the attributes that were true at the time.

## 12. Decisions and implementation choices

1. `id_fondo_clase_dim` is the readable deterministic composite `id_fondo|nombre_clase`; `id_codigo_fondo_clase` remains traceability metadata.
2. `id_fondo` uses the current name-based `id_fondo` for this assignment.
3. `tipo_cliente` from `Clase de Cuota` is included in `dim_fondo_clase`.
4. `calificacion` remains class-level.
5. Fund-level `moneda` uses the majority class currency; other fund-level attributes are consistent in the current data.
