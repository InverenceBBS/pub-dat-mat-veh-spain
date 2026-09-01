#!/usr/bin/env python3
"""How many distinct technical sheets are there, depending on where the line is
drawn between what belongs to the model and what varies unit by unit.

    python3 spec_cardinality.py [file.zip ...]

Measurement 2 of phase 0 said the full 36-field sheet has a cardinality of 15 %
to 56 % of the events, which is too high for the dimension to pay for itself.
This measures candidate subsets so the split can be decided with numbers.
"""
import collections
import glob
import hashlib
import io
import os
import sys
import zipfile

RAW = os.environ.get('MATVEH_RAW', '/data/matveh/raw')
LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'doc',
                      'record-layout.tsv')

IDENTITY = ['MARCA_ITV', 'MODELO_ITV', 'FABRICANTE_ITV', 'TIPO_ITV', 'VARIANTE_ITV',
            'VERSION_ITV', 'CONTRASENA_HOMOLOGACION_ITV', 'COD_TIPO',
            'CATEGORIA_HOMOLOGACION_EUROPEA_ITV', 'CARROCERIA', 'COD_PROPULSION_ITV',
            'TIPO_ALIMENTACION_ITV', 'CLASIFICACION_REGLAMENTO_VEHICULOS_ITV',
            'NIVEL_EMISIONES_EURO_ITV', 'CATEGORIA_VEHICULO_ELECTRICO']
GEOMETRY = ['DISTANCIA_EJES_12_ITV', 'VIA_ANTERIOR_ITV', 'VIA_POSTERIOR_ITV',
            'CILINDRADA_ITV', 'KW_ITV', 'POTENCIA_ITV']
WEIGHT = ['TARA', 'PESO_MAX', 'MASA_MAXIMA_TECNICA_ADMISIBLE_ITV']
UNIT = ['MASA_ORDEN_MARCHA_ITV', 'CO2_ITV']
SEATS = ['NUM_PLAZAS', 'NUM_PLAZAS_MAX', 'PLAZAS_PIE']
ELECTRIC = ['AUTONOMIA_VEHICULO_ELECTRICO', 'CONSUMO_WH_KM_ITV']
BASE = ['MARCA_VEHICULO_BASE', 'FABRICANTE_VEHICULO_BASE', 'TIPO_VEHICULO_BASE',
        'VARIANTE_VEHICULO_BASE', 'VERSION_VEHICULO_BASE']

CANDIDATES = [
    ('A. los 36 campos (lo propuesto)', IDENTITY + GEOMETRY + WEIGHT + UNIT + SEATS + ELECTRIC + BASE),
    ('B. sin masa en orden de marcha ni CO2', IDENTITY + GEOMETRY + WEIGHT + SEATS + ELECTRIC + BASE),
    ('C. B, y sin autonomia ni consumo', IDENTITY + GEOMETRY + WEIGHT + SEATS + BASE),
    ('D. identidad + geometria + pesos', IDENTITY + GEOMETRY + WEIGHT),
    ('E. identidad + geometria', IDENTITY + GEOMETRY),
    ('F. solo la identidad textual y los codigos', IDENTITY),
    ('G. marca, modelo, tipo y propulsion', ['MARCA_ITV', 'MODELO_ITV', 'COD_TIPO',
                                             'COD_PROPULSION_ITV']),
]


def load_layout():
    fields = {}
    with io.open(LAYOUT, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            row = dict(zip(head, line.rstrip('\n').split('\t')))
            fields[row['campo']] = (int(row['inicio']) - 1, int(row['longitud']))
    return fields


def main(argv):
    layout = load_layout()
    paths = argv or sorted(glob.glob(os.path.join(RAW, 'export_mensual_*.zip')))
    print('| Fichero | Eventos | ' + ' | '.join(name.split('.')[0] for name, _ in CANDIDATES) + ' |')
    print('|---|---:|' + '---:|' * len(CANDIDATES))
    rows = []
    for path in paths:
        sets = [set() for _ in CANDIDATES]
        total = 0
        with zipfile.ZipFile(path) as z:
            inner = [x for x in z.namelist() if x.lower().endswith('.txt')][0]
            with z.open(inner) as f:
                for raw in f:
                    raw = raw.rstrip(b'\r\n')
                    if len(raw) != 714:
                        continue
                    text = raw.decode('latin-1')
                    total += 1
                    for i, (_, names) in enumerate(CANDIDATES):
                        key = '\x1f'.join(text[layout[n][0]:layout[n][0] + layout[n][1]].strip()
                                          for n in names)
                        sets[i].add(hashlib.blake2b(key.encode('utf-8'), digest_size=16).digest())
        cells = ['%d (%.1f%%)' % (len(s), 100.0 * len(s) / max(total, 1)) for s in sets]
        print('| %s | %d | %s |' % (os.path.basename(path), total, ' | '.join(cells)))
        rows.append((os.path.basename(path), total, [len(s) for s in sets]))
        sys.stderr.write('hecho %s\n' % os.path.basename(path))

    print('\nQué contiene cada candidato:\n')
    for name, names in CANDIDATES:
        print('- **%s** (%d campos): %s' % (name, len(names), ', '.join('`%s`' % n for n in names)))


if __name__ == '__main__':
    main(sys.argv[1:])
