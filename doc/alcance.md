<!--
Documento abierto el 2026-08-31, el mismo día que el repositorio, en cuanto Víctor cerró las cuatro decisiones que quedaban abiertas en fuente.md.
Existe para que el alcance esté escrito antes que el código y no se vaya reinterpretando cada vez que alguien toca la ETL. Sus decisiones van citadas literalmente y marcadas como suyas; lo que viene detrás de cada una es análisis nuestro y puede estar equivocado.
Las tensiones del final no son objeciones: son puntos donde lo pedido y lo que hace falta para conseguirlo no coinciden del todo, y donde alguien tendrá que decidir. Se dejan escritas porque si no se olvidan.
La tensión 1 se cerró el mismo día, cuando Víctor precisó que las altas de usados son importaciones y no rematriculaciones domésticas: se comprobó contra los datos por procedencia y por trámite antes de darla por buena, y la comprobación se dejó escrita porque es la que justifica que los usados cuenten en el parque.
La tensión 3 se reescribió el mismo día: nació como «hace falta un catálogo externo para llegar a la medida del neumático» y Víctor la rebajó a clases gruesas de tamaño, con el argumento de que el desgaste lo marcan los kilómetros y no el tiempo. Lo que se sabía de la medida exacta no se borró, se movió detrás y se marcó como no necesario hoy: si el mapeo fino vuelve al alcance, está ahí y no hay que volver a investigarlo.
-->

# Alcance

## Las decisiones

Dictadas por Víctor de Buen el 2026-08-31, en respuesta a las cuatro decisiones que quedaban abiertas en [fuente.md](fuente.md):

***NOTA VBR***: *Todo el histórico de matriculaciones de vehículos nuevos de cualquier tipo al máximo nivel geográfico. Las bajas también son muy interesantes aunque no se puedan casar. Queremos formar agregados de parque móvil y ciclo de vida con mucho detalle. No nos interesa el titular para nada pero sí la ficha técnica porque afecta al tipo de neumáticos que necesitará. El mensual sustituye a los diarios sin contemplaciones.*

De ahí, y de una precisión suya posterior sobre los usados, se derivan seis cosas:

| Decisión | Qué significa en la práctica |
|---|---|
| **Todo el histórico** | Los 139 meses publicados, desde 2014-12. No se recorta por antigüedad. |
| **De cualquier tipo** | No se filtra por `COD_TIPO` ni por `COD_CLASE_MAT`: entran turismos, furgonetas, camiones, autobuses, motocicletas, ciclomotores, remolques, semirremolques y vehículos especiales. |
| **Al máximo nivel geográfico** | Se conservan `COD_MUNICIPIO_INE_VEH`, `MUNICIPIO`, `LOCALIDAD_VEHICULO` y `CODIGO_POSTAL`, además de las dos provincias. El código postal es el grano más fino que da la fuente. |
| **Las bajas también** | Entra una segunda fuente, el fichero de bajas, con su propio histórico. Ver [fuente.md](fuente.md#las-otras-fuentes-de-la-dgt). |
| **Y los usados también** | `IND_NUEVO_USADO` es dimensión, no filtro. Las altas de usados son importaciones que entran por primera vez en el parque español, no rematriculaciones de vehículos que ya estaban. Ver [la tensión 1](#1-los-usados-entran-son-importaciones-no-rematriculaciones). |
| **El mensual manda** | Cargar el mensual de un periodo **borra y sustituye** lo que hubiera de ese periodo, venga de diarios o de una carga anterior. No hay reconciliación, no hay conservación de lo viejo. |

Y dos cosas quedan fuera:

- **El titular no interesa**: `PERSONA_FISICA_JURIDICA`, `NUM_TITULARES`, `COD_TUTELA` y `COD_POSESION` no alimentan ningún agregado. Se cargan igualmente porque el registro es de ancho fijo y descartarlos no ahorra trabajo, pero no se modelan.
- **Casar altas con bajas no se intenta**: es imposible sin el bastidor completo, y Víctor lo da por asumido («aunque no se puedan casar»). Los agregados de ciclo de vida se construyen sobre **distribuciones**, no sobre vehículos individuales seguidos en el tiempo.

## Qué implica «el mensual sustituye a los diarios sin contemplaciones»

Es la decisión con más consecuencias técnicas, y todas van en la dirección de simplificar:

- **La unidad de carga es el mes.** Las tablas se particionan por mes del periodo del fichero, y recargar un mes es borrar su partición y volver a insertar. Idempotente por construcción, sin claves de deduplicación ni `ON CONFLICT`.
- **Los diarios son provisionales por definición.** Sólo cubren el mes en curso, que aún no tiene mensual publicado. En cuanto sale el mensual del periodo, lo que se cargó día a día se tira.
- **No hace falta medir si diarios y mensual coinciden** para decidir nada —era la cuarta decisión abierta—, pero **sí conviene medirlo igualmente y dejar constancia**: si el mensual trae sistemáticamente más registros que la suma de sus diarios, eso dice algo sobre el retraso con que la DGT consolida, y ese retraso afecta a cualquier serie que se publique sobre el mes en curso.
- Hace falta una **tabla de control de cargas** que registre, por fichero, qué se cargó, cuándo, con qué `last-modified` y `etag` del servidor y cuántas filas entraron. Sin ella no se sabe si un mes está en versión diaria o mensual.

## Tensiones que hay que resolver

Tres puntos donde lo pedido y lo que hace falta para conseguirlo no coincidían del todo. No eran objeciones al alcance: eran avisos de que había una decisión escondida. **La 1 y la 3 las ha resuelto Víctor**, y se conservan con su resolución porque el porqué sigue haciendo falta para leer los agregados; **la 2 sigue esperando confirmación** y mientras tanto se trabaja como dice el propio apartado.

### 1. Los usados entran: son importaciones, no rematriculaciones

**Resuelta el 2026-08-31.** Nació como tensión porque «matriculaciones de vehículos nuevos» y «parque móvil» tiran en direcciones opuestas: `IND_NUEVO_USADO` vale `N` o `U`, y en la muestra del 2026-08-28 hay **9.630 nuevos y 856 usados**, un 8,1% de las altas. Filtrar por `N` habría dejado fuera vehículos que ruedan y gastan neumáticos.

***NOTA VBR***: *Me he liado con los usados, no son rematriculaciones domésticas sino importaciones, así que deben entrar también.*

Los datos le dan la razón por dos caminos independientes:

- **Por procedencia.** De los 856 usados, **835 (97,5%) constan como importación**: 790 de la U.E. (`COD_PROCEDENCIA_ITV` = 3) y 45 extracomunitaria (= 1). Sólo 21 figuran como fabricación nacional.
- **Por trámite.** La rematriculación tiene clave propia, `CLAVE_TRAMITE` = 5, y ese día hubo **exactamente una** en todo el fichero. Los usados llegan por matriculación ordinaria (674), paso de temporal a definitiva (93) y matriculación temporal (88).

O sea que un vehículo usado en este fichero es un vehículo que **entra por primera vez en el parque español**, no uno que ya estaba y cambia de papeles. Entra en los agregados igual que un nuevo, y `IND_NUEVO_USADO` se conserva como **dimensión**, no como filtro, para poder separar el mercado de vehículo nuevo cuando interese.

Y de paso aparece un detalle que importa al contar: los **93 registros de «paso de matrícula temporal a definitiva» de ese día son todos usados**, y 88 de las 133 matriculaciones temporales también. O sea que el doble conteo del que avisa [fuente.md](fuente.md#qué-contiene-realmente) —trámite `9` y trámite `B` son el mismo vehículo dos veces— **está concentrado justo en el segmento de importación de usados**. Contar altas de usados sin resolver ese par infla precisamente el segmento que ahora entra en el alcance.

Queda en pie un aviso sobre el propio campo: el documento de la DGT dice que `IND_NUEVO_USADO` **«se calcula en el almacén de datos»**, no que venga del trámite. Un campo calculado por el emisor puede haber cambiado de criterio a lo largo de once años; conviene vigilar su serie temporal antes de fiarse de un salto.

### 2. «El titular no interesa», pero el régimen de uso sí debería

`RENTING` y `SERVICIO` **no son datos del titular**: dicen cómo se usa el vehículo. Y para lo que se persigue —desgaste y reposición de neumáticos— son de los campos más informativos del registro: un vehículo de renting o un taxi (`SERVICIO` = `A04`) recorre en un año lo que un particular en cuatro, y cambia neumáticos en esa proporción. Lo mismo `A01`/`A02` (alquiler), `A03` (autoescuela) o `B06` (agrícola).

Se conservan y se modelan como dimensión. Si la intención era descartarlos también, hay que decirlo, porque entonces el ciclo de vida pierde su variable más explicativa.

### 3. La ficha técnica no llega hasta el neumático

Esto era lo importante de las tres mientras el objetivo fue la medida exacta. **Dejó de serlo el 2026-08-31**, cuando Víctor rebajó lo que hace falta:

***NOTA VBR***: *En realidad sólo podemos aspirar a tener unos drivers bastante difusos porque el cambio de neumáticos no lo marca tanto el tiempo transcurrido sino los kilómetros recorridos, por lo que la función de transferencia será bastante difusa. Es muy probable que nos baste con que podamos diferenciar coches pequeños, medianos, grandes, todo-terrenos, furgonetas, camiones pequeños...*

El razonamiento es de física del problema, no de disponibilidad de datos: **lo que agota un neumático son los kilómetros, no los meses**, y el kilometraje no está en ninguna fuente pública española. Aunque se conociera la medida exacta de cada vehículo matriculado, entre la matriculación y la reposición hay un retardo difuso de varios años, con una dispersión que ninguna medida de neumático reduce. Afinar el mapeo hasta la referencia sería precisión gastada sobre un retardo que no se conoce.

Así que lo que hay que producir no es «qué neumático monta este coche», sino **cuántos vehículos de cada clase de tamaño entraron y salieron del parque de cada zona**. Y eso sí sale del fichero, sin catálogo externo ninguno.

#### La segmentación por tamaño sale del propio registro

Medido sobre `export_mat_20260828.txt`, la cobertura de los campos que la sostienen es prácticamente total:

| Campo | Cobertura | Para qué sirve |
|---|---:|---|
| `TARA`, `MASA_ORDEN_MARCHA_ITV`, `MASA_MAXIMA_TECNICA_ADMISIBLE_ITV` | 100% | el mejor discriminante de tamaño |
| `DISTANCIA_EJES_12_ITV` | 100% | batalla en mm; separa segmentos casi sola |
| `VIA_ANTERIOR_ITV`, `VIA_POSTERIOR_ITV` | 100% | anchura de vía en mm; es geometría de rueda |
| `KW_ITV`, `CILINDRADA_ITV` | 100% | potencia, que acota el índice de velocidad |
| `COD_TIPO` | 99,2% | la clase gruesa, ya codificada |
| `CATEGORIA_HOMOLOGACION_EUROPEA_ITV` | 99,0% | M1, N1, N2, N3, L… |
| `CARROCERIA` | 91,4% | carrocería europea AA-AF |

Los valores son reales y utilizables tal cual: `2677|1590|1583|1601` para un Tiguan (batalla, vía anterior, vía posterior en mm y masa en kg), `2300|1414|1408|1045` para un utilitario pequeño. Una motocicleta trae las vías a cero, que es lo correcto.

Y buena parte de las clases que pide Víctor **ya vienen codificadas** en `COD_TIPO`. Reparto de ese día:

| `COD_TIPO` | Clase | Registros |
|---|---|---:|
| 40 | Turismo | 7.724 |
| 50 | Motocicleta de 2 ruedas | 1.112 |
| 20 | Furgoneta | 644 |
| 0G | Vehículo mixto adaptable | 247 |
| 25 | Todo terreno | 124 |
| 81 | Tractocamión | 104 |
| 02 | Camión caja | 78 |
| 90 | Ciclomotor de 2 ruedas | 49 |
| 80 | Tractor | 44 |

Furgonetas, camiones —con su desglose por carrozado y por articulado, que da el tamaño—, tractocamiones, autobuses, motos y ciclomotores salen directamente del código. Lo que **no** sale hecho son dos cosas:

- **Pequeño, mediano y grande dentro del turismo.** No hay ningún campo que lo diga: hay que construirlo con umbrales sobre masa y batalla, o dejando que los datos formen los grupos. Es trabajo nuestro, pero es trabajo sobre campos con cobertura del 100%.
- **El todoterreno o SUV.** Ojo con esto, que es contraintuitivo: `COD_TIPO` = 25 sólo recogió **124 vehículos** ese día frente a 7.724 turismos, cuando el SUV es hoy más de la mitad del mercado. **Los SUV se matriculan como turismo**, y la carrocería europea tampoco los distingue —entre los turismos de ese día: 3.265 `AB` (dos volúmenes), 2.294 `AC` (familiar), 1.672 `AF` (multiuso), 401 `AA` (berlina)—, porque «SUV» no es una categoría de homologación. Justo la clase que Víctor nombra por su nombre es la única que hay que **derivar** con un clasificador, y la altura libre al suelo, que sería el discriminante natural, no viene en el registro.

#### Y lo de la medida exacta, por si vuelve a hacer falta

Lo que sigue queda documentado por si el mapeo fino vuelve al alcance; **hoy no hace falta para producir los agregados**.

Lo que el registro trae y sirve para acercarse a la medida:

- `CATEGORIA_HOMOLOGACION_EUROPEA_ITV` (M1, N1, L3e…), `CARROCERIA`, `CLASIFICACION_REGLAMENTO_VEHICULOS_ITV`.
- `MASA_MAXIMA_TECNICA_ADMISIBLE_ITV` y `MASA_ORDEN_MARCHA_ITV`, `TARA` y `PESO_MAX`: la carga por eje acota el índice de carga.
- `DISTANCIA_EJES_12_ITV`, `VIA_ANTERIOR_ITV` y `VIA_POSTERIOR_ITV`, en milímetros: geometría del vehículo.
- `KW_ITV` y `POTENCIA_ITV`: acotan el índice de velocidad.

#### La clave de cruce es la contraseña de homologación, no el TVV

Contado sobre los 10.486 registros de `export_mat_20260828.txt`:

| Campo | Registros con valor |
|---|---:|
| `CONTRASENA_HOMOLOGACION_ITV` | 10.348 (**98,7%**) |
| `CATEGORIA_HOMOLOGACION_EUROPEA_ITV` | 10.382 (99,0%) |
| `VARIANTE_ITV` | 10.381 (99,0%) |
| `VERSION_ITV` | 10.379 (99,0%) |
| `TIPO_ITV` | **0 (0,0%)** |
| `CODIGO_ITV` | 9 (0,1%) |

O sea que **el TVV está cojo**: llegan la variante y la versión, pero el tipo viene vacío en todos los registros de ese día, y `CODIGO_ITV` es prácticamente inexistente. Lo que sí llega, y casi siempre, es la **contraseña de homologación**, bien formada y con el formato europeo estándar: `E1*2018/858*00302*10`, `E9*2007/46*0355*26`. Ésa es la clave por la que hay que intentar el cruce.

(La medición es de un solo día. Antes de construir nada encima hay que repetirla sobre todo el histórico, porque son campos que la DGT fue añadiendo y en los primeros años pueden venir vacíos.)

#### Dónde puede estar el catálogo

Cuatro vías, exploradas el 2026-08-31:

1. **Fichas Técnicas Reducidas del Ministerio de Industria (GIAVEH)** — es la vía pública más prometedora. El buscador de [consulta de fichas reducidas](https://industria.serviciosmin.gob.es/FichasReducidasv2/UI/Solicitudes/Extranet/ConsultaFichasReducidas) **responde sin certificado digital** y busca precisamente por **contraseña de homologación**, además de por fabricante, marca y tipo de ficha. La ficha técnica reducida es el documento que recoge las características técnicas asociadas a una contraseña de homologación, neumáticos incluidos, y la base la comparte el Ministerio con las estaciones de ITV. Lo que falta por comprobar: qué devuelve exactamente cada consulta, si el resultado es un PDF o datos, y **qué cobertura tiene** —el registro contiene las fichas reducidas tramitadas, que no tienen por qué ser todas las homologaciones en circulación—. Y es consulta unitaria: no hay descarga masiva publicada.
2. **La ficha técnica del vehículo (eITV)**, que sí lleva las medidas de neumático homologadas. Es por vehículo y requiere identificarse como titular, así que no sirve para construir un catálogo.
3. **Los datos abiertos de la RDW neerlandesa**, que publica en abierto el registro de homologaciones europeas. **Descartada, comprobada**: sus trece datasets de *Typegoedkeuring* no traen medida de neumático. El de ejes por versión (`TGK As Uitvoering`) llega hasta el ancho de vía y la carga máxima por eje, y el único dataset con «banden» en el nombre es el de vehículos de **oruga**.
4. **Catálogos comerciales** de equipamiento original y sustitución —TecDoc/TecAlliance y equivalentes—, que es lo que usa el sector del recambio. Es la vía que resuelve el problema de verdad, y la que casi con seguridad ya está contratada en NEX.

#### Y «lo que puede usar legalmente» no es una lista cerrada

Aunque se consiga el catálogo, conviene no confundir dos cosas: la ficha del vehículo recoge **las medidas con las que se homologó**, pero la normativa admite montar otras equivalentes bajo condiciones de diámetro exterior, índice de carga y código de velocidad. El propio GIAVEH tiene un módulo de **Equivalencias** como trámite específico. Para el negocio esto importa en la dirección incómoda: **el conjunto de medidas legalmente montables sobre un vehículo es mayor que el que aparece en su ficha**, así que un agregado construido sólo con la medida de homologación subestima la variedad real de la demanda.
