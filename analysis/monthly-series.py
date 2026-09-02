#!/usr/bin/env python3
"""Monthly series out of the loaded data: the figures and the charts of
doc/estadisticas.md.

    python3 monthly-series.py [--out doc]

Reads as archive_rw through psql -- no driver, no privilege -- and writes the
PNGs and the markdown. Rerun it and everything is regenerated: the document is
derived, never edited by hand.

Two things it takes care of on purpose:

  - Cars go in their own chart. They are three quarters of the market, so on a
    shared axis everything else is a flat line at the bottom.
  - Every legend runs across the FULL WIDTH of the figure, wrapping as needed.
    Width is what a time series has to spare and height is what it lacks.
"""
import csv
import io
import os
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')                       # no display on a server
import matplotlib.pyplot as plt             # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'doc')
IMG = os.path.join(OUT, 'img')
DATABASE = os.environ.get('MATVEH_DATABASE', 'matveh')

# A brand-neutral, colour-blind-safe sequence, and the greys for what is not a
# protagonist.
COLOURS = ['#3366cc', '#dc3912', '#109618', '#ff9900', '#990099', '#0099c6',
           '#dd4477', '#66aa00', '#b82e2e', '#316395', '#994499', '#22aa99',
           '#aaaa11', '#6633cc']


def query(sql):
    """Rows of a query, as lists of strings, through psql."""
    out = subprocess.run(
        ['psql', '-X', '-P', 'pager=off', '-v', 'ON_ERROR_STOP=1', '-d', DATABASE,
         '-c', 'COPY (%s) TO STDOUT WITH (FORMAT csv)' % sql],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    text = out.stdout.decode('utf-8', 'replace')
    if out.returncode:
        raise RuntimeError('psql falló:\n%s' % text)
    # A real CSV reader and not a split on commas: descriptions carry commas of
    # their own -- 'Camión ligero, hasta 12 t' -- and quoting has to be honoured.
    return [row for row in csv.reader(io.StringIO(text)) if row]


def wide_legend(axes, handles, labels):
    """A legend across the whole width, below the plot, wrapping by itself.

    Never a narrow column at one side: that steals width from the data and
    wastes height. Horizontal and below is the one that wraps on its own.
    """
    columns = max(1, min(len(labels), 5))
    axes.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.12),
                ncol=columns, frameon=False, fontsize=9)


def thousands(value, _):
    return format(int(value), ',d').replace(',', '.')


def line_chart(name, title, subtitle, months, series, height=4.2):
    figure, axes = plt.subplots(figsize=(11, height))
    for i, (label, values) in enumerate(series):
        axes.plot(months, values, label=label, linewidth=1.6,
                  color=COLOURS[i % len(COLOURS)])
    axes.set_title(title, fontsize=13, loc='left', pad=14)
    if subtitle:
        axes.text(0, 1.02, subtitle, transform=axes.transAxes, fontsize=9,
                  color='#555555')
    axes.yaxis.set_major_formatter(FuncFormatter(thousands))
    axes.grid(axis='y', color='#dddddd', linewidth=0.6)
    axes.set_axisbelow(True)
    for side in ('top', 'right'):
        axes.spines[side].set_visible(False)
    step = max(1, len(months) // 12)
    axes.set_xticks(range(0, len(months), step))
    axes.set_xticklabels([months[i][:7] for i in range(0, len(months), step)],
                         rotation=45, ha='right', fontsize=8)
    wide_legend(axes, *axes.get_legend_handles_labels())
    figure.tight_layout()
    path = os.path.join(IMG, name)
    figure.savefig(path, dpi=110, bbox_inches='tight')
    plt.close(figure)
    print('escrito %s' % path)


def pivot(rows, months):
    """rows of (month, key, count) -> [(key, [count per month])], biggest first."""
    index = dict((m, i) for i, m in enumerate(months))
    series = {}
    for month, key, count in rows:
        if month not in index:
            continue
        series.setdefault(key, [0] * len(months))[index[month]] = int(count)
    return sorted(series.items(), key=lambda kv: -sum(kv[1]))


def main(argv):
    global OUT, IMG
    if '--out' in argv:
        OUT = argv[argv.index('--out') + 1]
        IMG = os.path.join(OUT, 'img')
    for directory in (OUT, IMG):
        if not os.path.isdir(directory):
            os.makedirs(directory)

    # ── The months that have data, and only the complete ones ───────────────
    months = [r[0] for r in query(
        "SELECT period::text FROM spain.registration GROUP BY period "
        "HAVING count(*) > 20000 ORDER BY period")]
    print('%d meses con datos, de %s a %s' % (len(months), months[0], months[-1]))

    # ── 1. In and out of the fleet ──────────────────────────────────────────
    entries = dict(query("SELECT period::text, count(*)::text FROM spain.park_entry "
                         "GROUP BY period ORDER BY period"))
    # Exits split in three, because they are NOT the same thing and adding them
    # up produces a chart that lies. In 2024-02 the DGT wrote off 694.219
    # vehicles under reason 4, 'otros motivos', with a mean age of 50 years:
    # those left the register, not the road. The same goes for the 199.177
    # written off ex officio in 2025-12.
    exits = query(
        "SELECT period::text, "
        "       CASE WHEN reason_code = '4' THEN 'Depuración del registro' "
        "            WHEN reason_code IN ('A','B') THEN 'Bajas de oficio' "
        "            ELSE 'Bajas ordinarias' END, count(*)::text "
        "  FROM spain.park_exit GROUP BY 1, 2 ORDER BY 1")
    line_chart('altas-bajas.png',
               'Entradas y salidas del parque de vehículos',
               'Las salidas van separadas: una depuración del registro no es un vehículo que deja de rodar. Las bajas temporales no cuentan, porque el vehículo vuelve.',
               months,
               [('Entradas', [int(entries.get(m, 0)) for m in months])]
               + [(k, v) for k, v in pivot(exits, months)])

    # ── 2 and 3. By size class: cars apart from everything else ─────────────
    by_class = query(
        "SELECT e.period::text, s.size_class_code, count(*)::text "
        "  FROM spain.park_entry e JOIN spain.vehicle_spec s USING (spec_pk) "
        " WHERE s.size_class_code IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2")
    names = dict(query("SELECT code, description FROM spain.size_class"))
    cars = [(names.get(k, k), v) for k, v in pivot(by_class, months) if k.startswith('CAR_')]
    rest = [(names.get(k, k), v) for k, v in pivot(by_class, months) if not k.startswith('CAR_')]
    line_chart('turismos.png', 'Altas de turismos por tamaño',
               'Cortes absolutos de masa: menos de 1.200 kg, de 1.200 a 1.749, y 1.750 o más.',
               months, cars)
    line_chart('resto.png', 'Altas del resto de vehículos, por clase',
               'Todo lo que no es turismo. En su propio gráfico porque los turismos son tres cuartas partes del mercado.',
               months, rest, height=4.8)

    # ── 4. Electrification ──────────────────────────────────────────────────
    fuel = query(
        "SELECT e.period::text, "
        "       CASE WHEN s.electric_category_code IN ('BEV','PHEV','REEV') THEN 'Eléctrico enchufable' "
        "            WHEN s.electric_category_code IN ('HEV','NOVC','HVE') THEN 'Híbrido no enchufable' "
        "            WHEN s.propulsion_code = '0' THEN 'Gasolina' "
        "            WHEN s.propulsion_code = '1' THEN 'Diésel' "
        "            WHEN s.propulsion_code IS NULL THEN 'Sin informar' "
        "            ELSE 'Otras' END, count(*)::text "
        "  FROM spain.park_entry e JOIN spain.vehicle_spec s USING (spec_pk) "
        " GROUP BY 1, 2 ORDER BY 1, 2")
    line_chart('propulsion.png', 'Altas por tipo de propulsión',
               'El híbrido no enchufable sale de CATEGORIA_VEHICULO_ELECTRICO, no de la propulsión, que en esos vehículos dice gasolina.',
               months, [(k, v) for k, v in pivot(fuel, months)])

    # ── 5. Age at scrapping ─────────────────────────────────────────────────
    # From registration_date, which is complete, and NOT from
    # first_registration_date, which the DGT fills in 4-13% of the records.
    age = query(
        "SELECT period::text, "
        "       round(percentile_cont(0.5) WITHIN GROUP "
        "             (ORDER BY (procedure_date - registration_date) / 365.25)::numeric, 2)::text "
        "  FROM spain.park_exit WHERE registration_date IS NOT NULL "
        "   AND procedure_date > registration_date GROUP BY 1 ORDER BY 1")
    age_by_month = dict(age)
    exit_months = [m for m in months if m in age_by_month]
    figure, axes = plt.subplots(figsize=(11, 3.6))
    axes.plot(exit_months, [float(age_by_month[m]) for m in exit_months],
              linewidth=1.8, color=COLOURS[1], label='Edad mediana a la baja definitiva')
    axes.set_title('Edad del vehículo al salir del parque', fontsize=13, loc='left', pad=14)
    axes.text(0, 1.02, 'Años entre la matriculación y la baja definitiva, mediana de cada mes.',
              transform=axes.transAxes, fontsize=9, color='#555555')
    axes.grid(axis='y', color='#dddddd', linewidth=0.6)
    axes.set_axisbelow(True)
    for side in ('top', 'right'):
        axes.spines[side].set_visible(False)
    step = max(1, len(exit_months) // 12)
    axes.set_xticks(range(0, len(exit_months), step))
    axes.set_xticklabels([exit_months[i][:7] for i in range(0, len(exit_months), step)],
                         rotation=45, ha='right', fontsize=8)
    wide_legend(axes, *axes.get_legend_handles_labels())
    figure.tight_layout()
    figure.savefig(os.path.join(IMG, 'edad-a-la-baja.png'), dpi=110, bbox_inches='tight')
    plt.close(figure)
    print('escrito %s' % os.path.join(IMG, 'edad-a-la-baja.png'))

    # ── The tables of the document ──────────────────────────────────────────
    yearly = query(
        "SELECT to_char(period, 'YYYY'), "
        "       sum(CASE WHEN t = 'e' THEN n ELSE 0 END)::text, "
        "       sum(CASE WHEN t = 's' THEN n ELSE 0 END)::text "
        "  FROM (SELECT period, 'e' AS t, count(*) AS n FROM spain.park_entry GROUP BY 1 "
        "        UNION ALL "
        "        SELECT period, 's', count(*) FROM spain.park_exit GROUP BY 1) x "
        " GROUP BY 1 ORDER BY 1")
    size_share = query(
        "SELECT c.description, count(*)::text, "
        "       round(100.0 * count(*) / (SELECT count(*) FROM spain.park_entry e2 "
        "         JOIN spain.vehicle_spec s2 USING (spec_pk) "
        "        WHERE s2.size_class_code IS NOT NULL), 1)::text "
        "  FROM spain.park_entry e JOIN spain.vehicle_spec s USING (spec_pk) "
        "  JOIN spain.size_class c ON c.code = s.size_class_code "
        " GROUP BY c.description, c.sort_order ORDER BY c.sort_order")
    provinces = query(
        "SELECT p.description, count(*)::text FROM spain.park_entry e "
        "  JOIN spain.place pl USING (place_pk) JOIN spain.province p "
        "    ON p.code = pl.province_code "
        " GROUP BY 1 ORDER BY count(*) DESC LIMIT 12")
    io.open(os.path.join(HERE, 'series.tsv'), 'w', encoding='utf-8').write(
        '\n'.join('\t'.join(r) for r in yearly + size_share + provinces))
    print('\n=== POR AÑO (año, entradas, salidas)')
    for r in yearly:
        print('\t'.join(r))
    print('\n=== POR TAMAÑO (clase, altas, %)')
    for r in size_share:
        print('\t'.join(r))
    print('\n=== POR PROVINCIA (provincia, altas)')
    for r in provinces:
        print('\t'.join(r))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
