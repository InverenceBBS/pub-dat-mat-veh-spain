#!/usr/bin/env python3
"""When does the DGT actually publish each daily file?

    python3 publication-hours.py            the whole picture
    python3 publication-hours.py --watch    week by week, to see it drift

The DGT documents no schedule, so this is measured, and the source is the only
one available: the HTTP **Last-Modified** header that its web server returns for
each ZIP. download.py captures it on every download and writes it to
manifest.tsv in the raw store, so the figure can be recomputed at any time --
and it should be, because the answer may drift.

WHAT IT MEASURES, AND WHAT IT DOES NOT. Last-Modified is the moment the file was
last written on the server, which is the closest thing to its publication time
that can be observed from outside. It is not an announced schedule and nothing
promises the DGT keeps it. Two consequences worth keeping in mind: a file
rewritten later without changing its contents would look published later than it
was, and the header is in GMT, which the DGT's own server sets -- not our clock.
"""
import collections
import io
import os
import sys
from datetime import datetime

RAW = os.environ.get('MATVEH_RAW', '/data/matveh/raw')
MANIFEST = os.path.join(RAW, 'manifest.tsv')


def rows():
    with io.open(MANIFEST, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            yield dict(zip(head, line.rstrip('\n').split('\t')))


def watch():
    """Week by week, so a change of habit shows up instead of being averaged away.

    Losing files is not what this guards against -- two passes a day and
    --recent 4 already tolerate the DGT moving its hour by up to four days. This
    is so that we FIND OUT, which the download alone would never tell us.
    """
    weeks = collections.defaultdict(collections.Counter)
    for r in rows():
        if r.get('granularity') != 'daily' or not r.get('http_last_modified'):
            continue
        published = datetime.strptime(r['http_last_modified'], '%a, %d %b %Y %H:%M:%S %Z')
        data_day = datetime.strptime(r['period'], '%Y%m%d')
        year, week, _ = data_day.isocalendar()
        weeks['%d-S%02d' % (year, week)]['%02d:%02d' % (published.hour, published.minute)] += 1

    print('# Hora de publicación, semana a semana\n')
    print('| Semana de los datos | Horas de publicación (GMT) |')
    print('|---|---|')
    for week in sorted(weeks):
        detail = ', '.join('%s x%d' % (h, n) for h, n in sorted(weeks[week].items()))
        print('| %s | %s |' % (week, detail))
    print('\nLo esperado es 06:30, y 13:00 de vez en cuando. Cualquier otra hora que se '
          'repita quiere decir que la DGT ha cambiado de costumbre, y entonces hay que '
          'revisar las dos pasadas del cron.')
    return 0


def main():
    if '--watch' in sys.argv[1:]:
        if not os.path.exists(MANIFEST):
            print('No hay manifiesto en %s' % MANIFEST)
            return 1
        return watch()
    if not os.path.exists(MANIFEST):
        print('No hay manifiesto en %s' % MANIFEST)
        return 1
    daily = [r for r in rows()
             if r.get('granularity') == 'daily' and r.get('http_last_modified')]
    if not daily:
        print('El manifiesto no trae ningún diario con last-modified.')
        return 1

    by_hour = collections.Counter()
    lags = []
    for r in daily:
        published = datetime.strptime(r['http_last_modified'], '%a, %d %b %Y %H:%M:%S %Z')
        data_day = datetime.strptime(r['period'], '%Y%m%d')
        by_hour['%02d:%02d' % (published.hour, published.minute)] += 1
        lags.append((published - data_day).total_seconds() / 3600.0)
    lags.sort()

    print('# Hora de publicación de los ficheros diarios de la DGT\n')
    print('Medido sobre **%d ficheros diarios** con `Last-Modified` en `%s`.\n'
          % (len(daily), MANIFEST))
    print('| Hora de publicación (GMT) | Ficheros |')
    print('|---|---:|')
    for hour, count in sorted(by_hour.items()):
        print('| %s | %d |' % (hour, count))
    print('\n| Desfase entre el día de los datos y su publicación | Horas |')
    print('|---|---:|')
    print('| mínimo | %+.1f |' % lags[0])
    print('| mediana | %+.1f |' % lags[len(lags) // 2])
    print('| máximo | %+.1f |' % lags[-1])
    print('\nDe aquí salen las dos pasadas del cron, a las 07:00 y a las 14:00 UTC.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
