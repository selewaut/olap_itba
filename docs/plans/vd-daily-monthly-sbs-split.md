# Plan: SBS daily and non-SBS monthly datasets

## Status

Implemented in `src/preprocessing/vd_datasets.py`. The generated outputs are `data/processed/fact_fondos_sbs.csv` and `data/processed/fact_fondos_competencia.csv`. The source CSV and the original `VD.zip` remain unchanged.

## 1. Input and initial validation results

- Input: `data/processed/vd_daily.csv`.
- The input contains `1,793,254` rows across `483` report dates.
- The report-date range is `2024-09-23` through `2026-09-23`.
- `Tipo de Fondo` contains `Abierto` and `Cerrado`.
- Open-fund rows: `1,777,354`.
- SBS manager rows among open funds: `41,361`.
- Non-SBS manager rows among open funds: `1,735,993`.
- Case-insensitive matching of `Sociedad Gerente` against `SBS` returns exactly one unique value:
  - `SBS Asset Management S.A.S.G.F.C.I.`
- The approved classification rule is exact equality with `Sociedad Gerente == "SBS Asset Management S.A.S.G.F.C.I."`.
- `Fecha` currently uses `DD/MM/YY`, for example `23/09/24`. The observed source format is not `YYYY/MM/DD`.
- There are `1,792,658` non-empty `Fecha` values and `596` missing values.
- The first validation of one row per `fecha_reporte` and `Fondos` found:
  - `4` duplicated groups.
  - `8` rows in those groups.
  - The four groups are exact duplicate pairs for `Pionero Money Market Dólar - Clase D` and `Pionero Money Market Dólar - Clase E` on `2026-03-06` and `2026-03-09`.
- If `Fondo` means the base `fondoId`, one row per report date is not expected because a base fund can have multiple classes. The uniqueness check will use the normalized original `Fondos` value, which preserves the fund-plus-class identity.
- The current input does not yet pass the requested one-row-per-report-date-per-`Fondos` validation and must be de-duplicated before output generation.
- There are `2,755` `FondoClase` x `Fecha` pairs repeated across different `fecha_reporte` values, producing `122,483` extra report observations. These occur in both fund types: `2,374` repeated pairs are `Abierto` and `373` are `Cerrado`. This confirms that the condition is not limited to rows explicitly marked `Cerrado`; a fund can remain marked `Abierto` after its last available data date.

## 2. Output datasets

The two output datasets are intentionally different populations:

### Daily SBS dataset

Contains only rows classified as SBS:

```text
Tipo de Fondo == "Abierto"
and Sociedad Gerente == "SBS Asset Management S.A.S.G.F.C.I."
```

- No non-SBS rows will be included.
- No monthly reduction is performed.
- The output remains at the available daily observation grain.

### Monthly non-SBS dataset

Contains only rows classified as non-SBS:

```text
Tipo de Fondo == "Abierto"
and Sociedad Gerente != "SBS Asset Management S.A.S.G.F.C.I."
```

- No SBS rows will be included.
- Monthly selection is performed after date normalization and de-duplication.
- The output contains one selected source row per fund/class and calendar month.

Blank or null `Sociedad Gerente` values are treated as non-SBS unless a different rule is approved.

## 3. Date normalization before date operations

Dates will be normalized before filtering, grouping, de-duplication, or monthly selection.

### `Fecha`

The source `Fecha` column is observed in `DD/MM/YY` format, not `YYYY/MM/DD`. The approved two-digit-year rule is the standard convention: `00-68` map to `2000-2068` and `69-99` map to `1969-1999`. The preprocessing will:

1. Parse valid values using an unambiguous date parser configured for the observed format.
2. Convert valid values to ISO `YYYY-MM-DD`.
3. Store the normalized result in the analytical `Fecha` column.
4. Preserve the original value internally as `Fecha_original` only for validation and traceability; do not export it.
5. Report missing or invalid values instead of silently coercing them.

The current input has `596` missing `Fecha` values. By approved business assumption, these rows represent funds with no valid quota-part observation and will be excluded from both output datasets before the SBS/non-SBS split. Their `Cantidad de Cuotaparte Actual` values are empty rather than literal numeric zeroes, so the exclusion must be based on missing `Fecha`, not on an equality test against zero.

### `fecha_reporte`

`fecha_reporte` is already in ISO `YYYY-MM-DD` format and will be validated for consistency. It will not be used as the analytical date, as a date filter, or for monthly grouping. It may be retained for provenance and will be used only where explicitly required by the approved duplicate-ordering rule below.

## 4. Derived fund columns

The original `Fondos` column will be preserved. Three derived identity columns will be created before the daily/monthly split: `FondoClase`, `fondoId`, and `idCodigoFondoClase`.

### `FondoClase`

When `Fondos` contains a `Clase` marker:

- `FondoClase` starts at the word `Clase`.
- The word `Clase` and its class identifier are included.
- Surrounding whitespace is removed.

Examples:

```text
Adcap Balanceado I - Clase A -> FondoClase = "Clase A"
Adcap Balanceado I - Clase Ley Nº 27.743 -> FondoClase = "Clase Ley Nº 27.743"
```

When no `Clase` marker is found:

- The fund is treated as having a single class.
- `FondoClase` is set to the normalized original `Fondos` value.

Example:

```text
1810 Mas Ahorro -> FondoClase = "1810 Mas Ahorro"
```

The current source has `31,727` rows without a `Clase` marker across `77` unique `Fondos` values. This fallback must be covered by validation.

### `fondoId`

- For a class-labelled `Fondos` value, `fondoId` is the base fund name before the first `Clase` marker, with the separator before `Clase` removed.
- For a single-class value, `fondoId` is set to the same normalized value as `FondoClase` and the original `Fondos` value.

Example:

```text
Adcap Balanceado I - Clase A -> fondoId = "Adcap Balanceado I"
1810 Mas Ahorro -> fondoId = "1810 Mas Ahorro"
```

The class separator is removed only when a `Clase` marker is present. Legitimate punctuation at the end of a fund name is preserved; the current data has eight such names, including `Optimum FAE (Fondo de Aplicaciones Especiales)`, `Superfondo Renta $`, and names ending in `F.C.I.`.

The logical fund identity is the combination of `fondoId` and `FondoClase`, which is equivalent to the original fund-plus-class `Fondos` value. This prevents different classes of the same fund from being combined.

### `idCodigoFondoClase`

A stable traceability identifier will be added as `idCodigoFondoClase`:

The primary identifier format is:

```text
idCodigoFondoClase = "CAFCI-" + Código Fondo CAFCI + "-" + Código Clase CAFCI
```

- The current source has no missing values in either CAFCI code column.
- If a code is missing in a future input, use `NO-CODE-<sha256>` based on normalized `fondoId` and `FondoClase`.
- `idCodigoFondoClase` is for source-code traceability; `FondoClase` remains the normalized name-based identity because the current data has code pairs mapped to multiple names.

## 5. Initial uniqueness and de-duplication validation

Before generating either output:

1. Normalize `Fecha`.
2. Derive `FondoClase`, `fondoId`, and `idCodigoFondoClase`.
3. Drop full-row duplicates where every source and derived column is identical, keeping one canonical row.
4. Exclude rows where `Fecha` is missing under the approved no-quota assumption.
5. Validate that each `fecha_reporte` has at most one row for each normalized `Fondos` value.
6. Report any duplicate keys before de-duplication.
7. For exact duplicate rows within the same `fecha_reporte` x `Fondos` group, keep one canonical row and drop the redundant copy without changing any values.
8. Re-run the uniqueness validation and require it to pass.

The current input is expected to report the four exact duplicate groups described in Section 1 before de-duplication.

## 6. Repeated observations and closed funds

For a normalized original `Fondos` value x `Fecha` pair observed on different `fecha_reporte` values, the approved rule is:

- Use the original `Fondos` value as the fund identity; the value already includes the class when one is present.
- Sort observations by `fecha_reporte` ascending.
- Keep only the first/earliest report observation.
- Treat later observations with the same `Fondos` value and normalized `Fecha` as repeated data from a fund that is no longer active.
- Use `fecha_reporte` only for this requested duplicate-ordering operation; do not use it for date filtering or monthly selection.

This rule will be applied before the SBS daily and non-SBS monthly split so both outputs are based on the same cleaned source rows. The validation report will show how many repeated pairs and rows were removed.

## 7. Daily SBS selection

After common cleaning:

1. Keep rows where `Fecha` is non-missing after normalization.
2. Keep rows where `Tipo de Fondo == "Abierto"`.
3. Keep rows where `Sociedad Gerente` equals `SBS Asset Management S.A.S.G.F.C.I.`.
4. Keep all valid daily observations without monthly aggregation.
5. Include only the approved final schema, with `Fecha` normalized to ISO format.
6. Do not use `fecha_reporte` for filtering or analytical date calculations.
7. Validate that each `fecha_reporte` has at most one row for each normalized `Fondos` value.

The daily output uses the final 31-column schema documented in Section 10.

## 8. Monthly non-SBS selection

After common cleaning:

1. Keep rows where `Fecha` is non-missing after normalization.
2. Keep rows where `Tipo de Fondo == "Abierto"`.
3. Keep rows where `Sociedad Gerente` is not equal to `SBS Asset Management S.A.S.G.F.C.I.`.
4. Determine the calendar month from the normalized `Fecha` column.
5. Group by normalized original `Fondos` + calendar month.
6. Keep the row with the greatest available normalized `Fecha` in the group; this is the latest available business date in that month.
7. Do not carry forward a date from the following month.
8. Do not use `fecha_reporte` to determine the month, select the latest row, or break ties.
9. Do not average, sum, or interpolate values.

The monthly output will include the selected source row and the derived identity/date columns. The grouping key is the normalized original `Fondos` value plus the calendar month, which preserves the fund-plus-class identity requested for monthly selection.

## 9. Date interpretation gate

The source `Fecha` values appear to behave like fund metadata dates rather than the daily report date. For example, the same original `Fondos` value and `Fecha` can appear across many different `fecha_reporte` values. This explains the repeated observations described above and is why the keep-first rule is required.

The plan follows the approved instruction to use `Fecha` for the monthly analytical date, even though its values appear to be fund-level metadata such as inception or registration dates. The normalized value will be used exactly as the analytical date, while `fecha_reporte` remains provenance/duplicate-ordering metadata only. The monthly dataset should therefore be interpreted as a latest-observation dataset grouped by each record's `Fecha`, not as a snapshot of the report-date calendar.

## 10. Output files after approval

The implementation writes two files under `data/processed/`:

- `fact_fondos_sbs.csv`
- `fact_fondos_competencia.csv`

The exact output names may be changed before implementation if a different naming convention is preferred.

### Final output schema

Both output files contain these 33 normalized columns:

```text
fecha, id_fondo_clase_dim, id_fondo, id_codigo_fondo_clase,
nombre_fondo_clase_origen, nombre_fondo, nombre_clase, tipo_fondo,
tipo_renta, region, tipo_renta_mixta, duracion, benchmark, moneda,
tipo_cliente, vcp_actual, vcp_anterior, variacion_diaria,
reexpresion_pesos, variacion_mensual, variacion_anual,
cantidad_cuotaparte_actual, cantidad_cuotaparte_anterior,
patrimonio_neto_actual, patrimonio_neto_anterior, calificacion,
sociedad_gestora, comision_ingreso, honorarios_adm_sg,
honorarios_adm_sd, otros_gastos, comision_rescate,
plazo_liquidacion_dias
```

The implementation will not modify `data/raw/VD.zip` or the current `data/processed/vd_daily.csv`.

## 11. Validation checklist

- Every valid `fecha` value is normalized to `YYYY-MM-DD` before date operations.
- Missing `fecha` values are excluded from both outputs under the approved no-quota assumption.
- The exclusion count is reported; the current input has `596` such rows.
- Daily output contains only `Abierto` SBS rows.
- Monthly output contains only `Abierto` non-SBS rows.
- No `Cerrado` rows appear in either output.
- `nombre_clase` retains the `Clase` marker when present.
- `nombre_clase` equals `nombre_fondo_clase_origen` for single-class funds without a `Clase` marker.
- `id_fondo` contains the base fund name or the same single-class value.
- `id_codigo_fondo_clase` is stable and traceable across repeated observations.
- Full-row duplicates are removed before all other validation and filtering steps.
- Each `fecha_reporte` has at most one row for each normalized `nombre_fondo_clase_origen` value after exact duplicate removal.
- Repeated `nombre_fondo_clase_origen` x `fecha` observations retain only the earliest `fecha_reporte` occurrence.
- The monthly output has one selected row per normalized `nombre_fondo_clase_origen` value and calendar month.
- Each monthly selected row is the latest available business date in its month.
- `fecha_reporte` is not used for filtering, analytical date conversion, or monthly selection.
- Row counts, date ranges, removed duplicates, and unparseable values are reported.
