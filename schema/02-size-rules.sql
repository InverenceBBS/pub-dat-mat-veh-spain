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
-- The car thresholds were recalibrated on 2026-09-01 against the quantiles of
-- 118.957 real cars, after the first attempt left 69% of them in one class. They
-- are ABSOLUTE and stay absolute, so that the fleet getting heavier over the
-- years shows up in the counts.
--
-- WHAT IS STILL WRONG WITH IT, said plainly: this separates cars by size, not
-- SUVs from saloons. A long-wheelbase estate and an SUV land in the same class.
-- Telling them apart needs ground clearance or body height, which the record
-- does not carry -- see doc/alcance.md.
-- ============================================================================

SET ROLE model_archive;

BEGIN;

-- The sheets already classified point at these classes, so they have to be
-- unassigned before the catalogue can be rebuilt. It is an UPDATE over the
-- DIMENSION, never over the events, and classify_size() at the end of this file
-- puts every one of them back with the new thresholds.
UPDATE spain.vehicle_spec SET size_class_code = NULL WHERE size_class_code IS NOT NULL;

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

  -- And the cars, the part that has to be invented. MASS FIRST: measured over
  -- the 118.957 cars of 2026-07, wheelbase runs from p10 = 2.551 to p90 = 2.840
  -- mm, so a cut at 2.500 left ninety per cent of the fleet on one side. Mass
  -- spreads properly: p10 = 1.198, p50 = 1.502, p90 = 1.991 kg. Wheelbase stays
  -- as the fallback for the records that bring no mass.
  --
  -- THE THRESHOLDS ARE ABSOLUTE ON PURPOSE, and they will drag the counts over
  -- the years: between 2014-12 and 2026-07 the median car went from 1.365 to
  -- 1.502 kg, so the small class empties out as time passes. That drift is not a
  -- defect of the classification, IT IS THE MEASUREMENT:
  --
  --   "Si los coches son más pequeños se necesiatrán menos neuméticos pequeños,
  --    eso es lo que queremos medir precisamente"  -- Víctor, 2026-09-01
  --
  -- Cuts relative to each year would hide exactly that, because every year would
  -- then have the same share of small cars by construction.
  (200, 'CAR_S',   '^40$',               NULL, 1199, NULL, NULL, 'masa por debajo de 1.200 kg'),
  (210, 'CAR_M',   '^40$',               1200, 1749, NULL, NULL, 'masa de 1.200 a 1.749 kg'),
  (220, 'CAR_L',   '^40$',               1750, NULL, NULL, NULL, 'masa de 1.750 kg o más'),
  (230, 'CAR_S',   '^40$',               NULL, NULL, NULL, 2549, 'sin masa: batalla por debajo de 2.550 mm'),
  (240, 'CAR_M',   '^40$',               NULL, NULL, 2550, 2749, 'sin masa: batalla de 2.550 a 2.749 mm'),
  (250, 'CAR_L',   '^40$',               NULL, NULL, 2750, NULL, 'sin masa: batalla de 2.750 mm o más'),
  (260, 'CAR_M',   '^40$',               NULL, NULL, NULL, NULL, 'turismo sin masa ni batalla: al centro, y se sabrá por el conteo');

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

-- Reclassify right here: this file has just emptied size_class_code, so leaving
-- without doing it would leave the dimension unclassified and every aggregate by
-- size empty, with nothing saying why.
\echo '--- reclasificando con los umbrales nuevos'
SELECT spain.classify_size() AS fichas_clasificadas;

COMMIT;

RESET ROLE;

\echo '--- las clases, sus reglas y cuántas fichas han caído en cada una'
SELECT c.code, c.description,
       (SELECT count(*) FROM spain.size_rule r WHERE r.size_class_code = c.code) AS reglas,
       (SELECT count(*) FROM spain.vehicle_spec s WHERE s.size_class_code = c.code) AS fichas
  FROM spain.size_class c ORDER BY c.sort_order;
