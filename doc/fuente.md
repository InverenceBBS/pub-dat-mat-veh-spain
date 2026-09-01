<!--
Documento abierto el 2026-08-31, en la primera pasada del repositorio, antes de escribir una línea de código.
Su objetivo es que cualquiera que llegue al repositorio sepa qué se descarga, de dónde, cuánto pesa y qué limitaciones tiene, sin repetir el reconocimiento.
Todas las cifras de tamaños están medidas ese día contra el servidor de la DGT y van fechadas en el cuerpo, porque envejecen solas: el histórico crece un mes cada mes.
El alcance se decidió el mismo día y vive aparte, en alcance.md: aquí queda sólo lo que se ha medido de la fuente.
-->

# La fuente: microdatos de matriculaciones de la DGT

La [Dirección General de Tráfico](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Matriculaciones-de-Vehiculos-diarios/) publica en abierto los microdatos de los trámites de matriculación de vehículos en España: un registro por trámite, con las características técnicas del vehículo y el domicilio del titular. No hace falta registrarse ni pedir nada para descargarlos.

## Qué hay publicado

El mismo contenido, con idéntico [diseño de registro](diseno-de-registro.md), en dos series con idéntica raíz URL 
```
ROOT=https://www.dgt.es/microdatos/salida/YYYY/M/vehiculos/matriculaciones
```

| Serie | Patrón de URL | Página de listado | Cobertura |
|---|---|---|---|
| Diaria | `<ROOT>/export_mat_YYYYMMDD.zip` | [matriculaciones-automoviles-diario](https://www.dgt.es/menusecundario/dgt-en-cifras/matraba-listados/matriculaciones-automoviles-diario.html) | sólo los últimos ~20 días |
| Mensual | `<ROOT>/export_mensual_mat_YYYYMM.zip` | [matriculaciones-automoviles-mensual](https://www.dgt.es/menusecundario/dgt-en-cifras/matraba-listados/matriculaciones-automoviles-mensual.html) | desde **2014-12** hasta el mes cerrado |

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

A pesar del nombre, el fichero **no trae sólo matriculaciones ordinarias**. El propio documento de la DGT enumera los trámites incluidos: matriculaciones de vehículos, de ciclomotores, temporales para empresas, temporales, rematriculaciones, prórrogas de matrícula temporal y pasos de matrícula temporal a definitiva.

El diccionario de `CLAVE_TRAMITE` es más ancho que eso y llega a incluir transferencias y bajas, pero **eso es porque el mismo diccionario sirve para los tres ficheros hermanos** de la DGT. En el de matriculaciones sólo aparecen trámites de alta. Contado sobre `export_mat_20260828.txt`, sus 10.486 registros se reparten así:

| `CLAVE_TRAMITE` | Descripción | Registros |
|---|---|---:|
| 1 | Matriculación ordinaria y de ciclomotores | 10.259 |
| 9 | Matriculación temporal | 133 |
| B | Paso de matrícula temporal a definitiva | 93 |
| 5 | Rematriculación | 1 |

Ni una baja, ni una transferencia. Aun así hay que mirar `CLAVE_TRAMITE`, porque el `9` y el `B` son **el mismo vehículo contado dos veces** si se suman sin más: primero se matricula en temporal y después pasa a definitiva. Y en el mismo fichero, **9.630 registros son de vehículo nuevo y 856 de usado** (`IND_NUEVO_USADO`), o sea un 8,1% de altas de usados. De esos usados, **835 (97,5%) constan como importación** —790 comunitaria y 45 extracomunitaria—: no son vehículos españoles que cambian de papeles, sino vehículos que entran por primera vez en el parque, y por eso [cuentan en los agregados](alcance.md#1-los-usados-entran-son-importaciones-no-rematriculaciones).

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

## Las otras fuentes de la DGT

Las matriculaciones son una de cuatro familias de microdatos de vehículos que publica la DGT, todas con la misma mecánica de listados diarios y mensuales:

| Familia | Raíz de la URL | Cobertura mensual | Diseño de registro |
|---|---|---|---|
| [Matriculaciones](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Matriculaciones-de-Vehiculos-diarios/) | `.../YYYY/M/vehiculos/matriculaciones` | desde 2014-12 | [MATRICULACIONES_MATRABA.pdf](https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/matraba/MATRICULACIONES_MATRABA.pdf) |
| [Bajas](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Bajas-de-Vehiculos-diarios/) | `.../YYYY/M/vehiculos/bajas` | desde 2014-12 | [BAJAS_MATRABA.pdf](https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/matraba/BAJAS_MATRABA.pdf) |
| [Transferencias](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Transferencias-de-Vehiculos-diarios/) | `.../YYYY/M/vehiculos/transferencias` | no comprobada | no comprobado |
| [Parque de vehículos](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-parque-de-vehiculos-mensual/) | `https://www.dgt.es/microdatos/Parque/` | desde 2025-03 (mensual) | [Interfaz-de-Salida-Fichero-Parque-Anual.pdf](https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/matraba/Interfaz-de-Salida-Fichero-Parque-Anual.pdf) |

### Bajas

Entra en el [alcance](alcance.md) por decisión expresa. Los nombres de fichero son `export_bajas_YYYYMMDD.zip` y `export_mensual_bajas_YYYYMM.zip`, y el histórico mensual arranca en **2014-12**, igual que el de matriculaciones.

**El diseño de registro es el mismo**: 714 bytes, 69 campos, en el mismo orden y con las mismas longitudes. La única diferencia entre los dos documentos oficiales es el nombre del campo 14, que en bajas se llama `NUM_PLAZAS_ITV` y en matriculaciones `NUM_PLAZAS`; el contenido descrito es idéntico. O sea que **el mismo troceado sirve para las dos fuentes**, y pueden vivir en la misma tabla con una columna que diga de qué fichero vienen.

Dos diferencias que sí afectan a la carga, medidas sobre `export_bajas_20260828.txt`:

- **El fichero de bajas no lleva línea de cabecera**, ni siquiera el diario. Todas sus líneas son registros de 714 bytes.
- Es **más pequeño**: 6.268 bajas ese día frente a 10.486 altas. Los mensuales, en cambio, pesan parecido (14.673.454 bytes el de 2026-07) y los antiguos pesan **más** que los de matriculaciones (20.415.430 bytes el de 2014-12, contra 9.481.060 el de matriculaciones del mismo mes): en aquel momento se achatarraba mucho más de lo que se matriculaba.

Y el contenido es el esperado, con una sorpresa que importa mucho para el ciclo de vida. Reparto de los 6.268 registros de ese día:

| `CLAVE_TRAMITE` | Descripción | Registros |
|---|---|---:|
| 6 | Baja temporal | 3.784 |
| 3 | Baja definitiva (excluidos Plan Renove, exportación y tránsito comunitario) | 2.110 |
| 7 | Baja definitiva por exportación y por tránsito comunitario | 374 |

**El 60% de las bajas son temporales**, y una baja temporal no saca al vehículo del parque: se da de baja para no pagar seguro mientras está parado, y vuelve. Sumar bajas sin separar por `CLAVE_TRAMITE` cuenta como desaparecidos vehículos que siguen existiendo. Coherentemente, en esos 3.784 registros `IND_BAJA_DEF` viene en blanco; en las bajas definitivas sí trae el motivo, y ese día el reparto fue 1.933 por exportación (`7`), 316 por tránsito comunitario (`9`), 129 de oficio por abandono (`A`), 58 exportación (`8`), 32 desguace (`0`) y 16 por tratamiento residual (`C`).

### Parque de vehículos

No estaba en el encargo, pero es la fuente que responde directamente a «agregados de parque móvil», así que conviene saber que existe: la DGT publica **el censo completo de vehículos**, no los eventos. Hay versión anual y versión mensual, y esta última **sólo desde 2025-03**, en fichero nacional (`parque_vehiculos_YYYYMM.zip`) y en ficheros por provincia (`parque_vehiculos_YYYYMM_PROVINCIA.zip`).

El precio es el tamaño: el nacional de 2026-07 pesa **1.748.777.115 bytes comprimido**, o sea unas cien veces un mensual de matriculaciones. Un solo mes de parque pesa más que todo el histórico de matriculaciones junto. Su diseño de registro es **distinto** al de MATRABA y no se ha analizado.

## El alcance

Las cuatro decisiones que quedaban abiertas en este documento las cerró Víctor el 2026-08-31 y están en [alcance.md](alcance.md), junto con las tres tensiones que hay que resolver antes de dar por buenos los agregados.
