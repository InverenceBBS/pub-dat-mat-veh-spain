#!/bin/bash
# Creates the schema. THIS IS THE ONLY PART THAT NEEDS PRIVILEGE, and it is run
# once:
#
#   sudo -u postgres bash /home/devel/matveh/etl/bootstrap-db.sh [--reset]
#
# Creating tables belongs to the owning role, model_archive. The ETL does NOT
# belong here and does not need any of this: it runs as archive_rw with no sudo,
# through run-load.sh, which is what the cron will call.
#
# --reset lets the schema be recreated when events are already loaded. It has to
# be typed: the guard exists so that nobody wipes eleven years of loading by
# re-running a setup script out of habit.
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

step "Hecho: el esquema está creado"
echo "Ahora la carga, que NO necesita sudo:"
echo "  bash $REPO/etl/run-load.sh"
