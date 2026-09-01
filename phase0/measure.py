#!/usr/bin/env python3
"""Phase 0 measurements over the downloaded DGT files.

    python3 measure.py [file.zip ...]     default: everything in the raw store

Answers the ten questions of doc/diseno-de-base-de-datos-y-etl.md before the
DDL is fixed. It touches no database: everything here is counting over text, so
it can run anywhere and needs no credentials.

Standard library only. One pass per file, and nothing kept in memory that grows
with the number of records except 16-byte digests.
"""
import collections
import glob
import hashlib
import io
import os
import sys
import zipfile

RAW = os.environ.get('MATVEH_RAW', '/data/matveh/raw')
LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'doc', 'record-layout.tsv')
WIDTH = 714
DAILY_HEADER = 'Veh'          # the daily header line starts with "Vehículos matriculados."

# The fields of each candidate dimension, by their DGT name. Same lists as the
# design document; if one changes there, it changes here.
SPEC_FIELDS = ['MARCA_ITV', 'MODELO_ITV', 'COD_TIPO', 'COD_PROPULSION_ITV',
               'CILINDRADA_ITV', 'POTENCIA_ITV', 'TARA', 'PESO_MAX', 'NUM_PLAZAS',
               'KW_ITV', 'NUM_PLAZAS_MAX', 'CO2_ITV', 'TIPO_ITV', 'VARIANTE_ITV',
               'VERSION_ITV', 'FABRICANTE_ITV', 'MASA_ORDEN_MARCHA_ITV',
               'MASA_MAXIMA_TECNICA_ADMISIBLE_ITV', 'CATEGORIA_HOMOLOGACION_EUROPEA_ITV',
               'CARROCERIA', 'PLAZAS_PIE', 'NIVEL_EMISIONES_EURO_ITV', 'CONSUMO_WH_KM_ITV',
               'CLASIFICACION_REGLAMENTO_VEHICULOS_ITV', 'CATEGORIA_VEHICULO_ELECTRICO',
               'AUTONOMIA_VEHICULO_ELECTRICO', 'MARCA_VEHICULO_BASE',
               'FABRICANTE_VEHICULO_BASE', 'TIPO_VEHICULO_BASE', 'VARIANTE_VEHICULO_BASE',
               'VERSION_VEHICULO_BASE', 'DISTANCIA_EJES_12_ITV', 'VIA_ANTERIOR_ITV',
               'VIA_POSTERIOR_ITV', 'TIPO_ALIMENTACION_ITV', 'CONTRASENA_HOMOLOGACION_ITV']
PLACE_FIELDS = ['COD_MUNICIPIO_INE_VEH', 'MUNICIPIO', 'LOCALIDAD_VEHICULO',
                'CODIGO_POSTAL', 'COD_PROVINCIA_VEH']
PLACE_NO_LOCALITY = ['COD_MUNICIPIO_INE_VEH', 'MUNICIPIO', 'CODIGO_POSTAL',
                     'COD_PROVINCIA_VEH']


def load_layout():
    fields = []
    with io.open(LAYOUT, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            row = dict(zip(head, line.rstrip('\n').split('\t')))
            fields.append((row['campo'], int(row['inicio']) - 1, int(row['longitud'])))
    assert len(fields) == 69, len(fields)
    assert sum(f[2] for f in fields) == WIDTH
    return fields


def digest(values):
    return hashlib.blake2b(('\x1f'.join(values)).encode('utf-8'), digest_size=16).digest()


class Measurement(object):
    """Everything counted in one pass over one file."""

    def __init__(self, name, period, fields):
        self.name, self.period, self.fields = name, period, fields
        self.label = ('bajas ' if 'bajas' in name else 'mat ') + period
        self.index = dict((f[0], i) for i, f in enumerate(fields))
        self.records = self.header_lines = 0
        self.line_lengths = collections.Counter()
        self.high_bytes = collections.Counter()     # 0x80-0x9F, the CP1252 range
        self.non_blank = collections.Counter()
        self.procedure = collections.Counter()
        self.spec = set()
        self.place = set()
        self.place_no_locality = set()
        self.approval = {}                          # approval+variant+version -> varies?
        self.trade_month = collections.Counter()    # month of FEC_TRAMITE vs the period
        self.tramitacion = collections.Counter()
        self.bad_lines = []

    def take(self, raw_line):
        text = raw_line.decode('latin-1')
        self.line_lengths[len(text)] += 1
        for byte in raw_line:
            if 0x80 <= byte <= 0x9F:
                self.high_bytes[byte] += 1
        if text.startswith(DAILY_HEADER) and len(text) != WIDTH:
            self.header_lines += 1
            return
        if len(text) != WIDTH:
            if len(self.bad_lines) < 3:
                self.bad_lines.append(text[:60])
            return
        self.records += 1
        value = [text[start:start + length].strip() for _, start, length in self.fields]
        get = lambda field: value[self.index[field]]                        # noqa: E731

        for i, v in enumerate(value):
            if v:
                self.non_blank[i] += 1
        self.procedure[get('CLAVE_TRAMITE')] += 1
        self.spec.add(digest([get(f) for f in SPEC_FIELDS]))
        self.place.add(digest([get(f) for f in PLACE_FIELDS]))
        self.place_no_locality.add(digest([get(f) for f in PLACE_NO_LOCALITY]))

        # 4. is the technical sheet a function of approval + variant + version?
        key = digest([get('CONTRASENA_HOMOLOGACION_ITV'), get('VARIANTE_ITV'),
                      get('VERSION_ITV')])
        seen = self.approval.get(key)
        pair = (get('CO2_ITV'), get('MASA_ORDEN_MARCHA_ITV'))
        if seen is None:
            self.approval[key] = [pair[0], pair[1], False, False]
        else:
            if pair[0] != seen[0]:
                seen[2] = True
            if pair[1] != seen[1]:
                seen[3] = True

        # 6. does the trade date fall in the file's period?
        trade = get('FEC_TRAMITE')
        self.trade_month[trade[4:8] + trade[2:4] if len(trade) == 8 else '?'] += 1

        # 7. what does FEC_TRAMITACION carry?
        tram, matr = get('FEC_TRAMITACION'), get('FEC_MATRICULA')
        self.tramitacion['vacío' if not tram.strip('0 ') else
                         '= FEC_MATRICULA' if tram == matr else
                         '= FEC_TRAMITE' if tram == trade else 'otra fecha'] += 1


def measure(path, fields):
    period = ''.join(c for c in os.path.basename(path) if c.isdigit())[-6:]
    m = Measurement(os.path.basename(path), period, fields)
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.lower().endswith('.txt')]
        assert len(inner) == 1, inner
        with z.open(inner[0]) as f:
            for raw_line in f:
                raw_line = raw_line.rstrip(b'\r\n')
                if raw_line:
                    m.take(raw_line)
    return m


def report(measurements, fields):
    out = []
    say = out.append
    say('# Fase 0 - mediciones sobre los ficheros de muestra\n')

    say('## 1. Ancho de linea y cabecera\n')
    say('| Fichero | Registros | Longitudes de linea | Cabeceras | Lineas raras |')
    say('|---|---:|---|---:|---|')
    for m in measurements:
        lengths = ', '.join('%d x%d' % (k, v) for k, v in sorted(m.line_lengths.items()))
        say('| %s | %d | %s | %d | %s |'
            % (m.name, m.records, lengths, m.header_lines, '; '.join(m.bad_lines) or '-'))

    say('\n## 2 y 3. Cardinalidad de las dimensiones\n')
    say('| Fichero | Eventos | vehicle_spec | % | place | % | place sin localidad |')
    say('|---|---:|---:|---:|---:|---:|---:|')
    for m in measurements:
        n = max(m.records, 1)
        say('| %s | %d | %d | %.1f%% | %d | %.2f%% | %d |'
            % (m.name, m.records, len(m.spec), 100.0 * len(m.spec) / n,
               len(m.place), 100.0 * len(m.place) / n, len(m.place_no_locality)))

    say('\n## 4. Varian CO2 y masa en orden de marcha dentro de la misma contrasena+variante+version?\n')
    say('| Fichero | Grupos | CO2 varia | Masa varia |')
    say('|---|---:|---:|---:|')
    for m in measurements:
        groups = len(m.approval) or 1
        co2 = sum(1 for v in m.approval.values() if v[2])
        mass = sum(1 for v in m.approval.values() if v[3])
        say('| %s | %d | %d (%.1f%%) | %d (%.1f%%) |'
            % (m.name, len(m.approval), co2, 100.0 * co2 / groups, mass, 100.0 * mass / groups))

    say('\n## 5. Cobertura por campo y por fichero (%% no blanco)\n')
    say('| # | Campo | ' + ' | '.join(m.label for m in measurements) + ' |')
    say('|---:|---|' + '---:|' * len(measurements))
    for i, (name, _, _) in enumerate(fields):
        cells = []
        for m in measurements:
            n = max(m.records, 1)
            cells.append('%.1f' % (100.0 * m.non_blank[i] / n))
        say('| %d | %s | %s |' % (i + 1, name, ' | '.join(cells)))

    say('\n## 6. Mes del tramite frente al periodo del fichero\n')
    say('| Fichero | Periodo | En el periodo | Fuera | Los tres meses mas frecuentes |')
    say('|---|---|---:|---:|---|')
    for m in measurements:
        inside = m.trade_month.get(m.period, 0)
        outside = m.records - inside
        top = ', '.join('%s: %d' % kv for kv in m.trade_month.most_common(3))
        say('| %s | %s | %d (%.2f%%) | %d (%.2f%%) | %s |'
            % (m.name, m.period, inside, 100.0 * inside / max(m.records, 1),
               outside, 100.0 * outside / max(m.records, 1), top))

    say('\n## 7. Que trae FEC_TRAMITACION\n')
    say('| Fichero | ' + ' | '.join(['vacío', '= FEC_MATRICULA', '= FEC_TRAMITE', 'otra fecha']) + ' |')
    say('|---|---:|---:|---:|---:|')
    for m in measurements:
        say('| %s | %s |' % (m.name, ' | '.join(
            str(m.tramitacion.get(k, 0)) for k in ['vacío', '= FEC_MATRICULA', '= FEC_TRAMITE', 'otra fecha'])))

    say('\n## 9. Bytes 0x80-0x9F (donde ISO-8859-1 y CP1252 difieren)\n')
    say('| Fichero | Apariciones | Detalle |')
    say('|---|---:|---|')
    for m in measurements:
        detail = ', '.join('0x%02X x%d' % kv for kv in sorted(m.high_bytes.items())) or '-'
        say('| %s | %d | %s |' % (m.name, sum(m.high_bytes.values()), detail))

    say('\n## 10. Reparto de CLAVE_TRAMITE\n')
    say('| Fichero | ' + ' | '.join('`%s`' % c for c in '1345679AB') + ' | otros |')
    say('|---|' + '---:|' * 10)
    for m in measurements:
        known = list('1345679AB')
        cells = [str(m.procedure.get(c, 0)) for c in known]
        others = sum(v for k, v in m.procedure.items() if k not in known)
        say('| %s | %s | %d |' % (m.name, ' | '.join(cells), others))

    return '\n'.join(out) + '\n'


def main(argv):
    fields = load_layout()
    paths = argv or sorted(glob.glob(os.path.join(RAW, '*.zip')))
    if not paths:
        print('No hay ficheros en %s' % RAW)
        return 1
    measurements = []
    for path in paths:
        sys.stderr.write('midiendo %s\n' % os.path.basename(path))
        measurements.append(measure(path, fields))
    sys.stdout.write(report(measurements, fields))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
