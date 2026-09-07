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
- `permission denied` on `.sql` file: quote the path (it has spaces).
