#!/bin/bash
# The whole circuit, once an hour and with no privilege: ask, download what is
# new, load it, classify what came in.
#
#   bash /home/devel/matveh/etl/hourly.sh
#
# This is the line that goes in the cron. It replaces the download-only one:
# downloading without loading leaves the files on disk and the database behind,
# which is exactly what happened with the first days of September.
#
# Cheap by design. The check is eight HEAD requests; the load does nothing when
# nothing came in; and the classification only touches the sheets that arrived,
# not the whole dimension.
#
# When the DGT publishes the monthly file of a month whose dailies are already
# loaded -- around the 15th -- this picks it up too, and the load replaces the
# month and marks its dailies superseded. No special case needed.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
export PGHOST=${PGHOST:-127.0.0.1}
export PGPORT=${PGPORT:-5432}
export PGDATABASE=${PGDATABASE:-matveh}
export PGUSER=${PGUSER:-archive_rw}

echo "══════ $(date -u '+%Y-%m-%dT%H:%M:%SZ') ══════"

python3 "$REPO/etl/download.py" --check 4
python3 "$REPO/etl/load.py" --pending
psql -P pager=off -tAc "SELECT 'fichas nuevas clasificadas: '||spain.classify_size(true)"
