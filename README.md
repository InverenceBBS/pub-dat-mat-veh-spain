<!--
Repositorio abierto el 2026-08-31 con el reconocimiento de la fuente. El 2026-09-01 se diseñó la base y se midió la fase 0; el 2026-09-02 quedó cargado el histórico completo y automatizada la actualización, y el estado del cuerpo se actualizó entonces.
Pendiente de decidir con Víctor: la licencia del repositorio y el idioma de la documentación (hoy en español; si el repositorio va a tener audiencia internacional habrá que decidir si se traduce o se duplica).
-->

# Microdatos de matriculaciones y bajas de vehículos en España

Descarga, documentación y carga en PostgreSQL de los **microdatos de matriculaciones y de bajas de vehículos** que publica en abierto la [Dirección General de Tráfico](https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/dgt-en-cifras-detalle/Microdatos-de-Matriculaciones-de-Vehiculos-diarios/): un registro por trámite, con la ficha técnica del vehículo y el municipio de domicilio del titular, desde diciembre de 2014 y con actualización diaria.

El objetivo es construir con ellos **agregados de parque móvil y de ciclo de vida del vehículo**, con el máximo detalle geográfico y técnico que la fuente permita.

Este repositorio **no contiene datos**. Contiene lo necesario para conseguirlos y entenderlos.

## Estado

**En producción.** El histórico completo está cargado —19.750.700 altas y 22.837.685 bajas, de 2014-12 a 2026-08— y una tarea horaria descarga, carga y clasifica lo que la DGT publica, sin intervención. Documentado: qué publica la DGT, cómo son los ficheros, qué se puede y qué no se puede hacer con ellos, qué se carga, el diseño de la base, las mediciones que ese diseño necesitaba y cómo se opera. El código está en [etl/](etl/) y [schema/](schema/); los guiones de medición, que no tocan ninguna base de datos, en [phase0/](phase0/).

## Documentación

| Documento | Qué contiene |
|---|---|
| [doc/alcance.md](doc/alcance.md) | Qué se carga y qué no, decidido el 2026-08-31, y las tres tensiones que hay que resolver antes de dar por buenos los agregados |
| [doc/fuente.md](doc/fuente.md) | Qué publica la DGT, patrones de URL, cadencia, volúmenes medidos, qué contiene realmente el fichero y sus limitaciones |
| [doc/diseno-de-registro.md](doc/diseno-de-registro.md) | Los 69 campos con longitud, posición de inicio y fin, tipo y descripción, y la comprobación del troceado contra un fichero real |
| [doc/record-layout.tsv](doc/record-layout.tsv) | Lo mismo en formato manejable por un programa: es la fuente del troceado, no una copia |
| [doc/tablas-de-codigos.md](doc/tablas-de-codigos.md) | El Anexo I completo: clase de matrícula, procedencia, servicio, tipo de vehículo, propulsión, provincias, trámite, baja definitiva y categoría de vehículo eléctrico |
| [doc/diseno-de-base-de-datos-y-etl.md](doc/diseno-de-base-de-datos-y-etl.md) | El esquema `spain` tabla por tabla, el destino de cada uno de los 69 campos, el particionado por mes, los seis pasos de la carga y lo que hay que medir antes de fijar el DDL |
| [doc/fase0-resultados.md](doc/fase0-resultados.md) | Las diez mediciones sobre ficheros reales que había que hacer antes de fijar el esquema, con los cinco hallazgos que lo cambian |
| [doc/operacion.md](doc/operacion.md) | Qué está corriendo, dónde, con qué credenciales, y las recetas para recargar un mes, cambiar las clases de tamaño o averiguar por qué algo ha fallado |
| [doc/estadisticas.md](doc/estadisticas.md) | Las series mensuales de once años, con gráficos: entradas y salidas del parque, turismos por tamaño —el pequeño se hunde y el grande se multiplica—, propulsión y edad a la baja |

## Lo esencial en cinco líneas

- Ficheros de **texto de ancho fijo, 714 bytes por línea, ISO-8859-1, 69 campos**, en ZIP, uno por día y uno por mes.
- **Matriculaciones y bajas comparten el mismo diseño de registro**, campo a campo, así que el mismo troceado sirve para los dos.
- El histórico de matriculaciones son **139 meses (2014-12 en adelante), ≈ 1,8 GB comprimidos, ≈ 20 millones de registros** (medido el 2026-08-31); el de bajas arranca el mismo mes.
- Llega a **municipio y código postal**, que es lo que lo hace valioso frente a las estadísticas agregadas.
- **No trae identificador de vehículo utilizable** —el bastidor viene truncado desde el 1 de febrero de 2025— ni identificación del titular: son ficheros de **eventos**, no un censo del parque, y un alta no se puede casar con su baja.

## Origen y condiciones de uso

Los datos son de la **Dirección General de Tráfico (Ministerio del Interior)** y se publican en su portal de datos abiertos. Este repositorio sólo automatiza su descarga y carga; cualquier uso de los datos queda sujeto a las condiciones que fije la DGT en su portal.
