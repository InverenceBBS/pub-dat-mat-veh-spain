#!/usr/bin/env python3
"""Extracts the Anexo I code tables from doc/tablas-de-codigos.md into codes/*.tsv,
and then checks the real files against them.

    python3 extract_codes.py [file.zip ...]

The markdown document is the source, as it says of itself; these TSV are the
versioned intermediate step, so that a change in the DGT's codes shows up as a
diff instead of breaking a load. Parsing the markdown at load time would be
fragile: one new table in the document and the ETL stops.
"""
import collections
import glob
import io
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, '..', 'doc', 'tablas-de-codigos.md')
CODES = os.path.join(HERE, '..', 'codes')
RAW = os.environ.get('MATVEH_RAW', '/data/matveh/raw')
LAYOUT = os.path.join(HERE, '..', 'doc', 'record-layout.tsv')

# Heading prefix in the document -> catalogue name. Anything else is ignored.
CATALOGUE = [
    ('COD_CLASE_MAT', 'plate_class'),
    ('COD_PROCEDENCIA', 'origin'),
    ('COD_SERVICIO', 'service_old'),
    ('SERVICIO', 'service'),
    ('COD_PROPULSION', 'propulsion'),
    ('CLAVE_TRAMITE', 'procedure_type'),
    ('IND_BAJA_DEF', 'deregistration_reason'),
    ('CATEGORÍA_VEHÍCULO_ELÉCTRICO', 'electric_category'),
    ('COD_TIPO', 'vehicle_type'),
    ('COD_PROVINCIA_VEH', 'province'),
]

# DGT field -> catalogue it must validate against.
CHECK = [('COD_CLASE_MAT', 'plate_class'), ('COD_PROCEDENCIA_ITV', 'origin'),
         ('SERVICIO', 'service'), ('COD_PROPULSION_ITV', 'propulsion'),
         ('CLAVE_TRAMITE', 'procedure_type'), ('IND_BAJA_DEF', 'deregistration_reason'),
         ('CATEGORIA_VEHICULO_ELECTRICO', 'electric_category'),
         ('COD_TIPO', 'vehicle_type'), ('COD_PROVINCIA_VEH', 'province'),
         ('COD_PROVINCIA_MAT', 'province')]


def catalogue_of(title):
    for prefix, name in CATALOGUE:
        if title.startswith(prefix):
            return name
    return None


def parse_document():
    """The document's tables, as {catalogue: [(code, description)]}."""
    tables = collections.OrderedDict()
    current = None
    with io.open(DOC, encoding='utf-8') as f:
        for line in f:
            if line.startswith('## '):
                current = catalogue_of(line[3:].strip())
                if current and current not in tables:
                    tables[current] = []
                continue
            if not current or not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) != 2 or cells[0] in ('Código', '---') or set(cells[0]) <= set('-: '):
                continue
            code, description = cells
            # "0, blanco o nulo" and "blanco, nulo o 0" describe a blank plus a
            # code. The words are not codes: only what is left after them is.
            if 'blanco' in code or 'nulo' in code:
                for token in re.findall(r'[A-Za-z0-9]+', code):
                    if token not in ('blanco', 'nulo', 'o', 'y'):
                        tables[current].append((token, description))
                tables[current].append(('', description))
                continue
            description = re.sub(r'\s*\(sólo en `[^`]+`\)', '', description)
            tables[current].append((code, description))
    return tables


def write_tsv(tables):
    if not os.path.isdir(CODES):
        os.makedirs(CODES)
    for name, rows in tables.items():
        path = os.path.join(CODES, '%s.tsv' % name)
        with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('code\tdescription\n')
            for code, description in rows:
                f.write('%s\t%s\n' % (code, description))
        print('%-28s %3d códigos  ->  codes/%s.tsv' % (name, len(rows), name))


def load_layout():
    fields = {}
    with io.open(LAYOUT, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            row = dict(zip(head, line.rstrip('\n').split('\t')))
            fields[row['campo']] = (int(row['inicio']) - 1, int(row['longitud']))
    return fields


def check(paths, tables):
    layout = load_layout()
    known = dict((name, set(c for c, _ in rows)) for name, rows in tables.items())
    unknown = collections.defaultdict(collections.Counter)
    for path in paths:
        with zipfile.ZipFile(path) as z:
            inner = [x for x in z.namelist() if x.lower().endswith('.txt')][0]
            with z.open(inner) as f:
                for raw in f:
                    raw = raw.rstrip(b'\r\n')
                    if len(raw) != 714:
                        continue
                    text = raw.decode('latin-1')
                    for field, name in CHECK:
                        start, length = layout[field]
                        value = text[start:start + length].strip()
                        if value not in known[name]:
                            unknown[(field, name)][value] += 1
        sys.stderr.write('comprobado %s\n' % os.path.basename(path))

    print('\n## Códigos que llegan y no están en el Anexo I\n')
    if not unknown:
        print('Ninguno.')
        return
    print('| Campo | Catálogo | Códigos desconocidos | Registros |')
    print('|---|---|---|---:|')
    for (field, name) in sorted(unknown):
        counter = unknown[(field, name)]
        shown = ', '.join('`%s` x%d' % (c if c else '(blanco)', n)
                          for c, n in counter.most_common(8))
        print('| `%s` | %s | %s | %d |' % (field, name, shown, sum(counter.values())))


def main(argv):
    tables = parse_document()
    write_tsv(tables)
    paths = argv or sorted(glob.glob(os.path.join(RAW, 'export_mensual_*.zip')))
    check(paths, tables)


if __name__ == '__main__':
    main(sys.argv[1:])
