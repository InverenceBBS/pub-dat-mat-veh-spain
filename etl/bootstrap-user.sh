#!/bin/bash
# The part of the setup that needs no privilege at all: the raw store and the
# daily capture. Runs as the ordinary user, never as root.
#
#   bash /home/devel/matveh/etl/bootstrap-user.sh
#
# The database side is bootstrap-db.sh, which runs as the postgres user.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
RAW=${MATVEH_RAW:-/data/matveh/raw}
LOGDIR=${MATVEH_LOG:-$HOME}

step() { echo; echo "══════ $* ══════"; }

step "1. El almacén de ficheros"
if [ ! -d "$RAW" ]; then
  echo "NO EXISTE $RAW. Créalo con:"
  echo "  sudo install -d -o $USER -g $USER -m 755 $RAW"
  exit 1
fi
echo "$RAW: $(ls -1 "$RAW"/*.zip 2>/dev/null | wc -l) ZIP, $(du -sh "$RAW" | cut -f1)"
test -s "$RAW/manifest.tsv" \
  && echo "manifiesto: $(($(wc -l < "$RAW/manifest.tsv") - 1)) ficheros con su huella" \
  || echo "AVISO: sin manifiesto, las filas de source_file irán sin huella ni URL"

step "2. Una descarga de prueba, que además trae lo de hoy"
python3 "$REPO/etl/download.py" --recent 2

step "3. La captura diaria"
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
