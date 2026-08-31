<!--
Documento abierto el 2026-08-31, en la primera pasada del repositorio, antes de escribir una línea de código.
Su objetivo es que cualquiera que llegue al repositorio sepa qué se descarga, de dónde, cuánto pesa y qué limitaciones tiene, sin repetir el reconocimiento.
Todas las cifras de tamaños están medidas ese día contra el servidor de la DGT y van fechadas en el cuerpo, porque envejecen solas: el histórico crece un mes cada mes.
Lo que queda por decidir está al final a propósito: son decisiones de alcance, no hallazgos.
-->

# La fuente: microdatos de matriculaciones de la DGT

La [Dirección General de Tráfico](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Matriculaciones-de-Vehiculos-diarios/) publica en abierto los microdatos de los trámites de matriculación de vehículos en España: un registro por trámite, con las características técnicas del vehículo y el domicilio del titular. No hace falta registrarse ni pedir nada para descargarlos.

## Qué hay publicado

El mismo contenido, con idéntico [diseño de registro](diseno-de-registro.md), en dos series:

| Serie | Patrón de URL | Página de listado | Cobertura |
|---|---|---|---|
| Diaria | `https://www.dgt.es/microdatos/salida/YYYY/M/vehiculos/matriculaciones/export_mat_YYYYMMDD.zip` | [matriculaciones-automoviles-diario](https://www.dgt.es/menusecundario/dgt-en-cifras/matraba-listados/matriculaciones-automoviles-diario.html) | sólo los últimos ~20 días |
| Mensual | `https://www.dgt.es/microdatos/salida/YYYY/M/vehiculos/matriculaciones/export_mensual_mat_YYYYMM.zip` | [matriculaciones-automoviles-mensual](https://www.dgt.es/menusecundario/dgt-en-cifras/matraba-listados/matriculaciones-automoviles-mensual.html) | desde **2014-12** hasta el mes cerrado |

Dos detalles del patrón de URL que importan al programar la descarga: el mes va **sin cero a la izquierda** en la ruta (`/2026/8/`) y **con** cero en el nombre del fichero (`202608`); y el año y el mes de la ruta son los del periodo, no los de la publicación.

O sea que el reparto natural del trabajo es: **el histórico se construye con los mensuales y el día a día se mantiene con los diarios**. Las URLs son predecibles, así que sólo hace falta leer el HTML del listado para saber qué días están publicados; el resto se genera.

La página oficial declara actualización **diaria**. Cada fichero ZIP contiene un único `.txt` con el mismo nombre.

## Cuánto pesa (medido el 2026-08-31)

| Medida | Valor |
|---|---|
| Diario `export_mat_20260828.zip` | 1.037.496 bytes comprimido |
| Su `.txt` | 7.497.570 bytes, **10.487 líneas** (10.486 registros más la cabecera) |
| Ratio de compresión | **7,2×** |
| Mensual `export_mensual_mat_202607.zip` | 17.837.719 bytes |
| Mensual más antiguo, `export_mensual_mat_201412.zip` | 9.481.060 bytes |
| Media de 24 mensuales muestreados entre 2015 y 2025 | **13,6 MB** (rango 10,4 - 17,6) |

Extrapolando esa media a los 139 meses publicados:

- **≈ 1,8 GB** de descarga comprimida,
- **≈ 13 GB** de texto plano,
- **≈ 20 millones de registros** (unos 1,7 millones al año).

Es un volumen cómodo para una única tabla de PostgreSQL, aun sin trucos: con los tipos ajustados (fechas como `date`, códigos como `char`, los textos largos casi todos vacíos) la tabla cruda queda en el orden de 6-8 GB más índices. La mayor parte del ancho se la llevan los campos de texto descriptivos —`FABRICANTE_ITV` son 70 caracteres, `FABRICANTE_VEHICULO_BASE` 50, marca y modelo 30 y 22—, así que normalizarlos a catálogos baja el tamaño de forma apreciable.

## El fichero

Texto de **ancho fijo, 714 bytes por línea**, **ISO-8859-1**, **69 campos**, sin cabecera de columnas. El detalle campo a campo está en [diseno-de-registro.md](diseno-de-registro.md) y las tablas de códigos en [tablas-de-codigos.md](tablas-de-codigos.md).

La única diferencia entre las dos series es la primera línea: **el fichero diario empieza con una línea de cabecera** de 79 bytes con el literal `Vehículos matriculados. Letras de la serie de la última matrícula asignada: ` y las tres letras de la última matrícula asignada. **El mensual no la lleva**, según dice el documento oficial en la página 3. La carga tiene que saltarla en los diarios, y no puede hacerlo por longitud sin más: hay que reconocerla.

## Qué contiene realmente

A pesar del nombre, el fichero **no trae sólo matriculaciones**. El propio documento de la DGT enumera los trámites incluidos: matriculaciones de vehículos, de ciclomotores, temporales para empresas, temporales, rematriculaciones, prórrogas de matrícula temporal y pasos de matrícula temporal a definitiva. Y el diccionario de `CLAVE_TRAMITE` va más allá e incluye transferencias y bajas —definitivas, temporales, por Plan Renove, por exportación—. Filtrar por `CLAVE_TRAMITE` y por `COD_CLASE_MAT` no es un refinamiento: es lo que separa una serie de matriculaciones de un revuelto de trámites.

Los campos se agrupan así:

- **El trámite**: `FEC_MATRICULA`, `FEC_TRAMITACION`, `FEC_TRAMITE`, `FEC_PROCESO`, `FEC_PRIM_MATRICULACION`, `CLAVE_TRAMITE`, `COD_CLASE_MAT`, `IND_NUEVO_USADO`.
- **La geografía**: `COD_PROVINCIA_VEH`, `COD_PROVINCIA_MAT`, `COD_MUNICIPIO_INE_VEH`, `MUNICIPIO`, `LOCALIDAD_VEHICULO`, `CODIGO_POSTAL`. Es el mayor atractivo de la fuente: llega a municipio y código postal.
- **El titular**, sin identificarlo: `PERSONA_FISICA_JURIDICA` (física/jurídica), `RENTING`, `NUM_TITULARES`, `NUM_TRANSMISIONES`, `COD_POSESION`, `COD_TUTELA`.
- **La ficha técnica**, que es la mitad del ancho del registro: marca, modelo, tipo, variante, versión, fabricante, carrocería, cilindrada, potencia fiscal y en kW, tara, pesos y masas, plazas, CO2, nivel EURO, propulsión, consumo Wh/km, autonomía eléctrica, distancia entre ejes y vías.
- **El estado del vehículo**: `IND_BAJA_DEF`, `IND_BAJA_TEMP`, `IND_SUSTRACCION`, `IND_PRECINTO`, `IND_EMBARGO`, `BAJA_TELEMATICA`.

## Limitaciones que condicionan cualquier uso

**No hay identificador de vehículo utilizable.** `BASTIDOR_ITV` viene truncado —los primeros caracteres y el resto a asteriscos, `WVGZZZCT3T***********`—, y desde el **1 de febrero de 2025** obtener el bastidor completo exige acreditar interés legítimo mediante un formulario ante la DGT. Sin bastidor completo no se puede seguir un vehículo entre ficheros ni deduplicar con garantías: **esto es un fichero de eventos, no un censo del parque**, y sumar matriculaciones no da el parque circulante porque las bajas no se pueden casar con su matriculación.

**No hay matrícula ni identificación del titular.** Ni siquiera el sexo o la edad. El detalle máximo real de un registro es *un trámite, un día, un municipio, un modelo*.

**Los campos que se han ido añadiendo no están rellenos hacia atrás.** El diseño de registro es el de hoy, pero el histórico arranca en 2014-12: los campos de vehículo eléctrico, consumo, autonomía o vehículo base no pueden existir en los primeros años con la misma cobertura. Cuánto y desde cuándo hay que **medirlo** al cargar, no suponerlo.

**Y la geografía es la del domicilio, no la del punto de venta.** `COD_PROVINCIA_VEH` es donde está domiciliado el vehículo y `COD_PROVINCIA_MAT` donde se matriculó; ninguno de los dos es dónde se vendió. En las flotas de renting y en las empresas de alquiler la divergencia es grande y sistemática, no ruido.

## Lo que queda por decidir

Estas decisiones son de alcance y afectan a todo lo que se construya encima, así que se toman antes de codificar la ETL:

1. **Alcance histórico**: los 139 meses desde 2014-12 o sólo los últimos años.
2. **Qué trámites entran**: todos los de `CLAVE_TRAMITE`, o sólo las matriculaciones; y dentro de ellas, si entran ciclomotores, remolques, vehículos especiales y matrículas temporales.
3. **Granularidad de destino**: registro crudo con los 69 campos; registro depurado con catálogos normalizados; o sólo agregados por periodo, geografía y tipo de vehículo.
4. **Qué hacer con los diarios y los mensuales a la vez**: si el mensual se considera la versión definitiva del periodo y sustituye a los diarios ya cargados, o si conviven. Los diarios de un mes y su mensual **no tienen por qué coincidir registro a registro**, y eso hay que medirlo antes de decidir.
