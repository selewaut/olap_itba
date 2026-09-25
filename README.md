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

Para este archivo, el rango esperado es `2024-09-23` a `2026-09-23` y hay 483 snapshots diarios.
