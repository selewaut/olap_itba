# Plan: SBS daily and non-SBS monthly datasets

## Status

Planning only. No new datasets have been generated. The source CSV and the original `VD.zip` remain unchanged.

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
- The current classification is therefore unambiguous, but the implementation will still use the approved `contains "SBS"` rule unless exact equality is chosen.
- `Fecha` currently uses `DD/MM/YY`, for example `23/09/24`. The observed source format is not `YYYY/MM/DD`.
- There are `1,792,658` non-empty `Fecha` values and `596` missing values.
- The first validation of one row per `fecha_reporte` and `Fondos` found:
  - `4` duplicated groups.
  - `8` rows in those groups.
  - The four groups are exact duplicate pairs for `Pionero Money Market Dólar - Clase D` and `Pionero Money Market Dólar - Clase E` on `2026-03-06` and `2026-03-09`.
- If `Fondo` means the base `fondoId`, one row per report date is not expected because a base fund can have multiple classes. The uniqueness check will therefore use the normalized `FondoClase` identity unless a base-fund-only check is explicitly approved.
- The current input does not yet pass the requested one-row-per-report-date-per-`Fondos` validation and must be de-duplicated before output generation.
- There are `2,755` `FondoClase` x `Fecha` pairs repeated across different `fecha_reporte` values, producing `122,483` extra report observations. These are the records described as likely stale or closed-fund observations and require the requested keep-first rule.

## 2. Output datasets

The two output datasets are intentionally different populations:

### Daily SBS dataset

Contains only rows classified as SBS:

```text
Tipo de Fondo == "Abierto"
and Sociedad Gerente contains "SBS", case-insensitive
```

- No non-SBS rows will be included.
- No monthly reduction is performed.
- The output remains at the available daily observation grain.

### Monthly non-SBS dataset

Contains only rows classified as non-SBS:

```text
Tipo de Fondo == "Abierto"
and Sociedad Gerente does not contain "SBS", case-insensitive
```

- No SBS rows will be included.
- Monthly selection is performed after date normalization and de-duplication.
- The output contains one selected source row per fund/class and calendar month.

Blank or null `Sociedad Gerente` values are treated as non-SBS unless a different rule is approved.

## 3. Date normalization before date operations

Dates will be normalized before filtering, grouping, de-duplication, or monthly selection.

### `Fecha`

The source `Fecha` column is observed in `DD/MM/YY` format, not `YYYY/MM/DD`. The preprocessing will:

1. Parse valid values using an unambiguous date parser configured for the observed format.
2. Convert valid values to ISO `YYYY-MM-DD`.
3. Store the normalized result in the analytical `Fecha` column.
4. Preserve the original value in `Fecha_original` for traceability if the schema change is approved.
5. Report missing or invalid values instead of silently coercing them.

The current input has `596` missing `Fecha` values. The implementation must not perform month selection on those rows. The default proposed policy is to quarantine them from the analytical output and report their count; an alternative policy may keep them in the daily SBS output if approved.

### `fecha_reporte`

`fecha_reporte` is already in ISO `YYYY-MM-DD` format and will be validated for consistency. It will not be used as the analytical date, as a date filter, or for monthly grouping. It may be retained for provenance and will be used only where explicitly required by the approved duplicate-ordering rule below.

## 4. Derived fund columns

The original `Fondos` column will be preserved. Two normalized identity columns will be created before the daily/monthly split.

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

- For a class-labelled `Fondos` value, `fondoId` is the base fund name before the first `Clase` marker.
- For a single-class value, `fondoId` is set to the same normalized value as `FondoClase` and the original `Fondos` value.

Example:

```text
Adcap Balanceado I - Clase A -> fondoId = "Adcap Balanceado I"
1810 Mas Ahorro -> fondoId = "1810 Mas Ahorro"
```

The logical fund identity is the combination of `fondoId` and `FondoClase`, which is equivalent to the original fund-plus-class `Fondos` value. This prevents different classes of the same fund from being combined.

### `idFondoClase`

A stable traceability identifier will be added as `idFondoClase`:

- Prefer the existing `Código Fondo CAFCI` and `Código Clase CAFCI` columns.
- Construct the identifier from those codes when available.
- If either code is missing, use a deterministic fallback built from normalized `fondoId` and `FondoClase`.
- Keep the same identifier for repeated observations of the same fund/class.

The current source has no missing values in either CAFCI code column. The exact identifier format will be documented in the output schema when implementation begins.

## 5. Initial uniqueness and de-duplication validation

Before generating either output:

1. Normalize `Fecha`.
2. Derive `FondoClase`, `fondoId`, and `idFondoClase`.
3. Validate that each `fecha_reporte` has at most one row for each normalized `FondoClase`.
4. Report any duplicate keys before de-duplication.
5. Remove exact duplicate rows within the same `fecha_reporte` x `FondoClase` group, keeping the first row.
6. Re-run the uniqueness validation and require it to pass.

The current input is expected to report the four exact duplicate groups described in Section 1 before de-duplication.

## 6. Repeated observations and closed funds

For a normalized `FondoClase` x `Fecha` pair observed on different `fecha_reporte` values:

- Sort observations by `fecha_reporte` ascending.
- Keep only the first observation.
- Do not keep later observations with the same fund/class and normalized `Fecha`.
- Use `fecha_reporte` only for this requested duplicate-ordering operation; do not use it for date filtering or monthly selection.

This rule will be applied before the SBS daily and non-SBS monthly split so both outputs are based on the same cleaned source rows. The validation report will show how many repeated pairs and rows were removed.

## 7. Daily SBS selection

After common cleaning:

1. Keep rows where `Tipo de Fondo == "Abierto"`.
2. Keep rows where `Sociedad Gerente` contains `SBS`, case-insensitive.
3. Keep all valid daily observations without monthly aggregation.
4. Include `Fecha` in normalized ISO format, `Fecha_original`, `FondoClase`, `fondoId`, and `idFondoClase`.
5. Do not use `fecha_reporte` for filtering or analytical date calculations.
6. Validate that each `fecha_reporte` has at most one row for each normalized `FondoClase`.

The daily output will preserve the remaining source columns unless a separate schema explicitly removes any of them.

## 8. Monthly non-SBS selection

After common cleaning:

1. Keep rows where `Tipo de Fondo == "Abierto"`.
2. Keep rows where `Sociedad Gerente` does not contain `SBS`, case-insensitive.
3. Determine the calendar month from the normalized `Fecha` column.
4. Group by `fondoId` + `FondoClase` + calendar month.
5. Keep the row with the greatest available normalized `Fecha` in each group.
6. If the month-end date is unavailable, keep the latest available date on or before that month end.
7. Do not use `fecha_reporte` to determine the month, select the latest row, or break ties.
8. Do not average, sum, or interpolate values.

The monthly output will include the selected source row and the derived identity/date columns. The requested `FondoClase` x `Fecha` grouping is represented by the normalized `fondoId` + `FondoClase` identity and the normalized analytical date.

## 9. Date interpretation gate

The source `Fecha` values appear to behave like fund metadata dates rather than the daily report date. For example, the same `FondoClase` and `Fecha` can appear across many different `fecha_reporte` values. This explains the repeated observations described above and is why the keep-first rule is required.

The plan follows the requested instruction to use `Fecha` for the monthly analytical date and does not use `fecha_reporte` for monthly selection. Before implementation, confirm whether this is intentional. If `fecha_reporte` is actually the intended daily date, the monthly rule must be reconsidered because it conflicts with the current instruction not to use `fecha_reporte` as a filtering or analytical date column.

## 10. Output files after approval

The implementation will write two proposed files under `data/processed/`:

- `vd_daily_sbs.csv`
- `vd_monthly_non_sbs.csv`

The exact output names may be changed before implementation if a different naming convention is preferred.

The implementation will not modify `data/raw/VD.zip` or the current `data/processed/vd_daily.csv`.

## 11. Validation checklist

- Every valid `Fecha` value is normalized to `YYYY-MM-DD` before date operations.
- Missing or invalid `Fecha` values are reported and handled according to the approved policy.
- Daily output contains only `Abierto` SBS rows.
- Monthly output contains only `Abierto` non-SBS rows.
- No `Cerrado` rows appear in either output.
- `FondoClase` retains the `Clase` marker when present.
- `FondoClase` equals normalized `Fondos` for single-class funds without a `Clase` marker.
- `fondoId` contains the base fund name or the same single-class value.
- `idFondoClase` is stable and traceable across repeated observations.
- Each `fecha_reporte` has at most one row for each normalized `FondoClase` after exact duplicate removal.
- Repeated `FondoClase` x `Fecha` observations retain only the earliest `fecha_reporte` occurrence.
- The monthly output has one selected row per `fondoId` + `FondoClase` + month.
- Each monthly selected row is the latest available date on or before that month end.
- `fecha_reporte` is not used for filtering, analytical date conversion, or monthly selection.
- Row counts, date ranges, removed duplicates, and unparseable values are reported.

## Approval questions

1. Should SBS classification remain `contains "SBS"` or use exact equality to `SBS Asset Management S.A.S.G.F.C.I.`? The current data produces the same result either way.
2. Is `FondoClase` intended to contain only the class suffix, such as `Clase A`, with `fondoId` containing the base fund name?
3. Is the proposed `idFondoClase` format based on `Código Fondo CAFCI` and `Código Clase CAFCI` acceptable?
4. Should the `596` rows with missing `Fecha` be quarantined, or should they remain in the daily SBS output without date-based operations?
5. Is the keep-first rule intended to use `FondoClase` + normalized `Fecha`, preserving different classes of the same fund?
6. Is `Fecha` intentionally the monthly analytical date despite appearing to be a fund metadata date?
7. For a missing month-end date, is the latest available date on or before month end the desired rule?
