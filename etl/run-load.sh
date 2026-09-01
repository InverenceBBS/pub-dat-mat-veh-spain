#!/bin/bash
# The ETL: catalogues, load, classify and check. NO PRIVILEGE AT ALL.
#
#   bash /home/devel/matveh/etl/run-load.sh [--monthly | --pending | file.zip ...]
#
# Runs as archive_rw, whose password libpq reads from the password file of
# whoever launches this -- one line per role, database in wildcard:
#   *:*:*:archive_rw:<the password>
#
# It needs no sudo because it only inserts and deletes, and because the two
# functions that do need ownership -- ensure_partition and classify_size -- are
# SECURITY DEFINER. That is what makes this callable from a cron job.
#
# The schema is created by bootstrap-db.sh, which is the privileged part and
# runs once.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
export PGHOST=${PGHOST:-127.0.0.1}      # TCP, so libpq uses the password file
export PGPORT=${PGPORT:-5432}
export PGDATABASE=${PGDATABASE:-matveh}
export PGUSER=${PGUSER:-archive_rw}
WHAT=${1:---pending}

step() { echo; echo "══════ $* ══════"; }

step "Con quién se conecta"
psql -tAc "select 'conectado a '||current_database()||' como '||current_user"

step "Los catálogos del Anexo I"
python3 "$REPO/etl/load.py" --codes

step "La carga: $WHAT"
python3 "$REPO/etl/load.py" "$@"

step "Clasificar las fichas por tamaño"
psql -c "SELECT spain.classify_size() AS fichas_clasificadas"

step "Las comprobaciones, contra doc/fase0-resultados.md"
psql -f "$REPO/schema/checks.sql"
