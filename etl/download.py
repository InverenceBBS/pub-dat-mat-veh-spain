#!/usr/bin/env python3
"""Downloads DGT microdata files into the raw store.

    python3 download.py [period ...]        e.g. mat:201412 bajas:20260831
    python3 download.py --recent [days]    today and the days before it
    python3 download.py --history          every monthly file, 2014-12 onwards
    python3 download.py --check [days]     ask HEAD first, download only what changed

Six digits mean the monthly file of that period; eight, the daily one of that
day. --recent is what the daily job runs: it asks for the last few days of both
families and ignores what is not published yet, so a day missed because of a
failure or a holiday is picked up on the next run. With no arguments it
downloads the phase 0 sample. Files already present
with the same sha256 are left alone, so it can be run again without
re-downloading.

THE DAILY FILES ARE ONLY PUBLISHED FOR SOME TWENTY DAYS. Whatever is needed to
compare a monthly file against the sum of its dailies has to be downloaded
while it is still there: once the month closes, that comparison can no longer
be made from the source.

Standard library only, and no shelling out: the same code has to work on
Windows, where there is no curl, no unzip and no sha256sum.
"""
import hashlib
import io
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

RAW = os.environ.get('MATVEH_RAW', '/data/matveh/raw')
MANIFEST = os.path.join(RAW, 'manifest.tsv')

# The two families share the URL shape. Note the two traps documented in
# doc/fuente.md: the month goes WITHOUT a leading zero in the path and WITH one
# in the file name, and both are the period's, not the publication's.
ROOT = 'https://www.dgt.es/microdatos/salida/%(year)s/%(month)d/vehiculos/%(family)s/%(name)s'
FAMILY = {'mat': ('matriculaciones', 'export_mensual_mat_%s.zip', 'export_mat_%s.zip'),
          'bajas': ('bajas', 'export_mensual_bajas_%s.zip', 'export_bajas_%s.zip')}

# The phase 0 sample: four registration months spread over the eleven years,
# plus the oldest and the newest of deregistrations. Enough to see whether the
# record layout of today holds for 2014, which is the measurement that can
# change the whole design.
SAMPLE = ['mat:201412', 'mat:201806', 'mat:202206', 'mat:202607',
          'bajas:201412', 'bajas:202607']

MANIFEST_HEAD = ['kind', 'granularity', 'period', 'file_name', 'url', 'byte_size', 'sha256',
                 'http_last_modified', 'http_etag', 'downloaded_time']


def url_of(kind, period):
    family, monthly, daily = FAMILY[kind]
    pattern = monthly if len(period) == 6 else daily
    return ROOT % {'year': period[:4], 'month': int(period[4:6]),
                   'family': family, 'name': pattern % period}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_manifest():
    rows = {}
    if os.path.exists(MANIFEST):
        with io.open(MANIFEST, encoding='utf-8') as f:
            head = f.readline().rstrip('\n').split('\t')
            for line in f:
                row = dict(zip(head, line.rstrip('\n').split('\t')))
                rows[row['file_name']] = row
    return rows


def write_manifest(rows):
    with io.open(MANIFEST, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(MANIFEST_HEAD) + '\n')
        for name in sorted(rows):
            f.write('\t'.join(str(rows[name].get(c, '')) for c in MANIFEST_HEAD) + '\n')


def download(kind, period, rows):
    url = url_of(kind, period)
    name = url.rsplit('/', 1)[1]
    path = os.path.join(RAW, name)
    if name in rows and os.path.exists(path) and sha256_of(path) == rows[name]['sha256']:
        print('%-40s ya estaba, intacto' % name)
        return
    request = urllib.request.Request(url, headers={'User-Agent': 'matveh/0.1'})
    with urllib.request.urlopen(request, timeout=120) as answer:
        headers = answer.headers
        with open(path, 'wb') as out:
            while True:
                chunk = answer.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
    rows[name] = {'kind': kind, 'granularity': 'monthly' if len(period) == 6 else 'daily',
                  'period': period, 'file_name': name, 'url': url,
                  'byte_size': os.path.getsize(path), 'sha256': sha256_of(path),
                  'http_last_modified': headers.get('last-modified', ''),
                  'http_etag': (headers.get('etag') or '').strip('"'),
                  'downloaded_time': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    print('%-40s %10d bytes  %s' % (name, rows[name]['byte_size'], rows[name]['sha256'][:12]))


def head(url):
    """The headers of a URL, or None if it is not published.

    This is the cheap way to ask "is there anything new?": a HEAD returns the
    ETag, the size and the date with ZERO bytes of body, so it can be run every
    hour without weighing on anyone.

    Conditional GETs would be cheaper still and they DO NOT WORK here: measured
    on 2026-09-01, the DGT's server ignores both If-None-Match and
    If-Modified-Since and answers 200 with the whole file. Hence HEAD plus our
    own comparison against the manifest.
    """
    request = urllib.request.Request(url, method='HEAD',
                                     headers={'User-Agent': 'matveh/0.1'})
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return answer.headers
    except urllib.error.HTTPError as trouble:
        if trouble.code == 404:
            return None
        raise


def check(days, rows):
    """What of the last `days` is new or has changed on the server.

    Also catches something a plain download never would: a file the DGT REWRITES
    after we took it. Comparing our stored ETag against the current one is the
    only way to notice, and then the load replaces that day, so a reprocess ends
    up in the database instead of being ignored for ever.
    """
    wanted = []
    for item in recent(days):
        kind, period = item.split(':')
        url = url_of(kind, period)
        name = url.rsplit('/', 1)[1]
        headers = head(url)
        if headers is None:
            print('%-40s no publicado' % name)
            continue
        etag = (headers.get('etag') or '').strip('"')
        known = rows.get(name)
        if known is None:
            print('%-40s NUEVO' % name)
            wanted.append(item)
        elif etag and etag != known.get('http_etag'):
            print('%-40s CAMBIADO en el servidor (etag %s -> %s)'
                  % (name, known.get('http_etag'), etag))
            wanted.append(item)
        else:
            print('%-40s sin cambios' % name)
    return wanted


def recent(days):
    """The last `days` days, both families, most recent first.

    Not published yet is the normal case for today's file, so a 404 here is not
    a failure: it is picked up on a later run.
    """
    today = datetime.now(timezone.utc).date()
    items = []
    for back in range(days):
        day = (today - timedelta(days=back)).strftime('%Y%m%d')
        items.extend(['mat:%s' % day, 'bajas:%s' % day])
    return items


def history(first='201412'):
    """Every monthly period from first up to the last closed month.

    The current month has no monthly file yet, and neither does the one just
    ended until the DGT closes it around the 15th, so both are simply asked for
    and skipped on a 404.
    """
    year, month = int(first[:4]), int(first[4:6])
    today = datetime.now(timezone.utc).date()
    items = []
    while (year, month) <= (today.year, today.month):
        items += ['mat:%04d%02d' % (year, month), 'bajas:%04d%02d' % (year, month)]
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return items


def main(argv):
    if not os.path.isdir(RAW):
        os.makedirs(RAW)
    if argv and argv[0] == '--history':
        argv = history(argv[1] if len(argv) > 1 else '201412')
    if argv and argv[0] == '--recent':
        days = int(argv[1]) if len(argv) > 1 else 3
        argv = recent(days)
    rows = read_manifest()
    if argv and argv[0] == '--check':
        days = int(argv[1]) if len(argv) > 1 else 4
        argv = check(days, rows)
        if not argv:
            print('\nNada nuevo.')
            return
    for item in (argv or SAMPLE):
        kind, period = item.split(':')
        try:
            download(kind, period, rows)
        except Exception as trouble:                      # noqa: BLE001
            print('%-40s FALLO: %s' % (item, trouble))
    write_manifest(rows)
    print('\nManifiesto: %s' % MANIFEST)


if __name__ == '__main__':
    main(sys.argv[1:])
