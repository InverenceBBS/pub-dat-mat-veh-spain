-- ============================================================================
-- matveh - what to look at after a load, and what each number has to match
--
--   psql -d matveh -f schema/checks.sql
--
-- These are not tests that pass or fail: they are the figures that phase 0
-- measured over the same files WITHOUT a database, so any difference between
-- the two columns is a bug in the load and not an opinion. The expected values
-- are in doc/fase0-resultados.md.
-- ============================================================================

\echo ''
\echo '=== 1. Ficheros cargados, y si las filas cuadran con las líneas del fichero'
SELECT kind, granularity, period, file_name, line_count, row_count,
       line_count - row_count AS descartadas,
       short_line_count AS cortas, header_line_count AS cabeceras, is_superseded
  FROM spain.source_file
 ORDER BY kind, period, file_name;

\echo ''
\echo '=== 2. Eventos cargados por mes, contra lo que dice el control de cargas'
SELECT 'registration' AS tabla, r.period, count(*) AS filas,
       (SELECT sum(row_count) FROM spain.source_file f
         WHERE f.kind = 'registration' AND f.period = r.period AND NOT f.is_superseded)
       AS segun_source_file
  FROM spain.registration r GROUP BY r.period
UNION ALL
SELECT 'deregistration', d.period, count(*),
       (SELECT sum(row_count) FROM spain.source_file f
         WHERE f.kind = 'deregistration' AND f.period = d.period AND NOT f.is_superseded)
  FROM spain.deregistration d GROUP BY d.period
 ORDER BY 1, 2;

\echo ''
\echo '=== 3. Las dimensiones: cuántas filas y cuánto deduplican'
SELECT 'vehicle_spec' AS dimension, count(*) AS filas,
       round(( (SELECT count(*) FROM spain.registration)
             + (SELECT count(*) FROM spain.deregistration))::numeric
             / greatest(count(*), 1), 1) AS eventos_por_fila
  FROM spain.vehicle_spec
UNION ALL
SELECT 'place', count(*), NULL FROM spain.place
UNION ALL
SELECT 'municipality', count(*), NULL FROM spain.municipality;

\echo ''
\echo '=== 4. Reparto de trámites: comparar con la medición 10 de la fase 0'
SELECT period, procedure_code, count(*)
  FROM spain.registration GROUP BY 1, 2 ORDER BY 1, 2;
SELECT period, procedure_code, count(*)
  FROM spain.deregistration GROUP BY 1, 2 ORDER BY 1, 2;

\echo ''
\echo '=== 5. La contraseña de homologación: 0% en mensuales, 97,7% en diarios'
SELECT f.granularity,
       count(*) FILTER (WHERE s.type_approval IS NOT NULL) AS con_contrasena,
       count(*) AS eventos,
       round(100.0 * count(*) FILTER (WHERE s.type_approval IS NOT NULL)
             / greatest(count(*), 1), 1) AS porcentaje
  FROM spain.registration r
  JOIN spain.vehicle_spec s USING (spec_pk)
  JOIN spain.source_file f ON f.kind = 'registration' AND f.period = r.period
                          AND NOT f.is_superseded
 GROUP BY 1;

\echo ''
\echo '=== 6. Códigos que llegaron y no están en el Anexo I'
SELECT 'service' AS catalogo, code, description FROM spain.service WHERE NOT is_documented
UNION ALL SELECT 'propulsion', code, description FROM spain.propulsion WHERE NOT is_documented
UNION ALL SELECT 'vehicle_type', code, description FROM spain.vehicle_type WHERE NOT is_documented
UNION ALL SELECT 'procedure_type', code, description FROM spain.procedure_type WHERE NOT is_documented
UNION ALL SELECT 'origin', code, description FROM spain.origin WHERE NOT is_documented
UNION ALL SELECT 'province', code, description FROM spain.province WHERE NOT is_documented
UNION ALL SELECT 'electric_category', code, description FROM spain.electric_category WHERE NOT is_documented
UNION ALL SELECT 'plate_class', code, description FROM spain.plate_class WHERE NOT is_documented
 ORDER BY 1, 2;

\echo ''
\echo '=== 7. El reparto por clase de tamaño, que es lo que el encargo pide contar'
SELECT c.code, c.description, count(*) AS altas
  FROM spain.park_entry e
  JOIN spain.vehicle_spec s USING (spec_pk)
  RIGHT JOIN spain.size_class c ON c.code = s.size_class_code
 GROUP BY c.code, c.description, c.sort_order
 ORDER BY c.sort_order;

\echo ''
\echo '=== 8. Entradas y salidas del parque, que es para lo que existe todo esto'
SELECT period, count(*) AS entradas FROM spain.park_entry GROUP BY 1 ORDER BY 1;
SELECT period, count(*) AS salidas  FROM spain.park_exit  GROUP BY 1 ORDER BY 1;

\echo ''
\echo '=== 9. Lo que ocupa cada cosa'
SELECT relname AS tabla, pg_size_pretty(pg_total_relation_size(c.oid)) AS tamano
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'spain' AND c.relkind IN ('r', 'p')
 ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 15;
