<!--
Repositorio abierto el 2026-08-31. Esta primera pasada es sólo reconocimiento y documentación de la fuente: no hay código todavía, y así se dice en el cuerpo para que nadie lo busque.
Pendiente de decidir con Víctor: la licencia del repositorio y el idioma de la documentación (hoy en español; si el repositorio va a tener audiencia internacional habrá que decidir si se traduce o se duplica).
-->

# Microdatos de matriculaciones y bajas de vehículos en España

Descarga, documentación y carga en PostgreSQL de los **microdatos de matriculaciones y de bajas de vehículos** que publica en abierto la [Dirección General de Tráfico](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Matriculaciones-de-Vehiculos-diarios/): un registro por trámite, con la ficha técnica del vehículo y el municipio de domicilio del titular, desde diciembre de 2014 y con actualización diaria.

El objetivo es construir con ellos **agregados de parque móvil y de ciclo de vida del vehículo**, con el máximo detalle geográfico y técnico que la fuente permita.

Este repositorio **no contiene datos**. Contiene lo necesario para conseguirlos y entenderlos.

## Estado

**Reconocimiento y documentación de la fuente, con el alcance ya decidido.** La ETL todavía no está escrita; lo que hay documentado es qué publica la DGT, cómo son los ficheros, qué se puede y qué no se puede hacer con ellos, y qué se va a cargar.

## Documentación

| Documento | Qué contiene |
|---|---|
| [doc/alcance.md](doc/alcance.md) | Qué se carga y qué no, decidido el 2026-08-31, y las tres tensiones que hay que resolver antes de dar por buenos los agregados |
| [doc/fuente.md](doc/fuente.md) | Qué publica la DGT, patrones de URL, cadencia, volúmenes medidos, qué contiene realmente el fichero y sus limitaciones |
| [doc/diseno-de-registro.md](doc/diseno-de-registro.md) | Los 69 campos con longitud, posición de inicio y fin, tipo y descripción, y la comprobación del troceado contra un fichero real |
| [doc/record-layout.tsv](doc/record-layout.tsv) | Lo mismo en formato manejable por un programa: es la fuente del troceado, no una copia |
| [doc/tablas-de-codigos.md](doc/tablas-de-codigos.md) | El Anexo I completo: clase de matrícula, procedencia, servicio, tipo de vehículo, propulsión, provincias, trámite, baja definitiva y categoría de vehículo eléctrico |

## Lo esencial en cinco líneas

- Ficheros de **texto de ancho fijo, 714 bytes por línea, ISO-8859-1, 69 campos**, en ZIP, uno por día y uno por mes.
- **Matriculaciones y bajas comparten el mismo diseño de registro**, campo a campo, así que el mismo troceado sirve para los dos.
- El histórico de matriculaciones son **139 meses (2014-12 en adelante), ≈ 1,8 GB comprimidos, ≈ 20 millones de registros** (medido el 2026-08-31); el de bajas arranca el mismo mes.
- Llega a **municipio y código postal**, que es lo que lo hace valioso frente a las estadísticas agregadas.
- **No trae identificador de vehículo utilizable** —el bastidor viene truncado desde el 1 de febrero de 2025— ni identificación del titular: son ficheros de **eventos**, no un censo del parque, y un alta no se puede casar con su baja.

## Origen y condiciones de uso

Los datos son de la **Dirección General de Tráfico (Ministerio del Interior)** y se publican en su portal de datos abiertos. Este repositorio sólo automatiza su descarga y carga; cualquier uso de los datos queda sujeto a las condiciones que fije la DGT en su portal.
