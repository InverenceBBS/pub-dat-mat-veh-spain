#!/usr/bin/env python3
"""Does the technical-sheet dimension saturate, or does it grow with the events?

    python3 spec_growth.py file.zip [file.zip ...]      in chronological order

Per-file cardinality says nothing about the size of the dimension: what matters
is how many sheets each new month ADDS. If most sheets of a month were already
seen, the dimension saturates and stays small; if not, it grows with the events
and it is not a dimension at all.

Two definitions are followed at once: the full sheet, and just brand + model +
type + propulsion, which is the coarsest thing that still says what the vehicle
is.
"""
import hashlib
import io
import os
import sys
import zipfile

LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'doc',
                      'record-layout.tsv')

FULL = ['MARCA_ITV', 'MODELO_ITV', 'FABRICANTE_ITV', 'TIPO_ITV', 'VARIANTE_ITV',
        'VERSION_ITV', 'CONTRASENA_HOMOLOGACION_ITV', 'COD_TIPO',
        'CATEGORIA_HOMOLOGACION_EUROPEA_ITV', 'CARROCERIA', 'COD_PROPULSION_ITV',
        'TIPO_ALIMENTACION_ITV', 'CLASIFICACION_REGLAMENTO_VEHICULOS_ITV',
        'NIVEL_EMISIONES_EURO_ITV', 'CATEGORIA_VEHICULO_ELECTRICO',
        'DISTANCIA_EJES_12_ITV', 'VIA_ANTERIOR_ITV', 'VIA_POSTERIOR_ITV',
        'CILINDRADA_ITV', 'KW_ITV', 'POTENCIA_ITV', 'TARA', 'PESO_MAX',
        'MASA_MAXIMA_TECNICA_ADMISIBLE_ITV', 'MASA_ORDEN_MARCHA_ITV', 'CO2_ITV',
        'NUM_PLAZAS', 'NUM_PLAZAS_MAX', 'PLAZAS_PIE', 'AUTONOMIA_VEHICULO_ELECTRICO',
        'CONSUMO_WH_KM_ITV', 'MARCA_VEHICULO_BASE', 'FABRICANTE_VEHICULO_BASE',
        'TIPO_VEHICULO_BASE', 'VARIANTE_VEHICULO_BASE', 'VERSION_VEHICULO_BASE']
COARSE = ['MARCA_ITV', 'MODELO_ITV', 'COD_TIPO', 'COD_PROPULSION_ITV']
# What the sheet would be if variant and version -- the two fields that look
# like a per-unit configuration code -- were left out of the key.
NO_VARIANT = [f for f in FULL if f not in ('VARIANTE_ITV', 'VERSION_ITV')]

# The classifying identity: what the vehicle IS, with nothing that looks like a
# per-unit configuration code and no measurement. This is the candidate for a
# dimension that groups, as opposed to one that merely deduplicates.
MODEL = ['MARCA_ITV', 'MODELO_ITV', 'COD_TIPO', 'COD_PROPULSION_ITV',
         'CATEGORIA_HOMOLOGACION_EUROPEA_ITV', 'CARROCERIA',
         'CLASIFICACION_REGLAMENTO_VEHICULOS_ITV', 'TIPO_ALIMENTACION_ITV',
         'CATEGORIA_VEHICULO_ELECTRICO', 'FABRICANTE_ITV']
MODEL_NO_MAKER = [f for f in MODEL if f != 'FABRICANTE_ITV']

SETS = [('ficha completa', FULL), ('sin variante ni version', NO_VARIANT),
        ('modelo (clasificacion + fabricante)', MODEL),
        ('modelo sin fabricante', MODEL_NO_MAKER),
        ('marca+modelo+tipo+propulsion', COARSE)]


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
    seen = [set() for _ in SETS]
    events = 0
    print('| Fichero | Registros | ' + ' | '.join(
        '%s: nuevas / acumuladas' % name for name, _ in SETS) + ' |')
    print('|---|---:|' + '---:|' * len(SETS))
    for path in argv:
        before = [len(s) for s in seen]
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
                    for i, (_, names) in enumerate(SETS):
                        key = '\x1f'.join(text[layout[n][0]:layout[n][0] + layout[n][1]].strip()
                                          for n in names)
                        seen[i].add(hashlib.blake2b(key.encode('utf-8'), digest_size=16).digest())
        events += total
        cells = []
        for i in range(len(SETS)):
            cells.append('%d / %d' % (len(seen[i]) - before[i], len(seen[i])))
        print('| %s | %d | %s |' % (os.path.basename(path), total, ' | '.join(cells)))
        sys.stderr.write('hecho %s\n' % os.path.basename(path))
    print('\nEventos acumulados: %d' % events)
    for i, (name, names) in enumerate(SETS):
        print('- %s: %d filas, el %.1f%% de los eventos' % (name, len(seen[i]),
              100.0 * len(seen[i]) / max(events, 1)))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
