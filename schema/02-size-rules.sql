-- ============================================================================
-- matveh - the coarse size classes, and the rules that assign them
--
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -d matveh -f 02-size-rules.sql
--
-- Separate from the schema on purpose: this is the part that WILL change. Every
-- threshold here is ours, none comes from the DGT, and none has been validated
-- by anyone yet. Re-run this file and then spain.classify_size() and the whole
-- history is reclassified without touching a single event row.
--
-- WHY IT IS NEEDED. The encargo asks to tell apart "coches pequeños, medianos,
-- grandes, todo-terrenos, furgonetas, camiones pequeños". Most of that is
-- already in COD_TIPO, but not the size of a car, and not the SUV: measured,
-- COD_TIPO 25 (todo terreno) caught 124 vehicles on a day with 7.724 cars,
-- because SUVs are registered as cars. So a car's size is DERIVED here, out of
-- wheelbase and mass, which have 100% coverage in the daily files.
--
-- WHAT IS STILL WRONG WITH IT, said plainly: this separates cars by size, not
-- SUVs from saloons. A long-wheelbase estate and an SUV land in the same class.
-- Telling them apart needs ground clearance or body height, which the record
-- does not carry -- see doc/alcance.md.
-- ============================================================================

SET ROLE model_archive;

BEGIN;

TRUNCATE spain.size_rule;
DELETE FROM spain.size_class;

INSERT INTO spain.size_class (code, description, sort_order) VALUES
  ('CAR_S',   'Turismo pequeño',                        10),
  ('CAR_M',   'Turismo mediano',                        20),
  ('CAR_L',   'Turismo grande',                         30),
  ('OFFROAD', 'Todo terreno declarado como tal',        40),
  ('VAN',     'Furgoneta y derivados',                  50),
  ('TRUCK_L', 'Camión ligero, hasta 12 t',              60),
  ('TRUCK_H', 'Camión pesado y tractocamión',           70),
  ('BUS',     'Autobús y autocar',                      80),
  ('MOTO',    'Motocicleta y similares',                90),
  ('MOPED',   'Ciclomotor y cuatriciclo ligero',       100),
  ('TRAILER', 'Remolque y semirremolque',              110),
  ('AGRI',    'Tractor y maquinaria agrícola',         120),
  ('SPECIAL', 'Vehículo especial y obras',             130),
  ('OTHER',   'Sin clasificar',                        140);

-- Rules are tried in priority order and the first match wins. A NULL bound is
-- "do not care"; a bound against a NULL measurement never matches, which is
-- what makes the wheelbase rules fall through to the mass ones when the file
-- brings no geometry -- the monthly files often do not.
INSERT INTO spain.size_rule
  (priority, size_class_code, vehicle_type_pattern, min_mass_kg, max_mass_kg,
   min_wheelbase_mm, max_wheelbase_mm, note) VALUES
  -- What COD_TIPO already says, and says well.
  (10,  'MOPED',   '^(9[012])$',        NULL, NULL, NULL, NULL, 'ciclomotores y cuatriciclo ligero'),
  (20,  'MOTO',    '^(5[01234])$',      NULL, NULL, NULL, NULL, 'motocicletas, motocarro, triciclo, cuatriciclo pesado'),
  (30,  'TRAILER', '^([RS].)$',         NULL, NULL, NULL, NULL, 'remolques y semirremolques'),
  (40,  'BUS',     '^(3[0-6])$',        NULL, NULL, NULL, NULL, 'autobuses'),
  (50,  'AGRI',    '^(80|82|7[HI])$',   NULL, NULL, NULL, NULL, 'tractores y maquinaria agrícola automotriz'),
  (60,  'TRUCK_H', '^(81|1[0-9A-F])$',  NULL, NULL, NULL, NULL, 'tractocamión y camión articulado'),
  (70,  'SPECIAL', '^(7[0-9A-G]|60)$',  NULL, NULL, NULL, NULL, 'vehículos especiales, obras y coche de inválido'),
  (80,  'OFFROAD', '^25$',              NULL, NULL, NULL, NULL, 'todo terreno declarado; NO recoge los SUV, que van como turismo'),
  (90,  'VAN',     '^(2[0124]|0G)$',    NULL, NULL, NULL, NULL, 'furgoneta, furgoneta mixta, camioneta, mixto adaptable'),
  (100, 'SPECIAL', '^(2[23])$',         NULL, NULL, NULL, NULL, 'ambulancia y coche fúnebre'),

  -- Trucks split by mass, since the code says nothing about size.
  (110, 'TRUCK_H', '^0[0-9A-F]$',      12000, NULL, NULL, NULL, 'camión de 12 t o más'),
  (120, 'TRUCK_L', '^0[0-9A-F]$',       NULL, 11999, NULL, NULL, 'camión de menos de 12 t'),
  (130, 'TRUCK_L', '^0[0-9A-F]$',       NULL, NULL, NULL, NULL, 'camión sin masa informada'),

  -- And the cars, which is the part that has to be invented. Wheelbase first,
  -- because it separates segments almost on its own; mass when there is none.
  (200, 'CAR_S',   '^40$',              NULL, NULL, NULL, 2499, 'batalla por debajo de 2.500 mm'),
  (210, 'CAR_M',   '^40$',              NULL, NULL, 2500, 2699, 'batalla de 2.500 a 2.699 mm'),
  (220, 'CAR_L',   '^40$',              NULL, NULL, 2700, NULL, 'batalla de 2.700 mm o más'),
  (230, 'CAR_S',   '^40$',              NULL, 1149, NULL, NULL, 'sin batalla: masa por debajo de 1.150 kg'),
  (240, 'CAR_M',   '^40$',              1150, 1549, NULL, NULL, 'sin batalla: masa de 1.150 a 1.549 kg'),
  (250, 'CAR_L',   '^40$',              1550, NULL, NULL, NULL, 'sin batalla: masa de 1.550 kg o más'),
  (260, 'CAR_M',   '^40$',              NULL, NULL, NULL, NULL, 'turismo sin batalla ni masa: al centro, y se sabrá por el conteo');

-- Applies the rules to every sheet, or only to the unclassified ones.
-- Returns how many it classified, because a silent UPDATE says nothing.
CREATE OR REPLACE FUNCTION spain.classify_size(only_missing boolean DEFAULT false)
RETURNS bigint AS $$
DECLARE
  touched bigint;
BEGIN
  UPDATE spain.vehicle_spec s
     SET size_class_code = coalesce(
           (SELECT r.size_class_code
              FROM spain.size_rule r
             WHERE (r.vehicle_type_pattern IS NULL
                    OR coalesce(s.vehicle_type_code, '') ~ r.vehicle_type_pattern)
               AND (r.min_mass_kg IS NULL
                    OR coalesce(s.running_mass_kg, s.kerb_weight_kg) >= r.min_mass_kg)
               AND (r.max_mass_kg IS NULL
                    OR coalesce(s.running_mass_kg, s.kerb_weight_kg) <= r.max_mass_kg)
               AND (r.min_wheelbase_mm IS NULL OR s.wheelbase_mm >= r.min_wheelbase_mm)
               AND (r.max_wheelbase_mm IS NULL OR s.wheelbase_mm <= r.max_wheelbase_mm)
             ORDER BY r.priority
             LIMIT 1),
           'OTHER')
   WHERE NOT only_missing OR s.size_class_code IS NULL;
  GET DIAGNOSTICS touched = ROW_COUNT;
  RETURN touched;
END $$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION spain.classify_size(boolean) TO archive_rw;

COMMENT ON FUNCTION spain.classify_size(boolean) IS
  'Assigns size_class_code to every technical sheet from the rules in size_rule. '
  'Run it after loading, and again whenever a threshold changes: it rewrites the '
  'dimension, never the twenty million events.';

COMMIT;

RESET ROLE;

\echo '--- las clases y cuántas reglas las alimentan'
SELECT c.code, c.description, count(r.rule_pk) AS reglas
  FROM spain.size_class c LEFT JOIN spain.size_rule r ON r.size_class_code = c.code
 GROUP BY 1, 2, c.sort_order ORDER BY c.sort_order;
