<!--
Documento abierto el 2026-09-01, a petición de Víctor: «Tal vez puedes hacer un documento de diseño de la base de datos y la ETL y le echamos un vistazo antes de implementarlo».
Existe para revisar el diseño ANTES de escribir el DDL y la carga, así que aquí no hay código instalable: los bloques SQL son el esbozo que se discute, no el fichero que se ejecuta. Cuando se apruebe, el DDL vive en schema/ y la carga en etl/, y este documento se queda como el porqué.
Las tres directrices de Víctor del 2026-09-01, que son el eje de todo lo que sigue: «meter sólo los campos en los que estamos interesados y con el tamaño mínimo imprescindible cuando tenga sentido» y «todos los valores largos que se repiten mucho deben ir a una tabla dimensional con un foreign key».
Lo que aquí se afirma sobre la fuente está medido y citado desde fuente.md y alcance.md; lo que es estimación nuestra va dicho como estimación en el cuerpo, porque la mitad de los números de tamaño no se pueden saber hasta la fase 0.
Las cardinalidades de vehicle_spec y de place son la única incógnita que puede cambiar la forma del esquema, y por eso la fase 0 está antes de la implementación y no después.
-->

# Diseño de la base de datos y de la ETL

Base **`matveh`**, esquema **`spain`**, en el servidor `45.159.223.206`. La base y el esquema ya están creados, con los roles y las credenciales del archivo de modelos; lo que se diseña aquí es **lo que va dentro**.

Estado: **implementado y en producción desde el 2026-09-02**. Lo que está corriendo, y cómo se opera, en [operacion.md](operacion.md); lo que se midió antes de construirlo, en [fase0-resultados.md](fase0-resultados.md). Este documento conserva el diseño y **el porqué de cada decisión**, que es lo que no se ve mirando el código.

> **La fase 0 se ejecutó el 2026-09-01 y desmintió una de las hipótesis de este documento.** Los resultados están en [fase0-resultados.md](fase0-resultados.md), y la corrección que exigen, en [La corrección tras la fase 0](#la-corrección-tras-la-fase-0). Lo que sigue conserva el diseño original porque el razonamiento sigue haciendo falta para entender la corrección; donde algo ha quedado desmentido, se dice en su sitio.

El alcance no se discute aquí: está cerrado en [alcance.md](alcance.md) y se da por bueno. Lo que se decide aquí es la forma que toman esos datos en PostgreSQL y cómo se cargan.

## Las tres directrices, y qué hace cada una

| Directriz | Dónde se aplica |
|---|---|
| **Sólo los campos que interesan** | 11 de los 69 campos no entran, y uno queda pendiente de medir. El detalle, campo a campo, [más abajo](#el-destino-de-los-69-campos). |
| **El tamaño mínimo imprescindible cuando tenga sentido** | Sólo en la tabla de hechos, que es la que tiene 20 millones de filas. En las dimensiones se usa el tipo cómodo, porque ahí el byte no se paga. |
| **Los valores largos que se repiten, a una dimensión con clave ajena** | Es la decisión estructural del diseño: **579 de los 714 bytes de cada registro son texto repetido** y se van a dos dimensiones, `vehicle_spec` y `place`. |

Ese «cuando tenga sentido» de la segunda directriz es lo que evita el error clásico de apretar todo: **una dimensión de cincuenta mil filas no necesita ahorrar nada**, así que ahí los campos van con su tipo natural y exacto, y se conservan incluso los de cobertura baja —los cinco del vehículo base, por ejemplo— porque guardarlos no cuesta. El ahorro se busca donde está el volumen, que es en las dos tablas de eventos.

## La forma: dos tablas de eventos y dimensiones compartidas

```
                    ┌─────────────────┐         ┌──────────────────┐
                    │  vehicle_spec   │         │      place       │
                    │  la ficha       │         │  municipio,      │
                    │  técnica        │         │  localidad, CP   │
                    └────────┬────────┘         └────────┬─────────┘
                             │                           │
              ┌──────────────┴───────────┬───────────────┴──────────────┐
              │                          │                              │
      ┌───────▼────────┐        ┌────────▼────────┐            ┌────────▼────────┐
      │  registration  │        │ deregistration  │            │  municipality   │
      │  altas         │        │  bajas          │            │  province       │
      │  ~20 M filas   │        │  ~20 M filas    │            │  catálogos      │
      └────────────────┘        └─────────────────┘            └─────────────────┘
```

**Dos tablas de eventos y no una.** El diseño de registro es el mismo para altas y bajas —714 bytes, 69 campos, comprobado campo a campo en [diseno-de-registro.md](diseno-de-registro.md)—, así que la tentación es una sola tabla con una columna que diga de qué fichero viene. No se hace, y el motivo es el mismo que ya está escrito en el archivo de modelos para `param_mle` y `param_bsr`: **una tabla común obliga a columnas que significan «aquí no aplica», y eso envenena cualquier consulta, porque quien lee tiene que saber de qué clase es la fila antes de interpretar un nulo**. En altas, `origin_code` e `is_used` dicen algo y `reason_code` no existe; en bajas es al revés. Y las consultas naturales son de un lado o del otro: entradas al parque y salidas del parque no se suman, se restan.

**Y las dimensiones son las mismas para las dos**, que es lo que hace que la separación no cueste nada: un vehículo que se matricula en 2016 y se da de baja en 2024 apunta a la misma fila de `vehicle_spec` desde los dos eventos, aunque no se pueda saber que es el mismo vehículo.

## Por qué la ficha técnica va a una dimensión, y qué se gana

La ficha técnica es **la mitad del ancho del registro** y no describe al vehículo individual: describe **su modelo**. `MARCA_ITV` son 30 caracteres, `FABRICANTE_ITV` 70, `VERSION_ITV` 35, y los cinco campos del vehículo base otros 175. Todos ellos se repiten idénticos en miles de registros.

Tres cosas se ganan, y la tercera es la que menos se ve y más vale:

**El tamaño.** Los 579 bytes de texto que absorben las dimensiones se convierten en **dos claves ajenas de 4 bytes** en cada fila de evento. Sobre 20 millones de altas eso es la diferencia entre unos 12 GB y algo del orden de 1,4 GB.

**La velocidad de los agregados.** Agrupar por marca, por tipo o por clase de tamaño se hace contra una tabla que cabe entera en memoria, y el hecho sólo aporta el conteo.

**Y que reclasificar cuesta un `UPDATE` de decenas de miles de filas, no de veinte millones.** Esto importa mucho aquí, porque lo que Víctor ha pedido producir no es la medida del neumático sino clases gruesas de tamaño —«coches pequeños, medianos, grandes, todo-terrenos, furgonetas, camiones pequeños»— y **esa clasificación no viene en el fichero: hay que construirla**, y el propio [alcance.md](alcance.md#la-segmentación-por-tamaño-sale-del-propio-registro) deja dicho que el SUV hay que derivarlo con un clasificador porque se matricula como turismo. O sea que la clase de tamaño **se va a cambiar de opinión varias veces**. Viviendo en `vehicle_spec` como una columna calculada, cada cambio de criterio es un `UPDATE` sobre la dimensión y todos los agregados históricos se recalculan solos.

### La clave de la dimensión: el hash de la ficha

`vehicle_spec` se identifica con un `spec_pk` sintético y una clave natural que es el **sha256 del contenido normalizado de sus 36 campos**. Es el mismo patrón que `model_blob` en el archivo de modelos: deduplicar por huella y dejar que el `ON CONFLICT DO NOTHING` haga el trabajo.

La razón para no usar como clave natural la contraseña de homologación, que sería lo elegante, es que **está en el 98,7 % de los registros pero no en todos** y no es única por ficha —la misma contraseña admite variantes y versiones distintas—. Con el hash de todo, ninguna fila se pierde y ninguna se funde con otra que no era igual. La normalización previa (recortar espacios, blanco a cadena vacía, sin tocar acentos) hay que fijarla y no cambiarla nunca, porque cambiarla cambia todos los hashes.

## La corrección tras la fase 0

Lo de arriba da por hecho que la ficha técnica se repite mucho. **Medido, no se repite lo bastante**: cada mes aporta unas 33.000 fichas nunca vistas y esa cifra no decae, así que en once años la dimensión tendría del orden de 4,6 millones de filas y crecería con los eventos en lugar de con los modelos. Y la razón de fondo es peor que un problema de tamaño: `MARCA_ITV` y `MODELO_ITV` son **texto libre y sucio** —el Tiguan aparece bajo once grafías distintas en un solo mes, una de ellas con la marca `VOLKSWAGEN BEETLE`—, así que la dimensión tal como estaba definida **no sirve para agrupar**, que era la mitad de su razón de ser. El detalle está en [los hallazgos 1 y 2 de la fase 0](fase0-resultados.md#1-la-ficha-técnica-no-es-una-dimensión-no-satura).

### Lo decidido el 2026-09-01, con los números delante

***NOTA VBR***: *1.) Conservamos y más adelante 2.) Intentaremos estandarizar los textos libres más adelante, por ahora no lo necesitaos, basta con tamaño y tipo 3.) ok*

Tres decisiones, y la segunda es la que simplifica el esquema:

| Decisión | Qué implica |
|---|---|
| **`vehicle_spec` se conserva** | La dimensión tendrá millones de filas y aun así merece la pena: cada ficha se usa 5,6 veces de media y evita repetir 579 bytes de texto en cada uno de los 20 millones de eventos. Variante, versión y contraseña de homologación se guardan. |
| **La normalización de marca y modelo se aplaza** | No se construyen ahora ni la tabla de marcas canónicas ni una dimensión de modelo: **se agrupa por tipo y por tamaño**, que no dependen del texto sucio. El texto crudo se guarda tal cual y la normalización se podrá hacer encima, cuando haga falta, sin recargar nada. |
| **Se capturan los diarios cada día** | Es la única vía para tener contraseña de homologación de aquí en adelante, ya que el histórico no la trae. |

**La consecuencia de la segunda hay que tenerla presente al usar los datos, y va en el `COMMENT` de las columnas**: mientras la normalización no exista, **un agregado por marca o por modelo no es publicable**, porque el 12 % de los Tiguan de un mes se escapa de su propia marca. Los agregados que sí valen desde el primer día son los de tipo de vehículo, clase de tamaño, geografía, propulsión y régimen de uso.

Así que el esquema se queda como estaba —`vehicle_spec` y `place`, dos dimensiones— y lo que cambia es lo que se espera de él: `vehicle_spec` no es un catálogo de modelos, es una tabla de deduplicación con millones de filas, y **lo que agrupa son sus dos columnas de clasificación**, `vehicle_type_code`, que viene del fichero, y `size_class_code`, que se deriva de las masas y la geometría.

Agrupar así obliga a un `JOIN` de la tabla de eventos contra una dimensión de millones de filas. Es un *hash join* de en torno a un segundo, así que no se denormaliza nada por ahora; si se demuestra lento con datos reales, la salida es llevar `vehicle_type_code` también al evento —tres bytes por fila— y no al revés.

### Lo que se descartó al decidir eso

La corrección que se estuvo considerando separaba las dos cosas que se habían metido en una sola tabla: **lo que agrupa** y **lo que deduplica**. Queda escrita porque el día que haga falta agrupar por marca, es por aquí por donde hay que volver.

```
   registration / deregistration
        │            │
        │            └── spec_pk ──> vehicle_spec   el detalle técnico completo,
        │                            millones de filas, se consulta poco
        └── model_pk ──> vehicle_model ── brand_pk ──> brand
                         lo que agrupa                 marca canónica,
                         decenas de miles             unas decenas de filas
```

**`brand`, marcas canónicas, con su tabla de grafías.** Unas sesenta marcas cubren casi todo el volumen; las 1.491 grafías de un mes se resuelven contra ellas con una tabla de alias, y lo que no case queda como marca desconocida y visible. **Es la única pieza que necesita trabajo humano**, y no se puede evitar: sin ella, un agregado por marca miente.

**`vehicle_model`, lo que agrupa**: marca canónica, modelo, tipo de vehículo, propulsión, categoría UE, carrocería, alimentación y categoría eléctrica. Decenas de miles de filas, y es contra ésta contra la que se agrupa en los agregados.

**`vehicle_spec`, lo que deduplica**: la ficha completa, con variante, versión, contraseña de homologación y todas las medidas. Millones de filas, pero sigue mereciendo la pena porque cada ficha se usa 5,6 veces de media y evita repetir 579 bytes de texto en cada evento.

Y el hecho llevaría **las dos claves ajenas**, 8 bytes en vez de 4: los agregados de negocio tocarían sólo la tabla pequeña, y el detalle técnico estaría ahí cuando se pide. **Aplazado**: hoy se agrupa por tipo y tamaño, que no necesitan nada de esto.

### La alternativa que se descartó: prescindir de la ficha

Se podía prescindir de `vehicle_spec` por completo: llevar al evento los dieciséis campos numéricos de la ficha —masas, cilindrada, kW, plazas, batalla, vías, CO2— como columnas, unos 30 bytes, y **tirar variante, versión y contraseña de homologación**.

| | Con `vehicle_spec` | Sin `vehicle_spec` |
|---|---|---|
| Tamaño total estimado | ~2,5 GB | ~2,1 GB |
| Variante y versión | se conservan | **se pierden** |
| Contraseña de homologación | se conserva | **se pierde** |
| Tablas que mantener | 3 | 2 |

**Descartada el 2026-09-01**: se conserva la ficha. Los 400 MB de diferencia no son nada frente a perder la única llave hacia un catálogo técnico, sobre todo ahora que los diarios se van a capturar cada día y esa llave va a existir de verdad para los datos nuevos.

## Las tablas

**El DDL vigente es [schema/01-spain-schema.sql](../schema/01-spain-schema.sql)**, que es lo que hay ejecutado; lo que sigue reproduce sus tablas para poder explicarlas, y se mantiene igual a él. Nombres en inglés, en singular, sin palabras clave de SQL, y las columnas ordenadas para que **el orden evite el relleno de alineación** de PostgreSQL: primero lo de 4 bytes, luego lo de 2, y al final lo de 1.

Dos cosas cambiaron al implementarlo, y conviene saber por qué:

**Los códigos son `text` y no `char(n)`.** Un `text` corto ocupa lo mismo o menos —un byte de cabecera más el contenido— y `char(n)` rellena con espacios: la provincia de Asturias, que es `O`, se guardaría como `'O '`, con las sutilezas de comparación que eso arrastra. Es el mismo motivo por el que el archivo de modelos usa `text` con un `CHECK` en lugar de `char(64)` para sus huellas.

**`procedure_code` admite nulo**, y no se supo hasta cargar: los dos registros de 707 caracteres de 2014-12 traen `CLAVE_TRAMITE` en blanco. Sus demás campos son buenos, así que se cargan, y las vistas de conteo los dejan fuera solas porque un nulo no casa con una lista `IN`.

```sql
-- ── LOS EVENTOS ─────────────────────────────────────────────────────────────
-- Una fila por trámite. Ni un texto: todo lo que era texto está en place o en
-- vehicle_spec. Particionada por el mes del FICHERO, no por la fecha del
-- trámite: la unidad de carga es el fichero mensual y recargar un mes tiene que
-- ser tirar su partición.
CREATE TABLE spain.registration (
  period                   date        NOT NULL,   -- primer día del mes del fichero
  procedure_date           date        NOT NULL,   -- FEC_TRAMITE: la fecha del evento
  registration_date        date,                   -- FEC_MATRICULA
  first_registration_date  date,                   -- FEC_PRIM_MATRICULACION
  process_date             date,                   -- FEC_PROCESO
  spec_pk                  integer     NOT NULL REFERENCES spain.vehicle_spec,
  place_pk                 integer              REFERENCES spain.place,
  service_code             text                 REFERENCES spain.service,
  plate_province_code      text                 REFERENCES spain.province,
  procedure_code           text                 REFERENCES spain.procedure_type,
  plate_class_code         text                 REFERENCES spain.plate_class,
  origin_code              text                 REFERENCES spain.origin,
  is_used                  boolean,
  is_renting               boolean,
  is_legal_person          boolean
) PARTITION BY RANGE (period);

CREATE TABLE spain.deregistration (
  period                   date        NOT NULL,
  procedure_date           date        NOT NULL,
  registration_date        date,
  first_registration_date  date,       -- con procedure_date da la EDAD A LA BAJA
  process_date             date,
  spec_pk                  integer     NOT NULL REFERENCES spain.vehicle_spec,
  place_pk                 integer              REFERENCES spain.place,
  service_code             text                 REFERENCES spain.service,
  plate_province_code      text                 REFERENCES spain.province,
  procedure_code           text                 REFERENCES spain.procedure_type,
  reason_code              text                 REFERENCES spain.deregistration_reason,
  last_transfer_date       date,       -- FEC_TRAMITACION: la última transferencia.
                                       -- Vacía en el 96% de las altas y con fecha
                                       -- propia en el 60% de las bajas, así que
                                       -- entra aquí y no allí
  transfer_count           smallint,   -- NUM_TRANSMISIONES: por cuántas manos pasó
  owner_count              smallint,   -- NUM_TITULARES. Los dos SOLO aquí: en un alta
                                       -- son constantes; en una baja son kilometraje
                                       -- acumulado, o sea ciclo de vida
  is_telematic             boolean,
  is_renting               boolean,
  is_legal_person          boolean
) PARTITION BY RANGE (period);

-- ── LA FICHA TÉCNICA ────────────────────────────────────────────────────────
-- Aquí el byte no se paga, así que los tipos son los cómodos y exactos, y se
-- conservan campos de cobertura baja porque no cuestan.
CREATE TABLE spain.vehicle_spec (
  spec_pk                integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  spec_hash              text NOT NULL UNIQUE CHECK (spec_hash ~ '^[0-9a-f]{64}$'),
  vehicle_type_code      char(2) REFERENCES spain.vehicle_type,
  propulsion_code        "char"  REFERENCES spain.propulsion,
  electric_category_code char(4) REFERENCES spain.electric_category,
  brand                  text,
  model                  text,
  manufacturer           text,
  itv_type               text,
  itv_variant            text,
  itv_version            text,
  type_approval          text,        -- CONTRASENA_HOMOLOGACION_ITV
  eu_category            char(4),
  body_code              char(4),
  rd2822_class           char(4),
  euro_level             text,
  fuel_feed_code         "char",
  displacement_cc        smallint,
  fiscal_power_cvf       numeric(5,2),
  power_kw               numeric(6,2),
  kerb_weight_kg         integer,
  max_weight_kg          integer,
  running_mass_kg        integer,
  max_technical_mass_kg  integer,
  seats                  smallint,
  max_seats              smallint,
  standing_places        smallint,
  co2_g_km               smallint,
  consumption_wh_km      smallint,
  electric_range_km      integer,
  wheelbase_mm           smallint,
  front_track_mm         smallint,
  rear_track_mm          smallint,
  base_brand             text,
  base_manufacturer      text,
  base_type              text,
  base_variant           text,
  base_version           text,
  -- DERIVADA, no de la fuente: la clase gruesa de tamaño que pide el encargo.
  -- Se recalcula con un UPDATE cuando cambie el criterio.
  size_class_code        text REFERENCES spain.size_class
);

-- ── LA GEOGRAFÍA ────────────────────────────────────────────────────────────
-- Dos niveles para no repetir el nombre del municipio en cada combinación.
CREATE TABLE spain.municipality (
  municipality_pk  integer  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  ine_code         char(5) NOT NULL UNIQUE,
  name             text    NOT NULL,
  province_code    char(2) REFERENCES spain.province
);

CREATE TABLE spain.place (
  place_pk         integer  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  place_hash       text     NOT NULL UNIQUE,
  municipality_pk  integer  REFERENCES spain.municipality,
  province_code    char(2)  REFERENCES spain.province,   -- COD_PROVINCIA_VEH
  postal_code      char(5),
  locality         text
);

-- ── EL CONTROL DE CARGAS ────────────────────────────────────────────────────
-- Sin esto no se sabe si un mes está en versión diaria o mensual, que es la
-- pregunta que hay que poder contestar todos los días.
CREATE TABLE spain.source_file (
  source_file_pk  bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  kind            text NOT NULL CHECK (kind IN ('registration', 'deregistration')),
  granularity     text NOT NULL CHECK (granularity IN ('daily', 'monthly')),
  period          date NOT NULL,          -- mes del periodo
  file_date       date,                   -- día, sólo en los diarios
  file_name       text NOT NULL,
  url             text NOT NULL,
  byte_size       bigint,
  sha256          text CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  http_last_modified  timestamptz,
  http_etag       text,
  line_count      bigint,
  row_count       bigint,
  loaded_time     timestamptz NOT NULL DEFAULT now(),
  is_superseded   boolean NOT NULL DEFAULT false
);
```

**Lo que NO lleva la tabla de eventos, y a propósito:** ninguna clave ajena a `source_file`. Serían 8 bytes por fila —160 MB— para saber algo que ya se sabe: la partición dice el periodo, y `source_file` dice qué fichero cargó ese periodo y cuál quedó superado.

## El destino de los 69 campos

Once campos no entran, uno queda a medir, y los 57 restantes se reparten entre los eventos y las dimensiones. Los campos de la DGT y sus longitudes salen de [record-layout.tsv](record-layout.tsv), que es la fuente del troceado.

| # | Campo de la DGT | Long. | Destino | Columna | Tipo | Nota |
|---:|---|---:|---|---|---|---|
| 1 | `FEC_MATRICULA` | 8 | `registration / deregistration` | `registration_date` | `date` | fecha de matriculación |
| 2 | `COD_CLASE_MAT` | 1 | `registration` | `plate_class_code` | `"char"` | FK plate_class |
| 3 | `FEC_TRAMITACION` | 8 | **medir** | — | — | en altas debería coincidir con la matriculación; si no aporta, fuera |
| 4 | `MARCA_ITV` | 30 | `vehicle_spec` | `brand` | `text` |  |
| 5 | `MODELO_ITV` | 22 | `vehicle_spec` | `model` | `text` |  |
| 6 | `COD_PROCEDENCIA_ITV` | 1 | `registration` | `origin_code` | `"char"` | FK origin; distingue importación |
| 7 | `BASTIDOR_ITV` | 21 | **fuera** | — | — | bastidor truncado: no identifica ni cruza |
| 8 | `COD_TIPO` | 2 | `vehicle_spec` | `vehicle_type_code` | `char(2)` | FK vehicle_type |
| 9 | `COD_PROPULSION_ITV` | 1 | `vehicle_spec` | `propulsion_code` | `"char"` | FK propulsion |
| 10 | `CILINDRADA_ITV` | 5 | `vehicle_spec` | `displacement_cc` | `smallint` |  |
| 11 | `POTENCIA_ITV` | 6 | `vehicle_spec` | `fiscal_power_cvf` | `numeric(5,2)` |  |
| 12 | `TARA` | 6 | `vehicle_spec` | `kerb_weight_kg` | `integer` | TARA |
| 13 | `PESO_MAX` | 6 | `vehicle_spec` | `max_weight_kg` | `integer` |  |
| 14 | `NUM_PLAZAS` | 3 | `vehicle_spec` | `seats` | `smallint` |  |
| 15 | `IND_PRECINTO` | 2 | **fuera** | — | — | no alimenta ningún agregado |
| 16 | `IND_EMBARGO` | 2 | **fuera** | — | — | no alimenta ningún agregado |
| 17 | `NUM_TRANSMISIONES` | 2 | `deregistration` | `transfer_count` | `smallint` | sólo en bajas: manos por las que pasó |
| 18 | `NUM_TITULARES` | 2 | `deregistration` | `owner_count` | `smallint` | sólo en bajas |
| 19 | `LOCALIDAD_VEHICULO` | 24 | `place` | `locality` | `text` |  |
| 20 | `COD_PROVINCIA_VEH` | 2 | `place` | `province_code` | `char(2)` | FK province; domicilio |
| 21 | `COD_PROVINCIA_MAT` | 2 | `registration / deregistration` | `plate_province_code` | `char(2)` | FK province; provincia del trámite |
| 22 | `CLAVE_TRAMITE` | 1 | `registration / deregistration` | `procedure_code` | `"char"` | FK procedure_type |
| 23 | `FEC_TRAMITE` | 8 | `registration / deregistration` | `procedure_date` | `date` | la fecha del evento |
| 24 | `CODIGO_POSTAL` | 5 | `place` | `postal_code` | `char(5)` | el grano más fino |
| 25 | `FEC_PRIM_MATRICULACION` | 8 | `registration / deregistration` | `first_registration_date` | `date` | edad del vehículo; en bajas, el ciclo de vida |
| 26 | `IND_NUEVO_USADO` | 1 | `registration` | `is_used` | `boolean` | dimensión, no filtro |
| 27 | `PERSONA_FISICA_JURIDICA` | 1 | `registration / deregistration` | `is_legal_person` | `boolean` | empresa o particular |
| 28 | `CODIGO_ITV` | 9 | **fuera** | — | — | cobertura 0,1% |
| 29 | `SERVICIO` | 3 | `registration / deregistration` | `service_code` | `char(3)` | FK service; régimen de uso |
| 30 | `COD_MUNICIPIO_INE_VEH` | 5 | `place -> municipality` | `ine_code` | `char(5)` |  |
| 31 | `MUNICIPIO` | 30 | `place -> municipality` | `name` | `text` |  |
| 32 | `KW_ITV` | 7 | `vehicle_spec` | `power_kw` | `numeric(6,2)` | centinela ******* a NULL |
| 33 | `NUM_PLAZAS_MAX` | 3 | `vehicle_spec` | `max_seats` | `smallint` |  |
| 34 | `CO2_ITV` | 5 | `vehicle_spec` | `co2_g_km` | `smallint` | medir si es función de la ficha |
| 35 | `RENTING` | 1 | `registration / deregistration` | `is_renting` | `boolean` | régimen de uso |
| 36 | `COD_TUTELA` | 1 | **fuera** | — | — | del titular |
| 37 | `COD_POSESION` | 1 | **fuera** | — | — | del titular |
| 38 | `IND_BAJA_DEF` | 1 | `deregistration` | `reason_code` | `"char"` | FK deregistration_reason |
| 39 | `IND_BAJA_TEMP` | 1 | **fuera** | — | — | redundante con procedure_code = 6 |
| 40 | `IND_SUSTRACCION` | 1 | **fuera** | — | — | no alimenta ningún agregado |
| 41 | `BAJA_TELEMATICA` | 11 | `deregistration` | `is_telematic` | `boolean` | canal del desguace |
| 42 | `TIPO_ITV` | 25 | `vehicle_spec` | `itv_type` | `text` | medir: 0% en el día muestreado |
| 43 | `VARIANTE_ITV` | 25 | `vehicle_spec` | `itv_variant` | `text` |  |
| 44 | `VERSION_ITV` | 35 | `vehicle_spec` | `itv_version` | `text` |  |
| 45 | `FABRICANTE_ITV` | 70 | `vehicle_spec` | `manufacturer` | `text` |  |
| 46 | `MASA_ORDEN_MARCHA_ITV` | 6 | `vehicle_spec` | `running_mass_kg` | `integer` |  |
| 47 | `MASA_MAXIMA_TECNICA_ADMISIBLE_ITV` | 6 | `vehicle_spec` | `max_technical_mass_kg` | `integer` |  |
| 48 | `CATEGORIA_HOMOLOGACION_EUROPEA_ITV` | 4 | `vehicle_spec` | `eu_category` | `char(4)` | M1, N1, L3e... |
| 49 | `CARROCERIA` | 4 | `vehicle_spec` | `body_code` | `char(4)` | AA-AF |
| 50 | `PLAZAS_PIE` | 3 | `vehicle_spec` | `standing_places` | `smallint` |  |
| 51 | `NIVEL_EMISIONES_EURO_ITV` | 8 | `vehicle_spec` | `euro_level` | `text` |  |
| 52 | `CONSUMO_WH_KM_ITV` | 4 | `vehicle_spec` | `consumption_wh_km` | `smallint` |  |
| 53 | `CLASIFICACION_REGLAMENTO_VEHICULOS_ITV` | 4 | `vehicle_spec` | `rd2822_class` | `char(4)` |  |
| 54 | `CATEGORIA_VEHICULO_ELECTRICO` | 4 | `vehicle_spec` | `electric_category_code` | `char(4)` | FK electric_category |
| 55 | `AUTONOMIA_VEHICULO_ELECTRICO` | 6 | `vehicle_spec` | `electric_range_km` | `integer` |  |
| 56 | `MARCA_VEHICULO_BASE` | 30 | `vehicle_spec` | `base_brand` | `text` | carrozados |
| 57 | `FABRICANTE_VEHICULO_BASE` | 50 | `vehicle_spec` | `base_manufacturer` | `text` | carrozados |
| 58 | `TIPO_VEHICULO_BASE` | 35 | `vehicle_spec` | `base_type` | `text` | carrozados |
| 59 | `VARIANTE_VEHICULO_BASE` | 25 | `vehicle_spec` | `base_variant` | `text` | carrozados |
| 60 | `VERSION_VEHICULO_BASE` | 35 | `vehicle_spec` | `base_version` | `text` | carrozados |
| 61 | `DISTANCIA_EJES_12_ITV` | 4 | `vehicle_spec` | `wheelbase_mm` | `smallint` | discriminante de tamaño |
| 62 | `VIA_ANTERIOR_ITV` | 4 | `vehicle_spec` | `front_track_mm` | `smallint` | geometría de rueda |
| 63 | `VIA_POSTERIOR_ITV` | 4 | `vehicle_spec` | `rear_track_mm` | `smallint` | geometría de rueda |
| 64 | `TIPO_ALIMENTACION_ITV` | 1 | `vehicle_spec` | `fuel_feed_code` | `"char"` | M/B/F |
| 65 | `CONTRASENA_HOMOLOGACION_ITV` | 25 | `vehicle_spec` | `type_approval` | `text` | clave de cruce con catálogos |
| 66 | `ECO_INNOVACION_ITV` | 1 | **fuera** | — | — | declarado sin uso por la DGT |
| 67 | `REDUCCION_ECO_ITV` | 4 | **fuera** | — | — | declarado sin uso por la DGT |
| 68 | `CODIGO_ECO_ITV` | 25 | **fuera** | — | — | declarado sin uso por la DGT |
| 69 | `FEC_PROCESO` | 8 | `registration / deregistration` | `process_date` | `date` | mide el retraso de consolidación |

Los once que se van, agrupados por motivo:

- **Del titular, que no interesa** (decisión de [alcance.md](alcance.md)): `COD_TUTELA` y `COD_POSESION`. Sí se conservan `RENTING`, `SERVICIO` y `PERSONA_FISICA_JURIDICA`, que **no son datos del titular sino del régimen de uso** y son la variable más explicativa del kilometraje, según [la tensión 2](alcance.md#2-el-titular-no-interesa-pero-el-régimen-de-uso-sí-debería).
- **Indicadores de estado que no alimentan ningún agregado**: `IND_PRECINTO`, `IND_EMBARGO`, `IND_SUSTRACCION`, e `IND_BAJA_TEMP`, que además es redundante con `CLAVE_TRAMITE = 6` (baja temporal).
- **Declarados sin uso por la DGT**, en blanco por definición: `ECO_INNOVACION_ITV`, `REDUCCION_ECO_ITV`, `CODIGO_ECO_ITV`.
- **Sin contenido utilizable**: `CODIGO_ITV`, con cobertura del 0,1 %, y `BASTIDOR_ITV`, que viene truncado y por tanto no identifica ni permite cruzar nada.

Y el que queda a medir es `FEC_TRAMITACION`: el documento de la DGT dice que es «la fecha de transferencia del vehículo contenida en los datos de transferencias», o sea un campo de otro fichero de la familia. Si en altas y bajas coincide con otra fecha que ya guardamos, o viene vacío, no entra.

**Nada de esto es irreversible.** Los ZIP originales se conservan, así que recuperar un campo descartado es añadir una columna y recargar, no volver a la DGT.

## Cuánto ocupa: lo estimado y lo que salió

| Tabla | Estimado al diseñar | **Medido el 2026-09-02, con el histórico cargado** |
|---|---|---|
| `registration` | ~20 M de filas, ~1,4 GB | 19.750.700 filas |
| `deregistration` | del orden de 20 M, ~1,5 GB | 22.837.685 filas |
| `vehicle_spec` | cardinalidad **por medir**, entre 15 y 250 MB | 6.464.912 filas y **4.006 MB** |
| `place` | ~60 mil filas, ~4 MB | 250.121 filas, 66 MB |
| `municipality` | — | 8.181 filas |

**Donde más se falló fue en la dimensión, y por el motivo que la fase 0 destapó**: se estimó como un catálogo de modelos y resultó no saturar, así que hoy `vehicle_spec` **ocupa más que todas las particiones de eventos juntas**. La partida gorda son los textos finos —variante, versión y fabricante—, y ahí está el margen si algún día aprieta el disco.

Lo que sí se cumplió es el orden de magnitud de los eventos y el argumento de fondo: la fila de evento son unos 72 bytes, de los que 24 son cabecera de PostgreSQL, así que apretar más los campos no cambiaría nada. Frente a los **13 GB de texto plano** de la fuente y a los 6-8 GB que estimaba [fuente.md](fuente.md#cuánto-pesa-medido-el-2026-08-31) para una tabla cruda.

## El particionado, y por qué por el mes del fichero

«El mensual sustituye a los diarios sin contemplaciones» ([alcance.md](alcance.md#qué-implica-el-mensual-sustituye-a-los-diarios-sin-contemplaciones)) fija la unidad de carga: **el mes**. Y la forma de que recargar un mes sea idempotente sin claves de deduplicación ni `ON CONFLICT` es que ese mes sea **una partición**, y recargar sea tirarla y volver a llenarla.

De ahí una decisión que conviene ver de frente: se particiona por `period` —el mes del **fichero**— y no por `procedure_date` —la fecha del **trámite**—. No son lo mismo: un mensual puede traer trámites de días de meses anteriores. Con `period` la recarga es un `DROP TABLE` de la partición; con `procedure_date` habría que borrar por criterio y podrían quedar filas huérfanas de una carga anterior.

El precio es que una consulta por fecha de trámite toca la partición del mes y alguna vecina. Es barato, y **cuánto solapamiento hay es una de las mediciones de la fase 0**: si resultara que es enorme, habría que replantearlo.

Las particiones se crean por año y mes desde 2014-12, y la carga de un periodo es:

```sql
BEGIN;
DROP TABLE IF EXISTS spain.registration_2026_07;   -- si había algo, se va entero
CREATE TABLE spain.registration_2026_07 PARTITION OF spain.registration
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
-- ... la carga ...
UPDATE spain.source_file SET is_superseded = true
 WHERE kind = 'registration' AND period = '2026-07-01' AND granularity = 'daily';
COMMIT;
```

## Los catálogos del Anexo I

Las nueve tablas de códigos —clase de matrícula, procedencia, servicio, propulsión, trámite, motivo de baja, categoría de vehículo eléctrico, tipo de vehículo y provincias— están transcritas en [tablas-de-codigos.md](tablas-de-codigos.md), y ese documento dice de sí mismo que **su destino es acabar siendo tablas de catálogo, cargadas desde ahí y no reescritas a mano en el DDL**.

Se respeta, con un paso intermedio: **un guion extrae del markdown un `.tsv` por catálogo**, esos TSV se versionan en `codes/`, y el DDL los carga con `\copy`. Parsear el markdown en cada carga sería frágil —una tabla nueva en el documento rompería la ETL—; extraerlos una vez y versionarlos deja el diff a la vista cuando la DGT cambie un código.

Dos cosas que los catálogos tienen que admitir, porque los datos reales las traen:

- **Códigos que llegan y no están en el Anexo I.** Los propios documentos avisan de que `CATEGORIA_HOMOLOGACION_EUROPEA_ITV`, `CARROCERIA`, `CLASIFICACION_REGLAMENTO_VEHICULOS_ITV` y `NIVEL_EMISIONES_EURO_ITV` **no tienen diccionario oficial**. Por eso esos cuatro se guardan como valor, no como clave ajena, y su lista se reconstruye de los datos.
- **Y los que sí tienen diccionario tampoco lo respetan.** Medido: llegan `B22` en `SERVICIO` (2.019 registros), `FCEV` en la categoría de vehículo eléctrico, `G` en propulsión, `-` en procedencia, `N` en el trámite. Así que **las claves ajenas no pueden apuntar a una lista cerrada**: la ETL da de alta el código desconocido con la descripción «no documentado en el Anexo I» y avisa. Ver [el hallazgo 5](fase0-resultados.md#5-llegan-códigos-que-no-están-en-el-anexo-i).
- **El blanco significa algo** en tres de ellos: en `COD_PROCEDENCIA` el blanco es «Fabricación Nacional» y en `COD_TIPO` es «SIN ESPECIFICAR». Se cargan con su fila explícita para que el `JOIN` no pierda registros.

## La ETL, en seis pasos

Cada paso es idempotente y deja constancia en `source_file`. La orquestación es un guion; el trabajo pesado lo hace PostgreSQL.

### 1. Descargar

Las URL son predecibles ([fuente.md](fuente.md#qué-hay-publicado)), con las dos trampas ya documentadas: el mes va **sin** cero a la izquierda en la ruta y **con** cero en el nombre del fichero, y el año y el mes son los del periodo, no los de publicación. Se guarda el ZIP tal cual, con su `sha256`, su `last-modified` y su `etag`, y **si el `sha256` coincide con el de la carga vigente, no se hace nada más**.

**Los diarios se capturan todos los días, y no sólo para adelantar el mes en curso.** Decidido el 2026-09-01, y el motivo es que la DGT sólo los publica unos veinte días y **son los únicos que traen la contraseña de homologación**: lo que no se descargue el día que toca, no se recupera. La descarga diaria es por tanto un archivo, no un adelanto; el mensual seguirá pisando en las tablas lo que el diario cargó, pero el ZIP diario se conserva.

Los ZIP **se guardan y no se borran**, en `/data/matveh/raw/`, fuera de git y con el mismo criterio que `/data/NEX`: son unos 3,6 GB entre las dos fuentes y son lo único que no se puede reconstruir si la DGT retira un fichero o cambia lo publicado. Recuperar un campo descartado es recargar desde ahí, sin volver a pedir nada.

### 2. Meter el fichero en crudo, y recodificarlo al entrar

**Todo lo almacenado queda en UTF-8**, que es la codificación de la base: `matveh` se creó con `ENCODING 'UTF8'` y `client_encoding` fijado a `UTF8` por base, así que nada de lo que se guarde ni de lo que se devuelva está en otra cosa. La fuente, en cambio, es ISO-8859-1 —medido: en `GIJÓN` la `Ó` ocupa un solo byte, `D3`—, así que **hay que recodificar, y se recodifica una sola vez, al entrar, y lo hace el servidor**:

```sql
TRUNCATE spain.staging_line;
COPY spain.staging_line (line) FROM STDIN
  WITH (FORMAT csv, DELIMITER E'\t', QUOTE E'\x01', ENCODING 'LATIN1');
```

Tres detalles que no son adorno:

> **Cambiado al implementarlo, el 2026-09-01.** La recodificación la hace ahora **el guion al leer el ZIP**, no el `COPY`. El motivo es que el guion pasa a `psql` el script y los datos por el mismo flujo, y pedirle que lea una mitad como UTF-8 y la otra como LATIN1 es frágil. Lo que no cambia es el resultado: **todo queda almacenado en UTF-8**, que es la codificación de la base. Lo de abajo se conserva porque explica el mecanismo del servidor, que sigue siendo válido si algún día la carga entra por otra vía.

- **`ENCODING 'LATIN1'` declara de qué codificación VIENE el fichero, no en cuál se guarda.** PostgreSQL lo lee como ISO-8859-1 y lo convierte a la codificación de la base, o sea a UTF-8, y esa opción manda sobre el `client_encoding` de la sesión sólo para ese `COPY`. Es la alternativa a recodificar en el cliente con un `iconv` o un `decode('latin-1')` en el guion, y se prefiere porque el guion no toca un byte y porque la conversión la hace el mismo componente que va a almacenar el resultado. Y como en la fuente cada carácter ocupa exactamente un byte, después de transcodificar **714 bytes son 714 caracteres**, y el troceado con `substr` cuenta caracteres sin ambigüedad.
- **Si la fuente resultara ser CP1252 y no ISO-8859-1**, las dos son idénticas salvo en los bytes `0x80`-`0x9F`, donde CP1252 pone el euro, las comillas tipográficas y la raya larga. Declarar `LATIN1` los convertiría en caracteres de control invisibles en vez de en esos símbolos. Por eso la fase 0 mide si esos bytes aparecen en el histórico: si no aparecen, las dos declaraciones son equivalentes y se queda `LATIN1`, que acepta cualquier byte; si aparecen, se declara `WIN1252` y hay que comprobar que no vengan además los cinco bytes que CP1252 deja sin definir, porque con esa declaración abortarían la carga.
- **`FORMAT csv` con un `QUOTE` que no puede aparecer** en el fichero, en lugar del formato `text`, para que una barra invertida en los datos se guarde como barra invertida y no como escape.
- **`FROM STDIN`**, no `FROM PROGRAM`: así la carga no necesita privilegios de superusuario ni que el fichero esté en el servidor, y se puede lanzar desde cualquier máquina con acceso.

El guion descomprime el ZIP en memoria y escribe las líneas a la entrada de `psql`. Un mensual son unos 107 MB de texto, así que la tabla de trabajo es pequeña y se vacía en cada fichero.

Aquí se aplican los controles de forma, y la fase 0 obligó a suavizar el más duro:

- **La cabecera se reconoce por su texto** —los 79 bytes que empiezan por `Vehículos matriculados.`— y se salta. Medido: **la llevan también los mensuales de matriculaciones**, uno por fichero, en contra de lo que dice el documento oficial; los de bajas no la llevan ni en diario ni en mensual.
- **Toda línea de datos mide 714 caracteres**, salvo un caso real que hay que admitir: en el mensual de 2014-12 hay dos registros de 707 en los que `FEC_PROCESO` viene como `?` en lugar de ocho dígitos. Son registros válidos, así que se cargan con la fecha de proceso nula y se cuentan aparte. **Abortar por eso dejaría fuera el primer mes del histórico.**
- Cualquier otra longitud sí aborta: ésa es la señal de que el diseño de registro cambió.

### 3. Trocear en SQL

El troceado sale de las posiciones de [record-layout.tsv](record-layout.tsv) y se escribe una vez, como una vista sobre la tabla de trabajo:

```sql
CREATE VIEW spain.staging_field AS
SELECT substr(line,   1,  8) AS fec_matricula,
       substr(line,   9,  1) AS cod_clase_mat,
       substr(line,  18, 30) AS marca_itv,
       ...
       substr(line, 707,  8) AS fec_proceso
  FROM spain.staging_line;
```

Con dos funciones auxiliares para lo que la DGT deja a medias, y las dos **inmutables**, para poder usarlas en índices y en columnas generadas:

- `spain.dgt_date(text)`: `DDMMYYYY` a `date`, devolviendo `NULL` cuando no son ocho dígitos o cuando el año cae fuera de un rango razonable. Un `to_date` a pelo se traga `32012020` sin protestar y produce una fecha inventada.
- `spain.dgt_number(text)`: recorta, y devuelve `NULL` para el blanco y para el centinela `*******` que `KW_ITV` documenta.

### 4. Resolver las dimensiones

Primero `place` y `vehicle_spec`, con el hash como clave de conflicto, y sin borrar nunca nada: son acumulativas, y una ficha técnica que dejó de matricularse en 2017 sigue haciendo falta para leer los eventos de 2016.

```sql
INSERT INTO spain.vehicle_spec (spec_hash, brand, model, ...)
SELECT DISTINCT ON (h) h, brand, model, ...
  FROM ( SELECT encode(sha256(convert_to(concat_ws(E'\x1f', marca_itv, modelo_itv, ...), 'UTF8')), 'hex') AS h,
                ... FROM spain.staging_field ) s
ON CONFLICT (spec_hash) DO NOTHING;
```

El separador de la concatenación es un carácter de control precisamente para que no pueda aparecer dentro de un campo: si se usara una coma, dos fichas distintas podrían dar el mismo hash.

### 5. Insertar los eventos

Un `INSERT ... SELECT` con dos `JOIN` por hash contra las dimensiones recién resueltas, dentro de la misma transacción que ha creado la partición. Si algo falla, no queda nada a medias.

### 6. Cerrar y medir

Contar filas, cuadrar contra las líneas del fichero, escribir la fila de `source_file`, marcar como superados los diarios del periodo, y **dejar registrada la comparación entre el mensual y la suma de sus diarios**, que es la medida que dice con cuánto retraso consolida la DGT y afecta a cualquier serie que se publique sobre el mes en curso.

### Con qué se implementa

**Python 3 de la biblioteca estándar para orquestar, `psql` para cargar.** Sin dependencias: `urllib` descarga, `zipfile` descomprime en memoria, `hashlib` calcula la huella y `subprocess` alimenta a `psql`, que ya resuelve la conexión con el entorno y el fichero de contraseñas. No hace falta `psycopg` —que además no está instalado en la máquina— porque **no se hace una sola consulta fila a fila**: todo son `COPY` e `INSERT ... SELECT`.

Funciona igual en Windows y en Linux, que es requisito, porque no sale al sistema operativo para nada: no hay `unzip`, ni `iconv`, ni tuberías de utilidades Unix.

## Cómo queda implementado

Escrito el 2026-09-01, después de la fase 0. Cinco ficheros y ninguna dependencia que instalar:

| Fichero | Qué hace |
|---|---|
| [schema/00-create-database.sql](../schema/00-create-database.sql) | La base, el esquema y los privilegios. Ya ejecutado. |
| [schema/01-spain-schema.sql](../schema/01-spain-schema.sql) | Las tablas, los catálogos, las funciones de conversión, las particiones y las vistas de conteo, con un `COMMENT` en cada sitio donde un dato puede engañar |
| [schema/02-size-rules.sql](../schema/02-size-rules.sql) | Las clases de tamaño y las reglas que las asignan, **aparte porque son lo que va a cambiar** |
| [etl/download.py](../etl/download.py) | La descarga, con el manifiesto de huellas y el modo `--recent` de la tarea diaria |
| [etl/load.py](../etl/load.py) | La carga: trocea, resuelve dimensiones e inserta, todo en una transacción por fichero |
| [schema/checks.sql](../schema/checks.sql) | Las cifras que hay que mirar después de cargar, y contra qué compararlas |
| [etl/run-load.sh](../etl/run-load.sh) | La carga completa, **como `archive_rw` y sin privilegios** |
| [etl/hourly.sh](../etl/hourly.sh) | El circuito de cada hora: preguntar, descargar, cargar, clasificar |
| [etl/bootstrap-db.sh](../etl/bootstrap-db.sh) y [bootstrap-user.sh](../etl/bootstrap-user.sh) | El montaje en una máquina nueva, separado en lo que necesita privilegio y lo que no |
| [schema/migrations/](../schema/migrations/) | Los cambios de esquema posteriores, que se ejecutan a mano y no rehaciendo el DDL |

Y **cómo se opera** —qué corre, dónde están las trazas, cómo recargar un mes— está en [operacion.md](operacion.md).

Tres decisiones de implementación que no estaban en el diseño y conviene saber:

**Recargar un diario no es tirar una partición**, porque la partición es mensual y contiene los demás días. Se resuelve borrando por fecha de proceso, y eso se puede hacer porque está medido: **`FEC_PROCESO` es exactamente la fecha del fichero diario** en los tres diarios comprobados, en los 30.636 registros, sin una excepción.

**Un cero en una medida física se guarda como nulo.** Los mensuales traen masa, batalla y vías a `0` en registros enteros, y eso no es un cero: es «no informado». Guardarlo como cero bajaría cualquier media sin decir una palabra. En los contadores —plazas, titulares, transmisiones— el cero sí es un cero y se guarda.

**La ETL no necesita privilegios, y eso no es comodidad.** Corre como `archive_rw` con su contraseña en el fichero de contraseñas de quien la lanza; sólo el DDL es del propietario. Las dos operaciones que sí exigen ser dueño —crear la partición de un mes y vaciarla— están encapsuladas en `spain.ensure_partition` y `spain.reset_partition`, ambas `SECURITY DEFINER`. El motivo: **un proceso que pide `sudo` no se puede poner en un cron**, y la carga tenía que acabar en el cron.

**Se pregunta cada hora en vez de adivinar el horario.** La DGT no publica ninguno, así que `download.py --check` hace `HEAD` primero —el `ETag` con cero bytes de cuerpo— y sólo descarga lo nuevo o lo que haya cambiado. Los GET condicionales no sirven: medido, ese servidor ignora `If-None-Match` y `If-Modified-Since` y devuelve el fichero entero. Además de barato, esto detecta **un fichero que la DGT reescriba**, que una descarga diaria no vería.

**Un código que no está en el Anexo I se da de alta al vuelo**, con la descripción «no documentado en el Anexo I» y marcado como no documentado, en vez de rechazar la fila. `spain.checks` los lista.

## Fase 0: lo que había que medir antes de fijar el DDL

**Hecha el 2026-09-01. Los resultados, en [fase0-resultados.md](fase0-resultados.md)**: nueve de las diez mediciones salieron, la décima no es posible hasta que la DGT publique el mensual de agosto. Lo que sigue es lo que se pedía medir y para qué.

Diez mediciones, sobre cuatro mensuales repartidos —**2014-12, 2018-06, 2022-06 y 2026-07**— más el par de diarios ya descargado. Es media tarde de trabajo y evita construir el esquema equivocado.

| # | Qué se mide | Qué decide |
|---:|---|---|
| 1 | **Que las líneas de 2014 y 2018 midan 714 caracteres** (ya recodificadas) y que el troceado dé valores coherentes | Si el diseño de registro de hoy no vale para el histórico, cambia todo. Es lo primero. |
| 2 | Cardinalidad de `vehicle_spec` y su porcentaje sobre los eventos | Si es alta —digamos más del 5 %—, la dimensión no ahorra lo previsto y hay que partirla en dos niveles: modelo, y lo que varía por vehículo al hecho |
| 3 | Cardinalidad de `place`, y si la localidad la multiplica | Si la localidad hace explotar la dimensión sin aportar, se queda fuera y sobreviven municipio y CP |
| 4 | Si `co2_g_km` y `running_mass_kg` varían dentro de la misma contraseña, variante y versión | Son los dos candidatos a no ser función de la ficha técnica |
| 5 | Cobertura de cada campo **por año** | Confirma lo que avisa [fuente.md](fuente.md#limitaciones-que-condicionan-cualquier-uso): los campos añadidos después no están rellenos hacia atrás |
| 6 | Solapamiento entre `period` y `procedure_date` | Si es grande, el particionado por mes de fichero se replantea |
| 7 | `FEC_TRAMITACION`: qué trae y si difiere de las fechas que ya guardamos | Entra o no entra |
| 8 | Mensual contra la suma de sus diarios | El retraso de consolidación, que afecta al mes en curso |
| 9 | Si aparecen bytes `0x80`-`0x9F` en el histórico | Si la fuente es ISO-8859-1 o CP1252, o sea qué se declara al recodificar a UTF-8 |
| 10 | Serie mensual de trámites `9` (temporal) contra `B` (paso a definitiva) durante los once años | Cuántas temporales no llegan nunca a definitiva, que es el error del convenio de conteo de altas |

## El convenio de conteo vive en las vistas, no en la carga

**Se carga todo.** Ninguna fila se descarta por su trámite, `procedure_code` es `NOT NULL` en las dos tablas de eventos, y qué cuenta como entrada o salida del parque se decide al consultar. Lo dijo Víctor el 2026-09-01:

***NOTA VBR***: *Estoy pensando que si los trámites dudodos son un % pequeño del total podemos dejar los registros y luego en las queries ya se verá si entran o no.*

Es lo acertado por dos motivos que se refuerzan: el volumen de los trámites dudosos es pequeño —las matriculaciones temporales son el 1,3 % del fichero del día medido— así que guardarlos no cuesta nada; y el convenio es de negocio y va a cambiar, mientras que recargar once años porque se cambió de criterio sí cuesta.

De modo que el convenio es **dos vistas**, `spain.park_entry` y `spain.park_exit`, y cambiarlo es un `CREATE OR REPLACE VIEW`. Éste es el que proponemos de partida:

**Entran al parque** cuatro trámites:

| Código | Qué es | Por qué entra |
|---|---|---|
| `1` | Matriculación ordinaria y de ciclomotores | es la matriculación normal: el 97,8 % del fichero |
| `5` | Rematriculación | vuelve a dar de alta un vehículo; sólo hubo **una** en el día medido |
| `8` | Matriculación vehículo especial | tractores, maquinaria y demás vehículos especiales |
| `9` | Matriculación temporal | matrícula provisional, con la que el vehículo ya rueda |

**Y no entra** el que parece que debería:

| Código | Qué es | Por qué NO entra |
|---|---|---|
| `B` | Paso de matrícula temporal a definitiva | es **el mismo vehículo** que ya contó al sacar la temporal (`9`), así que sumarlo lo cuenta dos veces |

Queda un flanco, y conviene saber de qué está hecho: **una matrícula temporal que caduca y nunca pasa a definitiva** cuenta como alta con este convenio. La matrícula temporal es un permiso de circulación con fecha de caducidad —prorrogable, y de ahí el trámite `A`— y existe en dos figuras: la de un particular o una empresa para un vehículo concreto, y la de empresa para pruebas, que **no pertenece a un vehículo sino al fabricante, concesionario, carrocero o taller**, y se monta sucesivamente en vehículos distintos.

Las situaciones en que esa temporal nunca llega a `B`, y no todas cuentan igual:

| Situación | ¿Acaba entrando en el parque? |
|---|---|
| **El vehículo se va de España**: se matricula temporalmente sólo para conducirlo hasta su país | **No, nunca.** Contarlo como alta es un alta que no existe |
| **Pruebas, demostraciones y prensa**, con placa de empresa | **No, nunca**, bajo esa matrícula |
| **Traslado hasta el carrocero o el punto de entrega**, cuando el vehículo se entrega en chasis | Normalmente sí, pero meses después — y no, si el carrozado se exporta |
| **El trámite definitivo se atasca**: falta ficha técnica, homologación individual, ITV o el impuesto de matriculación | Normalmente sí, con retraso o tras una prórroga |
| **El vehículo se devuelve o se rechaza** antes de completar la matriculación | No |

O sea que las dos primeras son error de verdad y las demás son un retraso que se cierra solo. (Esto es cómo funciona la figura, no una medición: lo que se mide es lo de abajo.)

El techo del error, en el único día medido, son las 133 matriculaciones temporales sobre 10.486 registros: el 1,3 %. Y el reparto real se puede medir con lo que vamos a cargar, sin fuente externa, contando `9` y `B` por mes a lo largo de los once años: si el circuito se cerrase siempre, los dos acumulados convergerían con un desfase de unas semanas, y lo que quede sin cerrar es la proporción que nunca llega a definitiva. Ese día hubo 133 temporales y 93 pasos a definitiva, y **los 93 eran todos vehículos usados**, lo que apunta a que el circuito vive sobre todo en la importación de usados — el mismo segmento del que avisa [alcance.md](alcance.md#1-los-usados-entran-son-importaciones-no-rematriculaciones).

**Salen del parque** los tres trámites de baja definitiva:

| Código | Qué es |
|---|---|
| `3` | Baja definitiva, excluidos Plan Renove, exportación y tránsito comunitario — el desguace de toda la vida |
| `4` | Baja definitiva por Plan Renove — los planes de achatarramiento subvencionado |
| `7` | Baja definitiva por exportación y por tránsito comunitario — el vehículo se va del país |

**Y no sale**:

| Código | Qué es | Por qué NO sale |
|---|---|---|
| `6` | Baja temporal | el vehículo **sigue existiendo**: se da de baja para no pagar seguro mientras está parado, y vuelve. Y es el **60 % de las bajas** del día medido, así que contarlo como salida vacía el parque de vehículos que ruedan |

El `4` no apareció en el día medido —sólo `3`, `6` y `7`—, pero en el histórico tiene que estar: los planes de achatarramiento de 2015 en adelante se registraron así, y son bajas definitivas de verdad.

**Y una advertencia que va en el `COMMENT` de las tablas**, porque aquí está el único sitio donde «ya se verá en la query» muerde: en altas los dudosos son el 1,3 %, pero **el 60 % de las bajas son temporales**, o sea vehículos que no salen del parque. Consultar `deregistration` sin filtrar no da de más un 1 %: da dos veces y media las salidas reales. Por eso las vistas se llaman `park_entry` y `park_exit` y son el camino recomendado; las tablas están debajo para quien quiera contar otra cosa a sabiendas.

## Lo que quedaba por decidir, y quedó decidido el 2026-09-01

Cuatro puntos, resueltos por Víctor el mismo día, con sus palabras:

| Punto | Decisión |
|---|---|
| Los once campos que se quedan fuera, y si `NUM_TITULARES` y `NUM_TRANSMISIONES` volvían | **Vuelven, y sólo en las bajas**, donde cuentan por cuántas manos pasó el vehículo antes de morir: *«ok a NUM_TITULARES y NUM_TRANSMISIONES»* |
| Dónde viven los ZIP descargados | `/data/matveh/raw/`, fuera de git y sin borrar: *«Los ZIP ok»* |
| Si entra la provincia del trámite, `COD_PROVINCIA_MAT` | **Entra**: *«COD_PROVINCIA_MAT se queda»* |
| La nomenclatura de tablas y columnas | **Aprobada** tal como está en este documento: *«nomenclatura: ok»* |

Y el convenio de conteo se resolvió antes, y de otra manera: no se decide en la carga, [se decide en las vistas](#el-convenio-de-conteo-vive-en-las-vistas-no-en-la-carga).

Con esto **no queda nada abierto salvo lo que depende de medir**: las diez mediciones de la fase 0, que son el paso siguiente.

## Lo descartado por el camino, con su motivo

**Una sola tabla de eventos con una columna de tipo.** Habría ahorrado duplicar la mitad de las columnas, y se descarta por el argumento de los nulos que significan «aquí no aplica».

**Normalizar marca, modelo y fabricante en catálogos propios**, con `vehicle_spec` apuntando a ellos. Es más puro y ahorraría unos megabytes en la dimensión. No se hace porque `vehicle_spec` tiene, como mucho, unos cientos de miles de filas: el ahorro es irrelevante y el coste son tres `JOIN` más en cada consulta.

**Guardar la ficha técnica como `jsonb` en el evento.** Flexible ante cambios del diseño de registro, y desastroso aquí: repite el documento en cada fila y no deja agrupar por marca sin abrir el JSON.

**Usar la contraseña de homologación como clave natural de la ficha.** Sería lo elegante, pero falta en el 1,3 % de los registros y no es única por ficha técnica.

**Un identificador de vehículo derivado del bastidor truncado más la ficha y la fecha.** Permitiría intentar casar altas con bajas, que es lo que haría posible el ciclo de vida vehículo a vehículo. Se descarta porque Víctor ya lo dio por imposible —«aunque no se puedan casar»— y porque un emparejamiento aproximado que falle un 5 % de las veces produce curvas de supervivencia con un sesgo que nadie sabría acotar. Los agregados se construyen sobre distribuciones.

**Índices por si acaso.** Sólo se crea un BRIN sobre `procedure_date` en cada tabla de eventos —barato, y encaja porque los datos entran en orden temporal—. Los demás se añadirán cuando existan las consultas que los necesiten, no antes.
