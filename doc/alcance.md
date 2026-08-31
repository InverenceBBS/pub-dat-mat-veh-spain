<!--
Documento abierto el 2026-08-31, el mismo día que el repositorio, en cuanto Víctor cerró las cuatro decisiones que quedaban abiertas en fuente.md.
Existe para que el alcance esté escrito antes que el código y no se vaya reinterpretando cada vez que alguien toca la ETL. Sus decisiones van citadas literalmente y marcadas como suyas; lo que viene detrás de cada una es análisis nuestro y puede estar equivocado.
Las tensiones del final no son objeciones: son puntos donde lo pedido y lo que hace falta para conseguirlo no coinciden del todo, y donde alguien tendrá que decidir. Se dejan escritas porque si no se olvidan.
-->

# Alcance

## Las decisiones

Dictadas por Víctor de Buen el 2026-08-31, en respuesta a las cuatro decisiones que quedaban abiertas en [fuente.md](fuente.md):

***NOTA VBR***: *Todo el histórico de matriculaciones de vehículos nuevos de cualquier tipo al máximo nivel geográfico. Las bajas también son muy interesantes aunque no se puedan casar. Queremos formar agregados de parque móvil y ciclo de vida con mucho detalle. No nos interesa el titular para nada pero sí la ficha técnica porque afecta al tipo de neumáticos que necesitará. El mensual sustituye a los diarios sin contemplaciones.*

De ahí se derivan cinco cosas:

| Decisión | Qué significa en la práctica |
|---|---|
| **Todo el histórico** | Los 139 meses publicados, desde 2014-12. No se recorta por antigüedad. |
| **De cualquier tipo** | No se filtra por `COD_TIPO` ni por `COD_CLASE_MAT`: entran turismos, furgonetas, camiones, autobuses, motocicletas, ciclomotores, remolques, semirremolques y vehículos especiales. |
| **Al máximo nivel geográfico** | Se conservan `COD_MUNICIPIO_INE_VEH`, `MUNICIPIO`, `LOCALIDAD_VEHICULO` y `CODIGO_POSTAL`, además de las dos provincias. El código postal es el grano más fino que da la fuente. |
| **Las bajas también** | Entra una segunda fuente, el fichero de bajas, con su propio histórico. Ver [fuente.md](fuente.md#las-otras-fuentes-de-la-dgt). |
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

Tres puntos donde lo pedido y lo que hace falta para conseguirlo no coinciden del todo. No son objeciones al alcance: son avisos de que hay una decisión escondida.

### 1. «Vehículos nuevos» y «parque móvil» tiran en direcciones opuestas

`IND_NUEVO_USADO` vale `N` o `U`, y en la muestra del 2026-08-28 hay **9.630 nuevos y 856 usados**: un **8,1%** de las altas son vehículos usados, casi todos importaciones. Ese 8,1% **entra en el parque español** exactamente igual que un vehículo nuevo, y sus neumáticos se desgastan igual. Si el objetivo fuera sólo el mercado de vehículo nuevo, se filtra por `N`; si el objetivo es el parque y su ciclo de vida, filtrar por `N` deja fuera vehículos que están rodando.

La salida que no obliga a elegir: **cargar el fichero íntegro y filtrar en la capa de agregados**, con `IND_NUEVO_USADO` como dimensión y no como filtro de carga. Así conviven una serie de matriculaciones de nuevos y un parque que incluye las importaciones de usados, sin volver a descargar nada. Es lo que se hace salvo instrucción contraria.

Y hay un aviso sobre el propio campo: el documento de la DGT dice que `IND_NUEVO_USADO` **«se calcula en el almacén de datos»**, no que venga del trámite. Un campo calculado por el emisor puede haber cambiado de criterio a lo largo de once años; conviene vigilar su serie temporal antes de fiarse de un salto.

### 2. «El titular no interesa», pero el régimen de uso sí debería

`RENTING` y `SERVICIO` **no son datos del titular**: dicen cómo se usa el vehículo. Y para lo que se persigue —desgaste y reposición de neumáticos— son de los campos más informativos del registro: un vehículo de renting o un taxi (`SERVICIO` = `A04`) recorre en un año lo que un particular en cuatro, y cambia neumáticos en esa proporción. Lo mismo `A01`/`A02` (alquiler), `A03` (autoescuela) o `B06` (agrícola).

Se conservan y se modelan como dimensión. Si la intención era descartarlos también, hay que decirlo, porque entonces el ciclo de vida pierde su variable más explicativa.

### 3. La ficha técnica no llega hasta el neumático

Esto es lo importante de las tres. **El registro no trae la medida del neumático**, ni la llanta, ni el índice de carga o velocidad. Lo que trae y sirve para acercarse:

- `CATEGORIA_HOMOLOGACION_EUROPEA_ITV` (M1, N1, L3e…), `CARROCERIA`, `CLASIFICACION_REGLAMENTO_VEHICULOS_ITV`.
- `MASA_MAXIMA_TECNICA_ADMISIBLE_ITV` y `MASA_ORDEN_MARCHA_ITV`, `TARA` y `PESO_MAX`: la carga por eje acota el índice de carga.
- `DISTANCIA_EJES_12_ITV`, `VIA_ANTERIOR_ITV` y `VIA_POSTERIOR_ITV`, en milímetros: geometría del vehículo.
- `KW_ITV` y `POTENCIA_ITV`: acotan el índice de velocidad.

La medida del neumático hay que traerla, entonces, de otro catálogo, cruzando por lo que sí identifica la homologación del vehículo. Y ahí lo que hay medido cambia cuál es la clave de cruce.

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
