#!/bin/bash
# Sets up the spain schema and loads whatever is in the raw store.
#
# RUNS AS THE DATABASE SUPERUSER, and takes no sudo of its own:
#   sudo -u postgres bash /home/devel/matveh/etl/bootstrap-db.sh [--reset]
#
# The log is the caller's business: pipe it through tee to a file the CALLING
# user can write, not one that a previous run left owned by root.
#
# Split from bootstrap-user.sh on purpose: everything here needs the database
# and nothing else, so it can be launched from a session that already holds the
# sudo, while the part that needs no privilege runs on its own.
#
# Meant to be run again. The schema refuses to wipe loaded events unless told to
# with PGOPTIONS="-c spain.allow_reset=yes", and loading a month replaces that
# month. What it is NOT is a migration tool: to change one function, copy its
# CREATE OR REPLACE and run that alone.
set -euo pipefail

# --reset is what lets the schema be recreated when events are already loaded.
# It has to be typed: the guard exists precisely so that nobody wipes eleven
# years of loading by re-running a setup script out of habit.
if [ "${1:-}" = "--reset" ]; then
  export PGOPTIONS="-c spain.allow_reset=yes"
  echo "AVISO: --reset, así que el esquema se recrea y lo ya cargado se pierde."
fi

REPO=$(cd "$(dirname "$0")/.." && pwd)
RAW=${MATVEH_RAW:-/data/matveh/raw}
PSQL="psql -v ON_ERROR_STOP=1 -d matveh"

step() { echo; echo "══════ $* ══════"; }

step "0. Qué hay para cargar"
ls -1 "$RAW"/*.zip 2>/dev/null | wc -l | xargs echo "ficheros ZIP en $RAW:"

step "1. El esquema"
$PSQL -f "$REPO/schema/01-spain-schema.sql"

step "2. Las clases de tamaño y sus reglas"
$PSQL -f "$REPO/schema/02-size-rules.sql"

step "3. Los catálogos del Anexo I"
python3 "$REPO/etl/load.py" --codes

step "4. Los mensuales"
python3 "$REPO/etl/load.py" --monthly

step "5. Lo que quede, que son los diarios"
python3 "$REPO/etl/load.py" --pending

step "6. Clasificar las fichas por tamaño"
$PSQL -c "SELECT spain.classify_size() AS fichas_clasificadas"

step "7. Las comprobaciones, contra doc/fase0-resultados.md"
$PSQL -f "$REPO/schema/checks.sql"

step "Hecho"
echo "Para volver a cargar un mes concreto:"
echo "  sudo -u postgres python3 $REPO/etl/load.py $RAW/export_mensual_mat_202607.zip"
