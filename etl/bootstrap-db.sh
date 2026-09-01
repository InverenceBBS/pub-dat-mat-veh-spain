#!/bin/bash
# Sets up the spain schema and loads whatever is in the raw store.
#
# RUNS AS THE DATABASE SUPERUSER, and takes no sudo of its own:
#   sudo -u postgres bash /home/devel/matveh/etl/bootstrap-db.sh 2>&1 | tee /home/devel/matveh-db.log
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
