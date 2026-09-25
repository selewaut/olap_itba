# Fuentes por indice — evaluacion para descarga 2 anios (2024-09-23 → 2026-09-23)

Verificado el 2026-09-23 con API real BCRA v4. Frecuencia y cobertura abajo.

| # | Indice pedido | Fuente recomendada | Como bajar (implementado en `src/downloading/`) | Frecuencia | Cobertura 2 anios | Plan B |
|---|---|---|---|---|---|---|
| 1 | Dólar Oficial | **BCRA API v4** `id=4` minorista vendedor + `id=5` mayorista ref | `bcra_client.py` → `GET /estadisticas/v4.0/Monetarias/{id}?desde=&hasta=` sin auth | Diaria | ✅ Total (4 desde 2010, 5 desde 2002) | BCRA web "Principales variables" CSV; datos.gob.ar serie mensual |
| 2 | Dólar CCL | **ArgentinaDatos API** casa `contadoconliqui` (fuente DolarApi) | `dolar_ccl.py` → `GET api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui/YYYY/MM/DD` loop ~730 días | Diaria (hábiles) | ✅ Requiere loop (~3-5 min); spot check con `dolarapi.com/v1/dolares/contadoconliqui` | Bluelytics API, Ámbito Financiero scraping, dolarblu.com histórico |
| 3 | Merval ARS + USD | **Yahoo Finance `^MERV`**; USD = ARS / CCL venta | `market_yfinance.py` (`yfinance`) + `merval_usd()` | Diaria | ✅ | BYMA oficial (sin API, scraping), Investing.com `merv-historical-data` |
| 4 | Índice CER | **BCRA API v4 `id=30`** base 02/02/2002=1 | `bcra_client.py` | Diaria | ✅ (desde 2002) | BCRA Comunicación "B" series diarias PDF/XLS |
| 5 | Índice UVA | **BCRA API v4 `id=31`** base 31/03/2016=14.05 | `bcra_client.py` | Diaria | ✅ (desde 2016) | BCRA Com. "B" 13134/13156, tasmet.pdf |
| 6 | Índice acciones Brasil (?) | **= Bovespa `^BVSP`** (pedido duplica #11; se unifica). Si se quiere segundo índice BR: `EWZ`/MSCI Brazil | `market_yfinance.py` | Diaria | ✅ | B3 oficial `b3.com.br`, Investing.com |
| 7 | IPC | **datos.gob.ar Series API** `145.3_INGNACNAL_DICI_M_15` (nivel) + `145.3_INGNACUAL_DICI_M_38` (var mensual) | `indec_client.py` → `GET apis.datos.gob.ar/series` sin auth. `clean.py` pone la fecha al último día del mes | Mensual | ✅ 24 obs. 2 años | XLS INDEC (`--fuente xls`); ArgenStats; BCRA `id=27/28` |
| 8 | IPM mayorista | **datos.gob.ar** IPIM `448.1_NIVEL_GENERAL_0_0_13_46` (+ IPIB `449.1_NIVEL_GENERAL_0_0_13_97`) | `indec_client.py` misma API; archivos `indec_ipim_nivel.csv` / `indec_ipib_nivel.csv` | Mensual | ✅ | XLS SIPM INDEC (`--fuente xls`) |
| 9 | TAMAR | **BCRA API v4 `id=44`** privada (serie nueva) | `bcra_client.py` | Diaria | ⚠️ **Desde 2024-10-01** → 2 años truncados ~23 meses. Alts `45/135/136/137` (privada/pub+priv, n.a./e.a. — ver metodología) | Informe Monetario Diario BCRA XLS, `tasmet.pdf` |
| 10 | BADLAR | **BCRA API v4 `id=7`** privada % n.a. (alts `139` idéntica, `140/35` e.a., `138` pub+priv) | `bcra_client.py` | Diaria | ✅ (desde 1999/2003) | Informe Monetario Diario, datos.gob.ar |
| 11 | Bovespa | **Yahoo Finance `^BVSP`** (Ibovespa BRL) | `market_yfinance.py` | Diaria | ✅ | B3 oficial, Investing.com |

## Detalles BCRA (verificados por API)

- Base: `https://api.bcra.gob.ar/estadisticas/v4.0` — **v3 deprecada (410)**, usar v4.
- `GET /Monetarias` lista variables; `GET /Monetarias/{id}?desde=YYYY-MM-DD&hasta=&limit=&offset=` pagina de a 1000.
- `GET /Metodologia/{id}` explica n.a. vs e.a., universo (privada vs pub+priv).
- TAMAR: metodología nueva (tope $1.000M en 2025, actualización anual por IPC). BADLAR: plazo fijo $1M+ 30-35 días.
- Últimos valores al 2026-09-22 aprox: oficial minorista ~1533, mayorista ~1513; BADLAR ~22% n.a.; TAMAR ~23.5%; CER ~843.9; UVA ~2130.

## Orden de descarga sugerido (2 años)

1. `uv run python -m src.downloading.run_all --only bcra` (segundos, valida pipeline).
2. `... --only merval,bovespa` (requiere `yfinance`).
3. `... --only ccl` (lento; dejar corriendo).
4. `... --only indec` (datos.gob.ar, segundos).
5. `uv run python -m src.preprocessing.clean` → `data/processed/fact_cotizacion.csv` → `\copy` al DW (`sql/dw_create.sql`).

## Fondos Comunes de Inversión (para comparar)

Fuente oficial: **CAFCI** (Cámara Argentina de FCI, `cafci.org.ar`) — valor cuotaparte + patrimonio diario por fondo/clase. Complemento: CNV. El DW ya trae `dim_fondo` + `fact_rendimiento_fondo` con `benchmark_codigo` para cruzar cada fondo con su índice (ej. fondo CER vs `CER`, money market vs `BADLAR`).

## Procesamiento de `VD.zip`

La fuente de fondos está almacenada como `data/raw/VD.zip`, con un workbook diario por snapshot. El módulo `src/preprocessing/vd.py` determina la fecha más reciente a partir del nombre de cada workbook, selecciona la ventana rolling de dos años calendario y genera `data/processed/vd_daily.csv`.

```zsh
uv run python -m src.preprocessing.vd
```

La selección se basa en el nombre `YYYYMMDD_Planilla_Diaria_F4.xlsx`, no en la columna `Fecha` del workbook ni en la fecha de modificación del zip. La columna `Fecha` se conserva como metadata original; el preprocessing agrega `fecha_reporte` y `archivo` para identificar el snapshot de cada fila. El archivo original no se modifica.
