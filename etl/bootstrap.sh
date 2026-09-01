#!/bin/bash
# Sets up the spain schema on THIS server and loads whatever is in the raw
# store, from nothing to checked, in one go.
#
#   bash /home/devel/matveh/etl/bootstrap.sh 2>&1 | tee /home/devel/matveh-bootstrap.log
#
# Run it as the ordinary user (devel), not as root: it calls sudo -u postgres
# for the database work, which is peer-authenticated and needs no password file.
#
# It is meant to be run again. The schema refuses to wipe loaded events unless
# told to on purpose, loading a month replaces that month, and the cron line is
# only added if it is not already there. What it is NOT is a migration tool: to
# change one function, copy its CREATE OR REPLACE and run that alone.
#
# This one is server-specific and bash on purpose. Everything portable -- the
# download and the load -- is Python and runs on Windows too.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
RAW=${MATVEH_RAW:-/data/matveh/raw}
LOGDIR=${MATVEH_LOG:-/home/devel}
PSQL="sudo -u postgres psql -v ON_ERROR_STOP=1 -d matveh"
LOAD="sudo -u postgres python3 $REPO/etl/load.py"

step() { echo; echo "══════ $* ══════"; }

step "0. Qué hay para cargar"
ls -1 "$RAW"/*.zip 2>/dev/null | wc -l | xargs echo "ficheros ZIP en $RAW:"
test -s "$RAW/manifest.tsv" || echo "AVISO: no hay manifiesto en $RAW, así que las filas de source_file irán sin huella ni URL"

step "1. El esquema"
$PSQL -f "$REPO/schema/01-spain-schema.sql"

step "2. Las clases de tamaño y sus reglas"
$PSQL -f "$REPO/schema/02-size-rules.sql"

step "3. Los catálogos del Anexo I"
cd "$REPO"
$LOAD --codes

step "4. Los mensuales"
$LOAD --monthly

step "5. Lo que quede por cargar, que son los diarios"
$LOAD --pending

step "6. Clasificar las fichas por tamaño"
$PSQL -c "SELECT spain.classify_size() AS fichas_clasificadas"

step "7. Las comprobaciones, contra doc/fase0-resultados.md"
$PSQL -f "$REPO/schema/checks.sql"

step "8. La descarga diaria"
# The daily files are the only ones carrying the homologation password and the
# DGT keeps them some twenty days: what is not downloaded on the day is lost.
CRON_LINE="17 6 * * * /usr/bin/python3 $REPO/etl/download.py --recent 3 >> $LOGDIR/matveh-download.log 2>&1"
if crontab -l 2>/dev/null | grep -qF "$REPO/etl/download.py"; then
  echo "ya estaba en el crontab:"
  crontab -l | grep -F "$REPO/etl/download.py"
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "añadida al crontab:"
  echo "$CRON_LINE"
fi

step "Hecho"
echo "Trazas en $LOGDIR. Para volver a cargar un mes concreto:"
echo "  sudo -u postgres python3 $REPO/etl/load.py $RAW/export_mensual_mat_202607.zip"
