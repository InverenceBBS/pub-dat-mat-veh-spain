<!--
Documento abierto el 2026-09-02, cuando la base dejó de ser un diseño y empezó a cargarse sola cada hora.
Existe porque el diseño explica POR QUÉ está hecho así y este explica QUÉ está corriendo, dónde y qué hacer cuando algo falle. Son dos preguntas distintas y quien viene a la segunda no quiere leer la primera.
Todas las cifras están medidas el 2026-09-02 sobre la carga real, y van fechadas en el cuerpo porque envejecen: el histórico crece un mes cada mes.
Lo que NO va aquí: contraseñas, ni el contenido del fichero de contraseñas. Sólo dónde tiene que estar y qué línea lleva.
-->

# Operación

Qué está corriendo, dónde, y qué hacer cuando falle. El **por qué** de cada decisión está en [diseno-de-base-de-datos-y-etl.md](diseno-de-base-de-datos-y-etl.md); lo que se midió antes de construirlo, en [fase0-resultados.md](fase0-resultados.md).

## Dónde vive cada cosa

| Qué | Dónde |
|---|---|
| La base de datos | `matveh`, esquema `spain`, en **45.159.223.206** (`llull-env-data-master-grid-III`) |
| El código | `/home/devel/matveh/` en ese servidor, copia de este repositorio |
| Los ficheros de la DGT | `/data/matveh/raw/`, con `manifest.tsv` — huella, tamaño, `ETag` y `Last-Modified` de cada uno |
| La traza de cada hora | `/home/devel/matveh-hourly.log` |
| La vigilancia del horario de publicación | `/home/devel/matveh-horario.log` |

Los ZIP **no se borran**: son lo único que no se puede reconstruir si la DGT retira o reescribe un fichero, y recuperar un campo que hoy no se carga es recargar desde ahí sin volver a pedir nada.

## Qué corre solo

Dos líneas en el `crontab` del usuario `devel`, y **ninguna necesita privilegios**:

```
7 * * * * /bin/bash /home/devel/matveh/etl/hourly.sh >> /home/devel/matveh-hourly.log 2>&1
30 7 * * 1 /usr/bin/python3 /home/devel/matveh/phase0/publication-hours.py --watch >> /home/devel/matveh-horario.log 2>&1
```

**Cada hora**, [etl/hourly.sh](../etl/hourly.sh) hace el circuito completo: pregunta por `HEAD` —ocho peticiones de cabecera, cero bytes de cuerpo—, descarga lo que sea nuevo o haya cambiado de `ETag`, lo carga y clasifica las fichas que hayan entrado. Si no hay nada, no hace nada y lo dice.

Por qué cada hora y no a una hora fija: **la DGT no publica ningún horario**. Medido, el diario del día D aparece a las 06:30 UTC del día D+1, y a veces a las 13:00, pero nada lo garantiza ([fuente.md](fuente.md#cuándo-se-publica-cada-diario)). Preguntando cada hora, la hora deja de importar. Y de paso se detecta algo que una descarga diaria no vería nunca: **un fichero que la DGT reescriba** después de que nos lo lleváramos.

**Los lunes** se recalcula la tabla de horas de publicación semana a semana. No sirve para no perder ficheros —de eso se encarga el `--check 4`, que aguanta cuatro días de retraso— sino para enterarse si la DGT cambia de costumbre.

## Qué hay cargado (medido el 2026-09-02)

| | Filas |
|---|---:|
| `registration`, 141 meses desde 2014-12 | **19.750.700** |
| `deregistration`, los mismos 141 meses | **22.837.685** |
| `vehicle_spec` | 6.464.912 |
| `place` | 250.121 |
| `municipality` | 8.181 |

Y una cosa que conviene saber antes de dimensionar cualquier cosa: **`vehicle_spec` ocupa 4 GB, más que todas las particiones de eventos juntas**. Es la consecuencia directa del hallazgo 1 de la fase 0 —la ficha técnica no satura—, y la partida más gorda son los textos finos: variante, versión y fabricante. Si algún día aprieta, ahí está el margen.

## Las credenciales, y por qué la carga no necesita `sudo`

**La ETL corre como `archive_rw`** y lee su contraseña del fichero de contraseñas de quien la lanza, con la base en comodín:

```
*:*:*:archive_rw:<la contraseña>
```

En el servidor, ese fichero es `/home/devel/.pgpass` y tiene que estar en modo `600` o libpq lo ignora sin decir nada. **Una línea por rol, nunca por base**: la contraseña es del rol y vale para todo el clúster, así que una línea por base guardaría el mismo secreto varias veces y una rotación dejaría obsoletas todas menos una.

Lo único que necesita privilegio es **crear o modificar el esquema**, que es cosa del propietario `model_archive` y se hace a mano. Que la carga no lo necesite no es un detalle de comodidad: **un proceso que pide `sudo` no se puede poner en un cron sin abrir un agujero**, y por eso las dos operaciones que sí requieren ser dueño —crear la partición de un mes y vaciarla— están encapsuladas en dos funciones `SECURITY DEFINER`, `spain.ensure_partition` y `spain.reset_partition`, en lugar de repartir permisos.

## Recetas

**Ver si va todo bien:**

```
tail -30 /home/devel/matveh-hourly.log
```

**Lanzar el circuito a mano**, sin esperar a la hora:

```
bash /home/devel/matveh/etl/hourly.sh
```

**Recargar un mes concreto** —porque la DGT lo reprocesó, o porque cambió el troceado—:

```
bash /home/devel/matveh/etl/run-load.sh /data/matveh/raw/export_mensual_mat_202607.zip
```

Es idempotente: reemplaza la partición de ese mes y vuelve a insertarla. Un fichero diario, en cambio, borra sus filas por fecha de proceso, que está medido que coincide exactamente con el día del fichero.

**Cargar todo lo que esté descargado y no en la base:**

```
bash /home/devel/matveh/etl/run-load.sh --pending
```

**Pasar las comprobaciones** —las mismas cifras que la fase 0 midió sin base de datos, así que una diferencia es un error de carga, no una opinión—:

```
psql -h 127.0.0.1 -U archive_rw -d matveh -f /home/devel/matveh/schema/checks.sql
```

**Cambiar las clases de tamaño**, que es lo que va a cambiar: se editan las reglas de [schema/02-size-rules.sql](../schema/02-size-rules.sql) y se ejecuta el fichero, que reclasifica al terminar. Necesita al propietario, y no toca ni una fila de eventos:

```
sudo -u postgres psql -v ON_ERROR_STOP=1 -d matveh -f /home/devel/matveh/schema/02-size-rules.sql
```

**Descargar el histórico entero de nuevo** —no hace falta salvo desastre; los que ya están se saltan por huella—:

```
python3 /home/devel/matveh/etl/download.py --history
```

**Actualizar el código en el servidor**, desde la máquina de trabajo:

```
rsync -a --exclude .git /devel/pub-dat-mat-veh-spain/ llull-env-data-master-grid-III:/home/devel/matveh/
```

## Cuando algo falla

**Un `404` no siempre es un problema.** Son normales y esperados: el diario del día en curso hasta que la DGT lo publica, **el de matriculaciones de un sábado o un domingo** —las bajas sí se publican a diario y las matriculaciones no—, y el mensual del mes que aún no ha cerrado.

**Un código que no está en el Anexo I no rompe la carga**: se da de alta con la descripción «no documentado en el Anexo I» y queda marcado. Han aparecido veinte en once años, entre ellos `ñ` y `Ñ` como propulsión y `PÚB` como servicio. Se listan con la comprobación 6 de `checks.sql`.

**Una línea de longitud distinta de 714 sí aborta**, y a propósito: significa que el diseño de registro ha cambiado. La única excepción admitida son las líneas de 707 caracteres con `FEC_PROCESO` a `?`, que existen —dos, en 2014-12— y se cargan con la fecha de proceso nula.

**Si la carga se para a mitad**, no deja nada a medias: cada fichero va en una sola transacción. Basta relanzar con `--pending`, que continúa por donde iba.

**Si aparece un error de permisos**, es que a la ETL le falta algo que debería tener; no se arregla lanzándola como `postgres`, porque entonces deja de poder ir en el cron. Los privilegios que necesita están en [schema/01-spain-schema.sql](../schema/01-spain-schema.sql) y en las migraciones de [schema/migrations/](../schema/migrations/).

## Lo que no está automatizado, y a propósito

- **Las copias de seguridad no existen.** Ni de esta base ni del servidor; está escrito en el capítulo 5 de [ARCHIVO-DE-MODELOS.es.md](/devel/ModelPassport/docs/ARCHIVO-DE-MODELOS.es.md) del otro proyecto, que comparte máquina. Lo que sí se puede reconstruir entero desde los ZIP es todo el contenido de `spain`: la base no guarda nada que no esté en `/data/matveh/raw`.
- **El esquema no se migra solo.** Un cambio de tablas o de funciones se escribe en `schema/migrations/` y se ejecuta a mano, como propietario.
- **La medición 8 de la fase 0 sigue pendiente**: comparar el mensual de agosto de 2026 con la suma de sus 22 diarios, que están guardados a propósito. Se podrá hacer en cuanto la DGT publique ese mensual, hacia el 15 de septiembre.
