#!/usr/bin/env python3
"""Loads DGT files into the spain schema of matveh.

    python3 load.py --codes                  the Anexo I catalogues, from codes/
    python3 load.py file.zip [file.zip ...]  those files
    python3 load.py --monthly                every monthly file in the raw store
    python3 load.py --pending                whatever is downloaded and not loaded
    python3 load.py --dry-run file.zip       prints the SQL instead of running it

One transaction per file, and the unit is the period: loading a month drops its
partition and fills it again, so running this twice leaves the same thing. The
monthly file supersedes the dailies of its period without asking.

The heavy lifting is PostgreSQL's: this only slices the fixed-width line and
hands it over. Nothing is inserted row by row, so no driver is needed -- psql
takes the whole script, data included, through its standard input.

ENCODING. Everything ends up as UTF-8, which is what the database is. The
conversion from the source's ISO-8859-1 happens HERE, on reading the ZIP, and
not in the COPY: the script and the data travel down the same pipe, and asking
psql to read one half as UTF-8 and the other as LATIN1 is asking for trouble.
"""
import glob
import io
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get('MATVEH_RAW', '/data/matveh/raw')
CODES = os.path.join(HERE, '..', 'codes')
LAYOUT = os.path.join(HERE, '..', 'doc', 'record-layout.tsv')
DATABASE = os.environ.get('MATVEH_DATABASE', 'matveh')
WIDTH = 714
HEADER = 'Veh'          # the header line starts with "Vehículos matriculados."

# ── What each DGT field becomes ─────────────────────────────────────────────
# (column, DGT field, conversion). The conversions are the functions of the
# schema, so the rule lives in one place only.
SPEC = [
    ('vehicle_type_code', 'COD_TIPO', 'text'),
    ('propulsion_code', 'COD_PROPULSION_ITV', 'text'),
    ('electric_category_code', 'CATEGORIA_VEHICULO_ELECTRICO', 'text'),
    ('brand', 'MARCA_ITV', 'text'),
    ('model', 'MODELO_ITV', 'text'),
    ('manufacturer', 'FABRICANTE_ITV', 'text'),
    ('itv_type', 'TIPO_ITV', 'text'),
    ('itv_variant', 'VARIANTE_ITV', 'text'),
    ('itv_version', 'VERSION_ITV', 'text'),
    ('type_approval', 'CONTRASENA_HOMOLOGACION_ITV', 'text'),
    ('eu_category', 'CATEGORIA_HOMOLOGACION_EUROPEA_ITV', 'text'),
    ('body_code', 'CARROCERIA', 'text'),
    ('rd2822_class', 'CLASIFICACION_REGLAMENTO_VEHICULOS_ITV', 'text'),
    ('euro_level', 'NIVEL_EMISIONES_EURO_ITV', 'text'),
    ('fuel_feed_code', 'TIPO_ALIMENTACION_ITV', 'text'),
    ('base_brand', 'MARCA_VEHICULO_BASE', 'text'),
    ('base_manufacturer', 'FABRICANTE_VEHICULO_BASE', 'text'),
    ('base_type', 'TIPO_VEHICULO_BASE', 'text'),
    ('base_variant', 'VARIANTE_VEHICULO_BASE', 'text'),
    ('base_version', 'VERSION_VEHICULO_BASE', 'text'),
    ('displacement_cc', 'CILINDRADA_ITV', 'measure_int'),
    ('kerb_weight_kg', 'TARA', 'measure_int'),
    ('max_weight_kg', 'PESO_MAX', 'measure_int'),
    ('running_mass_kg', 'MASA_ORDEN_MARCHA_ITV', 'measure_int'),
    ('max_technical_mass_kg', 'MASA_MAXIMA_TECNICA_ADMISIBLE_ITV', 'measure_int'),
    ('electric_range_km', 'AUTONOMIA_VEHICULO_ELECTRICO', 'measure_int'),
    ('fiscal_power_cvf', 'POTENCIA_ITV', 'measure_num'),
    ('power_kw', 'KW_ITV', 'measure_num'),
    ('wheelbase_mm', 'DISTANCIA_EJES_12_ITV', 'measure_small'),
    ('front_track_mm', 'VIA_ANTERIOR_ITV', 'measure_small'),
    ('rear_track_mm', 'VIA_POSTERIOR_ITV', 'measure_small'),
    ('co2_g_km', 'CO2_ITV', 'measure_small'),
    ('consumption_wh_km', 'CONSUMO_WH_KM_ITV', 'measure_small'),
    ('seats', 'NUM_PLAZAS', 'count_small'),
    ('max_seats', 'NUM_PLAZAS_MAX', 'count_small'),
    ('standing_places', 'PLAZAS_PIE', 'count_small'),
]
PLACE = [
    ('ine_code', 'COD_MUNICIPIO_INE_VEH', 'text'),
    ('municipality_name', 'MUNICIPIO', 'text'),
    ('province_code', 'COD_PROVINCIA_VEH', 'text'),
    ('postal_code', 'CODIGO_POSTAL', 'text'),
    ('locality', 'LOCALIDAD_VEHICULO', 'text'),
]
EVENT = [
    ('procedure_date', 'FEC_TRAMITE', 'date'),
    ('registration_date', 'FEC_MATRICULA', 'date'),
    ('first_registration_date', 'FEC_PRIM_MATRICULACION', 'date'),
    ('process_date', 'FEC_PROCESO', 'date'),
    ('last_transfer_date', 'FEC_TRAMITACION', 'date'),
    ('service_code', 'SERVICIO', 'text'),
    ('plate_province_code', 'COD_PROVINCIA_MAT', 'text'),
    ('procedure_code', 'CLAVE_TRAMITE', 'text'),
    ('plate_class_code', 'COD_CLASE_MAT', 'text'),
    ('origin_code', 'COD_PROCEDENCIA_ITV', 'text'),
    ('reason_code', 'IND_BAJA_DEF', 'text'),
    ('transfer_count', 'NUM_TRANSMISIONES', 'count_small'),
    ('owner_count', 'NUM_TITULARES', 'count_small'),
    ('is_renting', 'RENTING', 'flag'),
    ('is_telematic', 'BAJA_TELEMATICA', 'telematic'),
    ('is_legal_person', 'PERSONA_FISICA_JURIDICA', 'legal'),
    ('is_used', 'IND_NUEVO_USADO', 'used'),
]
# Which catalogue each coded column validates against, so that a code that is
# not in the Anexo I is registered instead of rejecting the row.
# 'province_code' is the one in place and municipality, and it was missing here:
# a '?' turned up in COD_PROVINCIA_VEH in 2017-03 and stopped the load. Every
# column with a foreign key to a catalogue has to be in this list.
CATALOGUE_OF = [('service_code', 'service'), ('plate_province_code', 'province'),
                ('province_code', 'province'),
                ('procedure_code', 'procedure_type'), ('plate_class_code', 'plate_class'),
                ('origin_code', 'origin'), ('reason_code', 'deregistration_reason'),
                ('vehicle_type_code', 'vehicle_type'), ('propulsion_code', 'propulsion'),
                ('electric_category_code', 'electric_category')]
CODE_FILES = ['plate_class', 'origin', 'service', 'propulsion', 'procedure_type',
              'deregistration_reason', 'electric_category', 'vehicle_type', 'province']


def layout():
    fields = {}
    with io.open(LAYOUT, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            row = dict(zip(head, line.rstrip('\n').split('\t')))
            fields[row['campo']] = (int(row['inicio']), int(row['longitud']))
    return fields


def slice_of(field, conversion, fields):
    """The SQL that extracts one field from the raw line, already converted."""
    start, length = fields[field]
    raw = 'substr(line, %d, %d)' % (start, length)
    if conversion == 'text':
        return 'spain.dgt_text(%s)' % raw
    if conversion == 'date':
        return 'spain.dgt_date(%s)' % raw
    # A zero in a physical measure of this source means NOT REPORTED, not zero:
    # the monthly files bring mass, wheelbase and track at 0 for whole records.
    # Storing that as a zero would drag every average down without a word.
    if conversion == 'measure_num':
        return 'nullif(spain.dgt_number(%s), 0)' % raw
    if conversion == 'measure_int':
        return 'nullif(spain.dgt_number(%s), 0)::integer' % raw
    if conversion == 'measure_small':
        return 'nullif(spain.dgt_number(%s), 0)::smallint' % raw
    # A count of zero, on the other hand, is a real zero: a trailer has no seats
    # and a new vehicle has no previous transfers.
    if conversion == 'count_small':
        return 'spain.dgt_number(%s)::smallint' % raw
    if conversion == 'flag':
        return 'spain.dgt_flag(%s)' % raw
    if conversion == 'telematic':          # 'En desguace' or blank
        return "(spain.dgt_text(%s) IS NOT NULL)" % raw
    if conversion == 'legal':              # D natural person, X legal person
        return "(CASE upper(btrim(%s)) WHEN 'X' THEN true WHEN 'D' THEN false END)" % raw
    if conversion == 'used':               # N new, U used
        return "(CASE upper(btrim(%s)) WHEN 'U' THEN true WHEN 'N' THEN false END)" % raw
    raise ValueError(conversion)


def hash_of(columns, fields):
    """sha256 over the normalised fields, which is the key of a dimension.

    The separator is a control character precisely because it cannot appear
    inside a field: with a comma, two different sheets could collide.
    """
    parts = ", ".join("coalesce(%s, '')" % slice_of(field, 'text', fields)
                      for _, field, _ in columns)
    return ("encode(sha256(convert_to(concat_ws(E'\\x1f', %s), 'UTF8')), 'hex')" % parts)


def row_in_sql(fields):
    """A temporary table with the line already sliced, converted and hashed."""
    columns = []
    for column, field, conversion in SPEC + PLACE + EVENT:
        columns.append('  %s AS %s' % (slice_of(field, conversion, fields), column))
    columns.append('  %s AS spec_hash' % hash_of(SPEC, fields))
    columns.append('  %s AS place_hash' % hash_of(PLACE, fields))
    return ("CREATE TEMP TABLE row_in ON COMMIT DROP AS\nSELECT\n%s\nFROM spain.staging_line;"
            % ',\n'.join(columns))


def literal(value):
    if value is None or value == '':
        return 'NULL'
    return "'%s'" % str(value).replace("'", "''")


DRY_RUN = False


def psql(script, database=DATABASE, quiet=True):
    """Runs a script through psql, data included, and returns its output.

    With --dry-run it prints the script instead, minus the data lines, which is
    how the generated SQL gets reviewed without a database in front.
    """
    if DRY_RUN:
        lines = [l for l in script.splitlines() if len(l) != WIDTH]
        print('\n'.join(lines))
        print('-- (y %d líneas de datos)' % (len(script.splitlines()) - len(lines)))
        return ''

    # -P pager=off because psql pages to a terminal and then waits for a
    # keypress, which would hang the load the day its output is not a pipe.
    command = ['psql', '-X', '-P', 'pager=off', '-v', 'ON_ERROR_STOP=1',
               '-d', database]
    if quiet:
        command += ['-q']
    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = process.communicate(script.encode('utf-8'))
    text = out.decode('utf-8', 'replace')
    if process.returncode:
        raise RuntimeError('psql falló:\n%s' % text)
    return text


def read_manifest():
    rows = {}
    path = os.path.join(RAW, 'manifest.tsv')
    if os.path.exists(path):
        with io.open(path, encoding='utf-8') as f:
            head = f.readline().rstrip('\n').split('\t')
            for line in f:
                row = dict(zip(head, line.rstrip('\n').split('\t')))
                rows[row['file_name']] = row
    return rows


# ── The catalogues ──────────────────────────────────────────────────────────

def load_codes():
    script = ['BEGIN;']
    for name in CODE_FILES:
        path = os.path.join(CODES, '%s.tsv' % name)
        with io.open(path, encoding='utf-8') as f:
            f.readline()
            for line in f:
                if not line.strip('\n'):
                    continue
                code, description = (line.rstrip('\n').split('\t') + [''])[:2]
                script.append(
                    "INSERT INTO spain.%s (code, description, is_documented) "
                    "VALUES (%s, %s, true) ON CONFLICT (code) DO UPDATE "
                    "SET description = excluded.description, is_documented = true;"
                    % (name, literal(code) if code else "''", literal(description)))
    script.append('COMMIT;')
    psql('\n'.join(script))
    counts = psql('\n'.join(
        "SELECT '%s', count(*) FROM spain.%s;" % (n, n) for n in CODE_FILES), quiet=False)
    print(counts.strip())


# ── One file ────────────────────────────────────────────────────────────────

def read_lines(path):
    """The records of the ZIP, decoded to UTF-8, plus what was skipped."""
    records, header_lines, short_lines = [], 0, 0
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.lower().endswith('.txt')]
        if len(inner) != 1:
            raise RuntimeError('%s trae %d ficheros .txt' % (path, len(inner)))
        with z.open(inner[0]) as f:
            for raw in f:
                text = raw.rstrip(b'\r\n').decode('latin-1')
                if not text:
                    continue
                if len(text) == WIDTH:
                    records.append(text)
                elif text.startswith(HEADER):
                    header_lines += 1
                elif len(text) == WIDTH - 7 and text.endswith('?'):
                    # FEC_PROCESO comes as '?' instead of eight digits: two such
                    # records exist in 2014-12 and they are perfectly valid.
                    records.append(text[:WIDTH - 8] + ' ' * 8)
                    short_lines += 1
                else:
                    raise RuntimeError(
                        'Línea de %d caracteres en %s, que no es cabecera ni el caso '
                        'conocido de FEC_PROCESO: %r' % (len(text), path, text[:60]))
    return records, header_lines, short_lines


def load_file(path, fields, manifest):
    name = os.path.basename(path)
    info = manifest.get(name, {})
    kind = 'deregistration' if 'bajas' in name else 'registration'
    granularity = info.get('granularity') or ('monthly' if 'mensual' in name else 'daily')
    period_digits = info.get('period') or ''.join(c for c in name if c.isdigit())
    period = '%s-%s-01' % (period_digits[:4], period_digits[4:6])
    file_date = ('%s-%s-%s' % (period_digits[:4], period_digits[4:6], period_digits[6:8])
                 if granularity == 'daily' else None)

    records, header_lines, short_lines = read_lines(path)
    event_columns = [c for c, _, _ in EVENT if c in EVENT_COLUMNS[kind]]

    # A monthly file replaces the period: its partition is emptied and rebuilt.
    # A daily one cannot do that -- the partition is monthly and holds the other
    # days -- so it deletes by process date instead.
    partition_call = ('reset_partition' if granularity == 'monthly' else 'ensure_partition')
    script = ['BEGIN;',
              "SELECT spain.%s('%s', DATE %s);" % (partition_call, kind, literal(period)),
              'TRUNCATE spain.staging_line;']
    if granularity == 'monthly':
        script.append("DELETE FROM spain.source_file WHERE kind = %s AND period = DATE %s;"
                      % (literal(kind), literal(period)))
    if granularity == 'daily':
        # A daily file cannot drop its partition, which is monthly and holds the
        # other days. It does not need to: measured over three daily files,
        # FEC_PROCESO is EXACTLY the file's date in every single record, so that
        # is what identifies what this file loaded.
        script.append("DELETE FROM spain.%s WHERE period = DATE %s AND process_date = DATE %s;"
                      % (kind, literal(period), literal(file_date)))
        script.append("DELETE FROM spain.source_file WHERE file_name = %s;" % literal(name))
    script.extend([

        "COPY spain.staging_line (line) FROM STDIN WITH "
        "(FORMAT csv, DELIMITER E'\\t', QUOTE E'\\x01');"])
    script.extend(records)
    script.append('\\.')
    script.append(row_in_sql(fields))

    spec_columns = [c for c, _, _ in SPEC]

    # Codes that are not in the Anexo I: registered, not rejected. THIS GOES
    # FIRST: vehicle_spec has foreign keys to vehicle_type, propulsion and
    # electric_category, so inserting the sheet before its codes exist fails
    # on the first s3 that turns up -- which is exactly what happened.
    available = set(EVENT_COLUMNS[kind]) | set(spec_columns) | set(c for c, _, _ in PLACE)
    for column, catalogue in CATALOGUE_OF:
        if column in available:
            script.append(
                "INSERT INTO spain.%s (code, description, is_documented)\n"
                "SELECT DISTINCT %s, 'no documentado en el Anexo I', false FROM row_in\n"
                " WHERE %s IS NOT NULL ON CONFLICT (code) DO NOTHING;"
                % (catalogue, column, column))

    # The dimensions, before the events that point at them.
    script.append(
        "INSERT INTO spain.vehicle_spec (spec_hash, %s)\n"
        "SELECT DISTINCT ON (spec_hash) spec_hash, %s FROM row_in\n"
        "ON CONFLICT (spec_hash) DO NOTHING;" % (', '.join(spec_columns), ', '.join(spec_columns)))
    script.append(
        "INSERT INTO spain.municipality (ine_code, name, province_code)\n"
        "SELECT DISTINCT ON (ine_code) ine_code, coalesce(municipality_name, ine_code),"
        " province_code\n"
        "  FROM row_in WHERE ine_code IS NOT NULL\n"
        "ON CONFLICT (ine_code) DO NOTHING;")
    script.append(
        "INSERT INTO spain.place (place_hash, municipality_pk, province_code, postal_code,"
        " locality)\n"
        "SELECT DISTINCT ON (place_hash) r.place_hash, m.municipality_pk, r.province_code,"
        " r.postal_code, r.locality\n"
        "  FROM row_in r LEFT JOIN spain.municipality m USING (ine_code)\n"
        "ON CONFLICT (place_hash) DO NOTHING;")

    # And the events. A row with no usable procedure date is not loaded: the
    # count of what was left out is written to source_file.
    select = ['DATE %s' % literal(period), 'coalesce(procedure_date, registration_date)']
    columns = ['period', 'procedure_date']
    for column in event_columns:
        if column == 'procedure_date':
            continue
        columns.append(column)
        select.append('r.%s' % column)
    columns += ['spec_pk', 'place_pk']
    select += ['s.spec_pk', 'p.place_pk']
    script.append(
        "INSERT INTO spain.%s (%s)\n"
        "SELECT %s\n"
        "  FROM row_in r\n"
        "  JOIN spain.vehicle_spec s USING (spec_hash)\n"
        "  LEFT JOIN spain.place p USING (place_hash)\n"
        " WHERE coalesce(r.procedure_date, r.registration_date) IS NOT NULL;"
        % (kind, ', '.join(columns), ', '.join(select)))

    script.append(
        "INSERT INTO spain.source_file (kind, granularity, period, file_date, file_name,"
        " url, byte_size, sha256, http_last_modified, http_etag, line_count, row_count,"
        " short_line_count, header_line_count)\n"
        "SELECT %s, %s, DATE %s, %s, %s, %s, %s, %s, %s, %s, %d, (SELECT count(*) FROM row_in),"
        " %d, %d;"
        % (literal(kind), literal(granularity), literal(period),
           'DATE ' + literal(file_date) if file_date else 'NULL',
           literal(name), literal(info.get('url')), info.get('byte_size') or 'NULL',
           literal(info.get('sha256')), literal(info.get('http_last_modified')) +
           '::timestamptz' if info.get('http_last_modified') else 'NULL',
           literal(info.get('http_etag')), len(records), short_lines, header_lines))

    if granularity == 'monthly':
        script.append(
            "UPDATE spain.source_file SET is_superseded = true\n"
            " WHERE kind = %s AND period = DATE %s AND granularity = 'daily';"
            % (literal(kind), literal(period)))
    script.append('COMMIT;')

    psql('\n'.join(script))
    print('%-38s %s %s  %7d registros%s' % (
        name, kind[:3], period[:7], len(records),
        '  (%d cortos, %d cabecera)' % (short_lines, header_lines)
        if short_lines or header_lines else ''))


EVENT_COLUMNS = {
    'registration': ['procedure_date', 'registration_date', 'first_registration_date',
                     'process_date', 'service_code', 'plate_province_code',
                     'procedure_code', 'plate_class_code', 'origin_code', 'is_used',
                     'is_renting', 'is_legal_person'],
    'deregistration': ['procedure_date', 'registration_date', 'first_registration_date',
                       'process_date', 'last_transfer_date', 'service_code',
                       'plate_province_code', 'procedure_code', 'reason_code',
                       'transfer_count', 'owner_count', 'is_telematic', 'is_renting',
                       'is_legal_person'],
}


def main(argv):
    global DRY_RUN
    if '--dry-run' in argv:
        DRY_RUN = True
        argv = [a for a in argv if a != '--dry-run']
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == '--codes':
        load_codes()
        return 0
    fields = layout()
    manifest = read_manifest()
    if argv[0] == '--monthly':
        paths = sorted(glob.glob(os.path.join(RAW, 'export_mensual_*.zip')))
    elif argv[0] == '--pending':
        loaded = set(psql("SELECT file_name FROM spain.source_file;",
                          quiet=False).split())
        paths = [p for p in sorted(glob.glob(os.path.join(RAW, '*.zip')))
                 if os.path.basename(p) not in loaded]
    else:
        paths = argv
    for path in paths:
        load_file(path, fields, manifest)
    if paths:
        # Otherwise the staging table keeps the last file loaded -- 165 MB of a
        # monthly one -- lying around until the next load needs it.
        psql('TRUNCATE spain.staging_line;')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
