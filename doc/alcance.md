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
- Y sobre todo el **TVV** —`TIPO_ITV`, `VARIANTE_ITV`, `VERSION_ITV`— junto con `CONTRASENA_HOMOLOGACION_ITV`, que es la clave de la homologación europea del vehículo. Es el identificador por el que una ficha técnica completa **se podría** cruzar con un catálogo de equipamiento original.

O sea que la medida del neumático **no sale de esta fuente**: sale de cruzar el TVV con otro catálogo que haya que conseguir aparte. Conviene saberlo antes de prometer nada, y conviene medir cuánta cobertura tiene el TVV en el histórico, porque son campos que la DGT fue añadiendo y en los primeros años pueden venir vacíos.
