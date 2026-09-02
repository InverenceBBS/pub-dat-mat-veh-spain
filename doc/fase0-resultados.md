<!--
Documento abierto el 2026-09-01, al ejecutar la fase 0 que diseno-de-base-de-datos-y-etl.md dejaba como paso previo obligatorio.
Todo lo que hay aquí está MEDIDO sobre los ficheros de la DGT descargados ese día, cuyas huellas están en /data/matveh/raw/manifest.tsv. Los guiones que producen cada tabla se citan al lado, así que cualquier cifra se puede regenerar.
El orden es deliberado: primero los cinco hallazgos que cambian el diseño, porque son lo que hay que decidir, y detrás las diez mediciones completas como respaldo. Quien venga a comprobar una cifra la busca abajo; quien venga a decidir, lee arriba.
La medición 8 no se pudo hacer y se dice por qué en su sitio, en vez de dejarla en silencio.
-->

# Fase 0: resultados

Las diez mediciones que [el documento de diseño](diseno-de-base-de-datos-y-etl.md#fase-0-lo-que-había-que-medir-antes-de-fijar-el-ddl) exigía antes de fijar el DDL, hechas el **2026-09-01** sobre ficheros reales. Nueve se hicieron; la décima —el mensual contra la suma de sus diarios— **seguía sin poder hacerse el 2026-09-02**, porque depende de que la DGT publique el mensual de agosto, y se explica por qué en su sitio.

**Ninguna toca la base de datos**: todo esto es contar sobre texto, con los guiones de [phase0/](../phase0/), que no necesitan credenciales ni PostgreSQL.

## Sobre qué se ha medido

Descargado con [etl/download.py](../etl/download.py) a `/data/matveh/raw/`, con su `sha256`, su `last-modified` y su `etag` en `manifest.tsv`:

| Ficheros | Registros |
|---|---:|
| Mensuales de matriculaciones 2014-12, 2018-06, 2022-06 y 2026-04 a 2026-07 | 1.222.419 |
| Mensuales de bajas 2014-12 y 2026-07 | 393.440 |
| **Diarios** de matriculaciones y de bajas de todo agosto de 2026 (22 días publicados) | 126.404 altas |

Los diarios de agosto se han guardado **aunque no se necesitaban hoy**: la DGT sólo publica unos veinte días de diarios, y sin ellos la medición 8 no se podrá hacer nunca. Ver [por qué falta la 8](#8-el-mensual-contra-la-suma-de-sus-diarios-no-medible-hoy).

## Los cinco hallazgos que cambian el diseño

### 1. La ficha técnica no es una dimensión: no satura

Es el hallazgo importante, y desmiente la hipótesis sobre la que estaba montado el esquema. La cardinalidad de la ficha técnica completa no es que sea alta —un 18 % de los eventos—: es que **cada mes nuevo aporta unas 33.000 fichas que no se habían visto nunca, y esa cifra no decae**:

| Mes | Registros | Fichas nuevas | Fichas acumuladas |
|---|---:|---:|---:|
| 2026-04 | 180.135 | 39.665 | 39.665 |
| 2026-05 | 189.626 | 32.732 | 72.397 |
| 2026-06 | 217.004 | 33.283 | 105.680 |
| 2026-07 | 189.104 | 32.979 | 138.659 |

Extrapolado a los 139 meses publicados, la dimensión tendría del orden de **4,6 millones de filas**, o sea que crecería con los eventos en vez de con los modelos de vehículo. Una tabla así deduplica —cada ficha se usa 5,6 veces de media— pero no es lo que se quería: no cabe en memoria para agrupar y no es «el catálogo de modelos».

Y quitar campos no arregla nada, que es lo que descarta la solución fácil. Medido con [phase0/spec_cardinality.py](../phase0/spec_cardinality.py) sobre el mensual de julio de 2026:

| Definición de la ficha | Filas distintas | % de los eventos |
|---|---:|---:|
| los 36 campos propuestos | 44.544 | 23,6 % |
| sin masa en orden de marcha ni CO2 | 41.007 | 21,7 % |
| sólo identidad textual y códigos, 15 campos | 36.299 | 19,2 % |
| marca + modelo + tipo + propulsión | 14.730 | 7,8 % |

De 36 campos a 15 sólo se baja del 23,6 % al 19,2 %. **La variabilidad está en la propia identidad textual**, no en las medidas: `VARIANTE_ITV` y `VERSION_ITV` traen códigos de configuración por unidad —`ACDXDBX0`, `FD7FD7GC008MN4VNA2KM`— que no describen un modelo.

### 2. Y marca y modelo son texto sucio, así que tampoco agrupan

Ésta es la razón de fondo por la que ni la versión gruesa satura. En **un solo mes** (julio de 2026, 189.104 registros):

- **1.491 marcas distintas**, de las cuales **494 aparecen una sola vez**.
- **10.152 modelos distintos** y 11.904 parejas marca-modelo.

El ejemplo que lo dice todo, todas las grafías de un mismo coche en ese mes:

| `MARCA_ITV` | `MODELO_ITV` | Registros |
|---|---|---:|
| `VOLKSWAGEN` | `TIGUAN` | 1.818 |
| `VOLKSWAGEN, VW` | `TIGUAN` | 73 |
| `VOLKSWAGEN VW` | `TIGUAN` | 25 |
| `VOLKSWAGEN V W` | `TIGUAN` | 18 |
| `VOLKSWAGEN AG` | `TIGUAN` | 4 |
| `VOLKSWAGEN` | `VOLKSWAGEN TIGUAN` | 3 |
| `VOLKSWAGEN BEETLE` | `TIGUAN` | 2 |
| `VOLKSWAGEN` | `TIGUAN 2.0 TDI` | 2 |
| `VOLKSWAGEN` | `TIGUAN 2.0 D4MRL` | 1 |
| `VOLKSWAGEN` | `TIGUAN 2.0 TDI 4MOTION` | 1 |
| `VOLKSWAGEN` | `TIGUAN SE NA V TDI BMT` | 1 |

Once formas del mismo vehículo, una de ellas con la marca de otro modelo dentro. **Cualquier agregado «por marca» hecho sobre el texto crudo está mal**, y no por un poco: el 12 % de los Tiguan de ese mes se escapa del recuento si se agrupa por `MARCA_ITV = 'VOLKSWAGEN'`.

Lo que **no** afecta: la segmentación por tamaño que pide el encargo no depende de este texto. Depende de `COD_TIPO`, las masas, la batalla y las vías, y ésos tienen cobertura del 100 % y son numéricos. O sea que el objetivo se sostiene; lo que se cae es contar por marca sin limpiar antes.

### 3. El mensual no trae la contraseña de homologación. El diario sí

Comparados los 22 diarios de agosto de 2026 (126.404 registros) con el mensual de julio (189.104), **campo a campo, la única diferencia que pasa de 20 puntos es una**:

| Campo | Diarios ago-2026 | Mensual jul-2026 |
|---|---:|---:|
| `CONTRASENA_HOMOLOGACION_ITV` | **97,7 %** | **0,0 %** |

Y no es cosa de julio: en los mensuales de 2018-06, 2022-06, 2026-04, 05, 06 y 07 la cobertura es 0,0 %; sólo el de 2014-12 trae algo, un 11,9 %.

Importa porque [alcance.md](alcance.md#la-clave-de-cruce-es-la-contraseña-de-homologación-no-el-tvv) identificó ese campo como **la clave de cruce** con cualquier catálogo técnico —la vía para llegar algún día a la medida del neumático—, y la midió al 98,7 % sobre un fichero **diario**. La conclusión que hay que tragar: **el histórico, que se construye con mensuales, no la lleva**. Sólo se puede acumular de aquí en adelante, capturándola de los diarios día a día.

### 4. Dos registros de 707 caracteres, y no son basura

En el mensual de 2014-12 hay dos líneas que no miden 714. Son registros válidos —un LIFAN SD y un RENAULT MASTER, con todos sus campos coherentes— en los que **`FEC_PROCESO` viene como `?` en lugar de ocho dígitos**, y por eso la línea se queda siete caracteres corta.

El diseño decía que la carga **aborta** si aparece una línea de otra longitud. Con esa regla, el primer mes del histórico no se carga. Hay que cambiarla: reconocer el caso, cargar el registro con `process_date` nulo, y contar cuántos han sido.

### 5. Llegan códigos que no están en el Anexo I

Medido con [phase0/extract_codes.py](../phase0/extract_codes.py), que además extrae los catálogos del [documento de códigos](tablas-de-codigos.md) a [codes/](../codes/) — diez ficheros TSV, 261 códigos:

| Campo | Códigos que no están en el Anexo I | Registros |
|---|---|---:|
| `SERVICIO` | `B22` | 2.019 |
| `COD_PROCEDENCIA_ITV` | `-` | 266 |
| `CATEGORIA_VEHICULO_ELECTRICO` | `FCEV` | 8 |
| `COD_PROPULSION_ITV` | `G` | 5 |
| `COD_TIPO` | `s3` | 3 |
| `CLAVE_TRAMITE` | `N` | 2 |
| `COD_PROVINCIA_MAT` | `AI` | 1 |

`FCEV` es reconocible —vehículo de pila de combustible, hidrógeno— y es una categoría que la DGT usa sin haberla documentado. `B22` son 2.019 registros, así que tampoco es una errata. `s3` en minúscula y `AI` como provincia sí lo parecen.

Consecuencia directa: **las claves ajenas a los catálogos no pueden apuntar a una lista cerrada**, o la carga falla por dos registros de once años. La ETL tiene que dar de alta el código desconocido con la descripción «no documentado en el Anexo I» y avisar, de modo que la novedad se vea en lugar de romper.

Y el blanco significa algo y hay que cargarlo como fila: `IND_BAJA_DEF` viene en blanco en 1.405.401 registros —son las bajas temporales, que no tienen motivo— y `CATEGORIA_VEHICULO_ELECTRICO` en 1.220.444, que son los vehículos que no son eléctricos.

## Lo que salió bien, y por tanto no hay que tocar

**El ancho de registro de hoy vale para todo el histórico.** Es la medición que podía cambiarlo todo, y sale limpia: los mensuales de 2014-12, 2018-06, 2022-06 y 2026-07 tienen **todas** sus líneas de 714 caracteres, salvo las dos del hallazgo 4. El troceado de [record-layout.tsv](record-layout.tsv) da valores coherentes en los cuatro.

**El particionado por el mes del fichero es sano.** Entre el 97,5 % y el 100 % de los trámites de un mensual caen en el mes del propio fichero. Lo que se sale son 3.811 registros de 151.128 en el peor caso, las bajas de julio de 2026, con trámites de meses anteriores.

**La codificación se puede declarar `LATIN1` sin más.** En 1.615.859 registros hay **siete** bytes del rango donde ISO-8859-1 y CP1252 difieren: seis `0x87` y un `0x91`, todos en los ficheros de bajas. Con `LATIN1` entran como caracteres de control invisibles en lugar de abortar; conviene limpiarlos al normalizar para no meter controles en la base.

**`place` sí es una dimensión de verdad**: entre 8.853 y 16.855 combinaciones distintas por mes sobre cientos de miles de eventos, y los municipios y códigos postales son un conjunto finito, así que satura de verdad. La localidad multiplica la dimensión por 1,3-1,8, y se queda.

**`FEC_TRAMITACION` fuera de las altas y dentro de las bajas.** En matriculaciones viene vacía en el 96-97 % de los registros: se confirma que no aporta. Pero en bajas trae una fecha distinta de las demás en el 60-64 % de los casos —la de la última transferencia—, y eso sí es ciclo de vida: cuánto tiempo llevaba el vehículo con su último dueño. Propongo que entre en `deregistration` como `last_transfer_date`, con el mismo criterio que `owner_count` y `transfer_count`.

**Y el reparto de trámites tiene dos ausencias que conviene saber.** Ni el `4` —baja definitiva por Plan Renove— ni el `8` —matriculación de vehículo especial— aparecen **ni una vez** en los nueve mensuales medidos, ni en 2014-12 con los planes de achatarramiento en marcha. Los vehículos especiales se matriculan con el trámite `1` y su clase de matrícula propia. Las vistas de conteo los dejan igualmente contemplados, que no cuesta nada, pero no hay que esperar que aporten. Y el reparto de las bajas es menos extremo de lo que sugería el único día medido antes: las temporales son el **43,7 %** en 2014-12 y el **50,5 %** en 2026-07, no el 60 %.

## Y una corrección a lo que estaba escrito

**Los mensuales sí llevan la línea de cabecera.** [fuente.md](fuente.md#el-fichero) dice, citando la página 3 del documento oficial, que la cabecera de 79 bytes la lleva el diario y «el mensual no la lleva». Medido: **los cuatro mensuales de matriculaciones la llevan**, uno cada uno. Los de bajas no la llevan, ni en diario ni en mensual, y eso sí coincide.

No cambia el diseño —la carga la reconoce por su texto y la salta— pero sí cambia un dato documentado, y el documento oficial se equivoca en ese punto.

## Las diez mediciones, con sus tablas

Producidas por [phase0/measure.py](../phase0/measure.py) sobre los nueve mensuales de la muestra. Las columnas dicen la familia y el periodo del fichero.

### 1. Ancho de línea y cabecera

| Fichero | Registros | Longitudes de linea | Cabeceras | Lineas raras |
|---|---:|---|---:|---|
| export_mensual_mat_201412.zip | 99888 | 79 x1, 707 x2, 714 x99888 | 1 | 171220146        LIFAN                         SD           ; 021220140        RENAULT                       MASTER        |
| export_mensual_mat_201806.zip | 203687 | 79 x1, 714 x203687 | 1 | - |
| export_mensual_mat_202206.zip | 143875 | 79 x1, 714 x143875 | 1 | - |
| export_mensual_mat_202604.zip | 180135 | 79 x1, 714 x180135 | 1 | - |
| export_mensual_mat_202605.zip | 189626 | 79 x1, 714 x189626 | 1 | - |
| export_mensual_mat_202606.zip | 217004 | 79 x1, 714 x217004 | 1 | - |
| export_mensual_mat_202607.zip | 189104 | 79 x1, 714 x189104 | 1 | - |
| export_mensual_bajas_201412.zip | 242312 | 714 x242312 | 0 | - |
| export_mensual_bajas_202607.zip | 151128 | 714 x151128 | 0 | - |

### 2 y 3. Cardinalidad de las dimensiones

| Fichero | Eventos | vehicle_spec | % | place | % | place sin localidad |
|---|---:|---:|---:|---:|---:|---:|
| export_mensual_mat_201412.zip | 99888 | 33772 | 33.8% | 8853 | 8.86% | 6993 |
| export_mensual_mat_201806.zip | 203687 | 30082 | 14.8% | 11864 | 5.82% | 8187 |
| export_mensual_mat_202206.zip | 143875 | 30339 | 21.1% | 10425 | 7.25% | 7372 |
| export_mensual_mat_202604.zip | 180135 | 39665 | 22.0% | 11212 | 6.22% | 7702 |
| export_mensual_mat_202605.zip | 189626 | 40892 | 21.6% | 11437 | 6.03% | 7843 |
| export_mensual_mat_202606.zip | 217004 | 43806 | 20.2% | 12057 | 5.56% | 8175 |
| export_mensual_mat_202607.zip | 189104 | 44544 | 23.6% | 11900 | 6.29% | 8099 |
| export_mensual_bajas_201412.zip | 242312 | 111484 | 46.0% | 21069 | 8.69% | 11700 |
| export_mensual_bajas_202607.zip | 151128 | 83992 | 55.6% | 16855 | 11.15% | 9170 |

### 4. ¿Varían el CO2 y la masa dentro de la misma contraseña, variante y versión?

| Fichero | Grupos | CO2 varia | Masa varia |
|---|---:|---:|---:|
| export_mensual_mat_201412.zip | 12641 | 537 (4.2%) | 1417 (11.2%) |
| export_mensual_mat_201806.zip | 17191 | 644 (3.7%) | 1611 (9.4%) |
| export_mensual_mat_202206.zip | 17598 | 2305 (13.1%) | 1435 (8.2%) |
| export_mensual_mat_202604.zip | 22427 | 2760 (12.3%) | 1830 (8.2%) |
| export_mensual_mat_202605.zip | 22938 | 2855 (12.4%) | 1893 (8.3%) |
| export_mensual_mat_202606.zip | 24279 | 2968 (12.2%) | 2072 (8.5%) |
| export_mensual_mat_202607.zip | 25049 | 2962 (11.8%) | 2029 (8.1%) |
| export_mensual_bajas_201412.zip | 14408 | 883 (6.1%) | 2137 (14.8%) |
| export_mensual_bajas_202607.zip | 29799 | 2821 (9.5%) | 3289 (11.0%) |

### 5. Cobertura por campo y por fichero (% no blanco)

| # | Campo | mat 201412 | mat 201806 | mat 202206 | mat 202604 | mat 202605 | mat 202606 | mat 202607 | bajas 201412 | bajas 202607 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | FEC_MATRICULA | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 2 | COD_CLASE_MAT | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 3 | FEC_TRAMITACION | 3.7 | 3.5 | 3.8 | 3.8 | 3.8 | 3.7 | 4.4 | 77.5 | 79.9 |
| 4 | MARCA_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 5 | MODELO_ITV | 100.0 | 99.6 | 99.4 | 99.4 | 99.3 | 99.3 | 99.3 | 100.0 | 100.0 |
| 6 | COD_PROCEDENCIA_ITV | 100.0 | 99.4 | 99.2 | 90.0 | 90.3 | 90.3 | 90.5 | 100.0 | 98.9 |
| 7 | BASTIDOR_ITV | 100.0 | 99.6 | 99.4 | 99.4 | 99.3 | 99.3 | 99.3 | 100.0 | 100.0 |
| 8 | COD_TIPO | 100.0 | 99.0 | 98.9 | 98.7 | 98.7 | 98.7 | 98.5 | 100.0 | 100.0 |
| 9 | COD_PROPULSION_ITV | 99.0 | 97.1 | 96.9 | 96.8 | 96.8 | 96.7 | 96.2 | 98.9 | 99.1 |
| 10 | CILINDRADA_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 11 | POTENCIA_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 12 | TARA | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 13 | PESO_MAX | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 14 | NUM_PLAZAS | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 15 | IND_PRECINTO | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 16 | IND_EMBARGO | 0.2 | 0.0 | 0.0 | 0.1 | 0.1 | 0.1 | 0.1 | 3.1 | 2.5 |
| 17 | NUM_TRANSMISIONES | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 18 | NUM_TITULARES | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 19 | LOCALIDAD_VEHICULO | 17.5 | 98.3 | 97.8 | 98.2 | 98.2 | 98.2 | 98.0 | 10.4 | 26.0 |
| 20 | COD_PROVINCIA_VEH | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 21 | COD_PROVINCIA_MAT | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 22 | CLAVE_TRAMITE | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 23 | FEC_TRAMITE | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 24 | CODIGO_POSTAL | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 25 | FEC_PRIM_MATRICULACION | 4.3 | 5.3 | 9.7 | 11.7 | 11.4 | 10.4 | 13.0 | 3.8 | 6.1 |
| 26 | IND_NUEVO_USADO | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 27 | PERSONA_FISICA_JURIDICA | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 28 | CODIGO_ITV | 65.6 | 44.2 | 28.1 | 0.1 | 0.2 | 0.2 | 0.1 | 30.2 | 39.8 |
| 29 | SERVICIO | 100.0 | 99.7 | 99.5 | 99.4 | 99.3 | 99.3 | 99.3 | 100.0 | 100.0 |
| 30 | COD_MUNICIPIO_INE_VEH | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 31 | MUNICIPIO | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 32 | KW_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 33 | NUM_PLAZAS_MAX | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 34 | CO2_ITV | 90.8 | 92.3 | 88.6 | 85.1 | 84.2 | 84.1 | 83.7 | 12.6 | 39.9 |
| 35 | RENTING | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 55.8 | 84.5 |
| 36 | COD_TUTELA | 0.3 | 0.2 | 0.2 | 0.1 | 0.2 | 0.2 | 0.2 | 0.4 | 0.2 |
| 37 | COD_POSESION | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 4.6 | 10.3 |
| 38 | IND_BAJA_DEF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 56.3 | 49.5 |
| 39 | IND_BAJA_TEMP | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 18.4 | 15.9 |
| 40 | IND_SUSTRACCION | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.9 | 1.7 |
| 41 | BAJA_TELEMATICA | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 41.9 | 49.5 |
| 42 | TIPO_ITV | 11.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.8 | 2.5 |
| 43 | VARIANTE_ITV | 99.8 | 98.3 | 98.5 | 98.3 | 98.3 | 98.3 | 98.1 | 25.7 | 62.4 |
| 44 | VERSION_ITV | 99.7 | 98.2 | 98.5 | 98.3 | 98.3 | 98.3 | 98.0 | 12.0 | 43.6 |
| 45 | FABRICANTE_ITV | 100.0 | 99.9 | 99.9 | 100.0 | 100.0 | 100.0 | 100.0 | 10.1 | 41.5 |
| 46 | MASA_ORDEN_MARCHA_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 47 | MASA_MAXIMA_TECNICA_ADMISIBLE_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 48 | CATEGORIA_HOMOLOGACION_EUROPEA_ITV | 99.8 | 98.5 | 98.6 | 98.3 | 98.3 | 98.3 | 98.0 | 10.2 | 95.7 |
| 49 | CARROCERIA | 92.0 | 86.6 | 80.6 | 88.5 | 87.9 | 87.9 | 87.0 | 9.6 | 35.1 |
| 50 | PLAZAS_PIE | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 51 | NIVEL_EMISIONES_EURO_ITV | 99.2 | 97.2 | 96.3 | 97.0 | 96.8 | 96.9 | 96.3 | 83.2 | 95.1 |
| 52 | CONSUMO_WH_KM_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 53 | CLASIFICACION_REGLAMENTO_VEHICULOS_ITV | 100.0 | 99.0 | 98.9 | 98.6 | 98.6 | 98.6 | 98.4 | 83.8 | 96.7 |
| 54 | CATEGORIA_VEHICULO_ELECTRICO | 0.9 | 5.1 | 24.5 | 43.7 | 45.0 | 43.8 | 41.7 | 0.1 | 7.8 |
| 55 | AUTONOMIA_VEHICULO_ELECTRICO | 99.2 | 99.9 | 99.6 | 100.0 | 100.0 | 100.0 | 100.0 | 1.4 | 42.8 |
| 56 | MARCA_VEHICULO_BASE | 1.8 | 2.1 | 2.9 | 4.5 | 4.5 | 4.2 | 4.6 | 0.0 | 1.3 |
| 57 | FABRICANTE_VEHICULO_BASE | 1.8 | 15.2 | 15.3 | 4.5 | 4.5 | 4.3 | 4.6 | 0.0 | 4.9 |
| 58 | TIPO_VEHICULO_BASE | 1.1 | 0.0 | 1.7 | 8.1 | 8.7 | 8.9 | 7.8 | 0.0 | 0.5 |
| 59 | VARIANTE_VEHICULO_BASE | 1.1 | 2.4 | 1.7 | 8.1 | 8.7 | 8.9 | 7.8 | 0.0 | 0.7 |
| 60 | VERSION_VEHICULO_BASE | 1.1 | 2.4 | 1.7 | 8.1 | 8.7 | 8.9 | 7.8 | 0.0 | 0.7 |
| 61 | DISTANCIA_EJES_12_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 62 | VIA_ANTERIOR_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 63 | VIA_POSTERIOR_ITV | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 64 | TIPO_ALIMENTACION_ITV | 99.7 | 98.4 | 99.0 | 99.4 | 99.3 | 99.4 | 99.2 | 10.2 | 45.0 |
| 65 | CONTRASENA_HOMOLOGACION_ITV | 11.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.8 | 2.5 |
| 66 | ECO_INNOVACION_ITV | 45.7 | 64.2 | 72.6 | 69.6 | 69.1 | 69.2 | 65.5 | 0.9 | 22.9 |
| 67 | REDUCCION_ECO_ITV | 12.2 | 39.8 | 10.4 | 3.1 | 3.6 | 3.3 | 3.0 | 1.5 | 12.0 |
| 68 | CODIGO_ECO_ITV | 1.0 | 17.6 | 54.4 | 39.0 | 37.0 | 38.1 | 34.6 | 0.0 | 12.1 |
| 69 | FEC_PROCESO | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

### 6. Mes del trámite frente al periodo del fichero

| Fichero | Periodo | En el periodo | Fuera | Los tres meses mas frecuentes |
|---|---|---:|---:|---|
| export_mensual_mat_201412.zip | 201412 | 99871 (99.98%) | 17 (0.02%) | 201412: 99871, 201501: 16, 201411: 1 |
| export_mensual_mat_201806.zip | 201806 | 203612 (99.96%) | 75 (0.04%) | 201806: 203612, 201804: 40, 201803: 13 |
| export_mensual_mat_202206.zip | 202206 | 143875 (100.00%) | 0 (0.00%) | 202206: 143875 |
| export_mensual_mat_202604.zip | 202604 | 180135 (100.00%) | 0 (0.00%) | 202604: 180135 |
| export_mensual_mat_202605.zip | 202605 | 189626 (100.00%) | 0 (0.00%) | 202605: 189626 |
| export_mensual_mat_202606.zip | 202606 | 217004 (100.00%) | 0 (0.00%) | 202606: 217004 |
| export_mensual_mat_202607.zip | 202607 | 189104 (100.00%) | 0 (0.00%) | 202607: 189104 |
| export_mensual_bajas_201412.zip | 201412 | 242279 (99.99%) | 33 (0.01%) | 201412: 242279, 201312: 6, 201212: 6 |
| export_mensual_bajas_202607.zip | 202607 | 147317 (97.48%) | 3811 (2.52%) | 202607: 147317, 202606: 1593, 202512: 492 |

### 7. Qué trae FEC_TRAMITACION

| Fichero | vacío | = FEC_MATRICULA | = FEC_TRAMITE | otra fecha |
|---|---:|---:|---:|---:|
| export_mensual_mat_201412.zip | 96167 | 37 | 0 | 3684 |
| export_mensual_mat_201806.zip | 196581 | 75 | 16 | 7015 |
| export_mensual_mat_202206.zip | 138462 | 27 | 3 | 5383 |
| export_mensual_mat_202604.zip | 173206 | 13 | 0 | 6916 |
| export_mensual_mat_202605.zip | 182347 | 12 | 0 | 7267 |
| export_mensual_mat_202606.zip | 208942 | 13 | 1 | 8048 |
| export_mensual_mat_202607.zip | 180809 | 19 | 0 | 8276 |
| export_mensual_bajas_201412.zip | 54623 | 21 | 32237 | 155431 |
| export_mensual_bajas_202607.zip | 30408 | 8 | 30723 | 89989 |

### 8. El mensual contra la suma de sus diarios: no medible hoy

**No se pudo hacer el 2026-09-01, ni seguía siendo posible el 2026-09-02, y no por falta de trabajo.** La comparación necesita un mes que tenga a la vez su fichero mensual y sus diarios, y hoy eso no existe: el mensual de agosto de 2026 aún no está publicado —la URL devuelve 404, y el de julio se publicó el 15 de agosto, así que el de agosto saldrá hacia mediados de septiembre— y de julio ya no quedan diarios, porque la DGT sólo mantiene los últimos veinte días.

Lo que sí se ha hecho es **guardar los 22 diarios de agosto que quedaban publicados**, con sus 126.404 altas, y los 31 de bajas. En cuanto salga el mensual de agosto —hacia el 15 de septiembre, según cuándo se publicó el de julio— la medición es inmediata y ya no depende de nadie. Si no se hubieran descargado el 2026-09-01, esa comparación habría sido imposible para siempre.

### 9. Bytes 0x80-0x9F (donde ISO-8859-1 y CP1252 difieren)

| Fichero | Apariciones | Detalle |
|---|---:|---|
| export_mensual_mat_201412.zip | 0 | - |
| export_mensual_mat_201806.zip | 0 | - |
| export_mensual_mat_202206.zip | 0 | - |
| export_mensual_mat_202604.zip | 0 | - |
| export_mensual_mat_202605.zip | 0 | - |
| export_mensual_mat_202606.zip | 0 | - |
| export_mensual_mat_202607.zip | 0 | - |
| export_mensual_bajas_201412.zip | 6 | 0x87 x6 |
| export_mensual_bajas_202607.zip | 1 | 0x91 x1 |

### 10. Reparto de CLAVE_TRAMITE

| Fichero | `1` | `3` | `4` | `5` | `6` | `7` | `9` | `A` | `B` | otros |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| export_mensual_mat_201412.zip | 99172 | 0 | 0 | 249 | 0 | 0 | 0 | 0 | 467 | 0 |
| export_mensual_mat_201806.zip | 199329 | 0 | 0 | 1164 | 0 | 0 | 2144 | 47 | 1001 | 2 |
| export_mensual_mat_202206.zip | 140186 | 0 | 0 | 548 | 0 | 0 | 2170 | 0 | 971 | 0 |
| export_mensual_mat_202604.zip | 174402 | 0 | 0 | 21 | 0 | 0 | 3760 | 0 | 1952 | 0 |
| export_mensual_mat_202605.zip | 183530 | 0 | 0 | 24 | 0 | 0 | 3957 | 0 | 2115 | 0 |
| export_mensual_mat_202606.zip | 210091 | 0 | 0 | 25 | 0 | 0 | 4423 | 0 | 2465 | 0 |
| export_mensual_mat_202607.zip | 181962 | 0 | 0 | 23 | 0 | 0 | 4568 | 0 | 2551 | 0 |
| export_mensual_bajas_201412.zip | 0 | 114703 | 0 | 0 | 105823 | 21786 | 0 | 0 | 0 | 0 |
| export_mensual_bajas_202607.zip | 0 | 61826 | 0 | 0 | 76259 | 13043 | 0 | 0 | 0 | 0 |
