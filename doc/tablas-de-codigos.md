<!--
Documento abierto el 2026-08-31. Transcripción literal del Anexo I del PDF oficial (MATRICULACIONES_MATRABA.pdf, págs. 8-20), sin añadir ni interpretar nada.
Está separado de diseno-de-registro.md porque es largo y porque su destino natural es acabar siendo tablas de catálogo en la base de datos: cuando se codifique la ETL, estas tablas se cargan desde aquí, no se reescriben a mano en el DDL.
Lo que se sabe que le falta al Anexo I está anotado en el cuerpo, en «Lo que el Anexo I no cubre», porque eso sí lo necesita quien lea los datos.
-->

# Tablas de códigos (Anexo I)

Transcripción del Anexo I del [Documento de interfaz de Envío de Datos (Matriculaciones)](https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/matraba/MATRICULACIONES_MATRABA.pdf), páginas 8 a 20. Los campos que las usan están en [diseno-de-registro.md](diseno-de-registro.md).

## COD_CLASE_MAT — clase de matrícula

| Código | Descripción |
|---|---|
| 0 | Ordinaria |
| 1 | Turística |
| 2 | Remolque |
| 3 | Diplomática |
| 4 | Reservada |
| 5 | Vehículo especial |
| 6 | Ciclomotor |
| 7 | Transporte Temporal |
| 8 | Histórica |

## COD_PROCEDENCIA — procedencia de los datos de filiación

| Código | Descripción |
|---|---|
| 0, blanco o nulo | Fabricación Nacional |
| 1 | Importación no comunitaria |
| 2 | Subasta |
| 3 | Importación U.E |

## COD_SERVICIO — código de servicio antiguo

| Código | Descripción |
|---|---|
| 0 | Particular |
| 1 | Público |
| 2 | Auto Taxi |
| 3 | Alquiler con conductor |
| 4 | Alquiler sin conductor |
| 5 | Escuela de conductores |
| 6 | Agrícola |
| 7 | Obras y servicios |
| 8 | Transporte escolar |
| 9 | Mercancías peligrosas |

## SERVICIO — código de servicio, versión nueva

Es el campo 29 del registro. El anterior, `COD_SERVICIO`, no aparece como campo en la Tabla 1.

| Código | Descripción |
|---|---|
| A00 | Público PUBL-Sin especificar |
| A01 | Público PUBL-Alquiler sin conductor |
| A02 | Público PUBL-Alquiler con conductor |
| A03 | Público PUBL-Aprendizaje de conducción |
| A04 | Público PUBL-Taxi |
| A05 | Público PUBL-Auxilio en carretera |
| A07 | Público PUBL-Ambulancia |
| A08 | Público PUBL-Funerario |
| A09 | Particular PART-Obras |
| A10 | Público PUBL-Mercancías peligrosas |
| A11 | Público PUBL-Basurero |
| A12 | Público PUBL-Transporte escolar |
| A13 | Público PUBL-Policía |
| A14 | Público PUBL-Bomberos |
| A15 | Público PUBL-Protección civil y salvamento |
| A16 | Público PUBL-Defensa |
| A18 | Público PUBL-Actividad económica |
| A20 | Público PUBL-Mercancías perecederas |
| B00 | Particular PART-Sin especificar |
| B06 | Particular PART-Agrícola |
| B07 | ParticularPART- |
| B09 | Particular PART-Obras |
| B17 | Particular PART-Vivienda |
| B18 | Público PART-Actividad económica |
| B19 | Particular PART-Recreativo |
| B21 | Particular PART-Vehículo para ferias |

## COD_PROPULSION — tipo de propulsión

| Código | Descripción |
|---|---|
| 0 | Gasolina |
| 1 | Diesel |
| 2 | Eléctrico |
| 3 | Otros |
| 4 | Butano |
| 5 | Solar |
| 6 | Gas Licuado de Petróleo |
| 7 | Gas Natural Comprimido |
| 8 | Gas Natural Licuado |
| 9 | Hidrógeno |
| A | Biometano |
| B | Etanol |
| C | Biodiesel |

## CLAVE_TRAMITE — código del trámite

| Código | Descripción |
|---|---|
| 1 | Matriculación ordinaria y de ciclomotores |
| 2 | Transferencia |
| 3 | Baja definitiva (excluidos Plan Renove, Baja por exportación y Tránsito comunitario) |
| 4 | Baja definitiva por Plan Renove |
| 5 | Rematriculación |
| 6 | Baja temporal |
| 7 | Baja definitiva por Exportación y por Tránsito comunitario |
| 8 | Matriculación vehículo especial |
| 9 | Matriculación temporal |
| A | Prorroga matricula temporal |
| B | Paso de matrícula temporal a definitiva |

## IND_BAJA_DEF — motivo de la baja definitiva

| Código | Descripción |
|---|---|
| 0 | Desguace |
| 1 | Agotamiento |
| 2 | Antigüedad |
| 3 | Renovación del parque |
| 4 | Otros motivos |
| 5 | R.D.L 4/1994 , R.D.L 10/1994 , R.D.L 4/1997 |
| 7 | Voluntaria |
| 8 | Exportación |
| 9 | Transito comunitario |
| A | De oficio por abandono |
| B | De oficio por seguridad |
| C | Por Tratamiento Residual |

## CATEGORÍA_VEHÍCULO_ELÉCTRICO

| Código | Descripción |
|---|---|
| PHEV | Eléctrico Enchufable |
| REEV | Eléctrico de Autonomía Extendida |
| HEV | Eléctrico Híbrido |
| BEV | Eléctrico de Batería |

## COD_TIPO — tipo de vehículo

| Código | Descripción |
|---|---|
| blanco, nulo o 0 | SIN ESPECIFICAR |
| 00 | CAMIÓN |
| 01 | CAMIÓN PLATAFORMA |
| 02 | CAMIÓN CAJA |
| 03 | CAMIÓN FURGÓN |
| 04 | CAMIÓN BOTELLERO |
| 05 | CAMIÓN CISTERNA |
| 06 | CAMIÓN JAULA |
| 07 | CAMIÓN FRIGORÍFICO |
| 08 | CAMIÓN TALLER |
| 09 | CAMIÓN PARA CANTERA |
| 0A | CAMIÓN PORTAVEHÍCULOS |
| 0B | CAMIÓN MIXTO |
| 0C | CAMIÓN PORTACONTENEDORES |
| 0D | CAMIÓN BASURERO |
| 0E | CAMIÓN ISOTERMO |
| 0F | CAMIÓN SILO |
| 0G | VEHICULO MIXTO ADAPTABLE |
| 10 | CAMIÓN ARTICULADO |
| 11 | CAMIÓN ARTICULADO PLATAFORMA |
| 12 | CAMIÓN ARTICULADO CAJA |
| 13 | CAMIÓN ARTICULADO FURGÓN |
| 14 | CAMIÓN ARTICULADO BOTELLERO |
| 15 | CAMIÓN ARTICULADO CISTERNA |
| 16 | CAMIÓN ARTICULADO JAULA |
| 17 | CAMIÓN ARTICULADO FRIGORÍFICO |
| 18 | CAMIÓN ARTICULADO TALLER |
| 19 | CAMIÓN ARTICULADO PARA CANTERA |
| 1A | CAMIÓN ARTICULADO VIVIENDA O CARAVANA |
| 1C | CAMIÓN ARTICULADO HORMIGONERA |
| 1D | CAMIÓN ARTICULADO VOLQUETE |
| 1E | CAMIÓN ARTICULADO GRÚA |
| 1F | CAMIÓN ARTICULADO CONTRA INCENDIOS |
| 20 | FURGONETA |
| 21 | FURGONETA MIXTA |
| 22 | AMBULANCIA |
| 23 | COCHE FÚNEBRE |
| 24 | CAMIONETA |
| 25 | TODO TERRENO |
| 30 | AUTOBÚS |
| 31 | AUTOBÚS ARTICULADO |
| 32 | AUTOBÚS MIXTO |
| 33 | BIBLIOBÚS |
| 34 | AUTOBÚS LABORATORIO |
| 35 | AUTOBÚS TALLER |
| 36 | AUTOBÚS SANITARIO |
| 40 | TURISMO |
| 50 | MOTOCICLETA DE 2 RUEDAS SIN SIDECAR |
| 51 | MOTOCICLETA CON SIDECAR |
| 52 | MOTOCARRO |
| 53 | AUTOMÓVIL DE 3 RUEDAS |
| 54 | CUATRICICLO PESADO |
| 60 | COCHE DE INVÁLIDO |
| 70 | VEHÍCULO ESPECIAL |
| 71 | PALA CARGADORA |
| 72 | PALA EXCAVADORA |
| 73 | CARRETILLA ELEVADORA |
| 74 | MONIVELADORA |
| 75 | COMPACTADORA |
| 76 | APISONADORA |
| 77 | GIROGRAVILLADORA |
| 78 | MACHACADORA |
| 79 | QUITANIEVES |
| 7A | VIVIENDA |
| 7B | BARREDORA |
| 7C | HORMIGONERA |
| 7D | VOLQUETE DE CANTERAS |
| 7E | GRÚA |
| 7F | SERVICIO CONTRA INCENDIOS |
| 7G | ASPIRADORA DE FANGOS |
| 7H | MOTOCULTOR |
| 7I | MAQUINARIA AGRÍCOLA AUTOMOTRIZ |
| 7J | PALA CARGADORA-RETROEXCAVADORA |
| 7K | TREN HASTA 160 PLAZAS |
| 80 | TRACTOR |
| 81 | TRACTOCAMIÓN |
| 82 | TRACTOCARRO |
| 90 | CICLOMOTOR DE 2 RUEDAS |
| 91 | CICLOMOTOR DE 3 RUEDAS |
| 92 | CUATRICICLO LIGERO |
| EX | EXTRANJERO |
| R0 | REMOLQUE |
| R1 | REMOLQUE PLATAFORMA |
| R2 | REMOLQUE CAJA |
| R3 | REMOLQUE FURGÓN |
| R4 | REMOLQUE BOTELLERO |
| R5 | REMOLQUE CISTERNA |
| R6 | REMOLQUE JAULA |
| R7 | REMOLQUE FRIGORÍFICO |
| R8 | REMOLQUE TALLER |
| R9 | REMOLQUE PARA CANTERAS |
| RA | REMOLQUE VIVIENDA O CARAVANA |
| RB | REMOLQUE DE VIAJEROS O DE AUTOBÚS |
| RC | REMOLQUE HORMIGONERA |
| RD | REMOLQUE VOLQUETE DE CANTERA |
| RE | REMOLQUE DE GRÚA |
| RF | REMOLQUE CONTRA INCENDIOS |
| RH | MAQ.AGRÍCOLA ARRASTRADA DE 2 EJES |
| S0 | SEMIRREMOLQUE |
| S1 | SEMIRREMOLQUE PLATAFORMA |
| S2 | SEMIRREMOLQUE CAJA |
| S3 | SEMIRREMOLQUE FURGÓN |
| S4 | SEMIRREMOLQUE BOTELLERO |
| S5 | SEMIRREMOLQUE CISTERNA |
| S6 | SEMIRREMOLQUE JAULA |
| S7 | SEMIRREMOLQUE FRIGORÍFICO |
| S8 | SEMIRREMOLQUE TALLER |
| S9 | SEMIRREMOLQUE CANTERA |
| SA | SEMIRREMOLQUE VIVIENDA O CARAVANA |
| SB | SEMIRREMOLQUE VIAJEROS O AUTOBÚS |
| SC | SEMIRREMOLQUE HORMIGONERA |
| SD | SEMIRREMOLQUE VOLQUETE DE CANTERA |
| SE | SEMIRREMOLQUE GRÚA |
| SF | SEMIRREMOLQUE CONTRA INCENDIOS |
| SH | MAQ.AGRICOLA ARRASTRADA DE 1 EJE |

## COD_PROVINCIA_VEH y COD_PROVINCIA_MAT — provincias

Son las siglas del antiguo sistema de matrículas provinciales, no el código INE de dos dígitos. Las dos listas son la misma salvo dos diferencias: `COD_PROVINCIA_VEH` no incluye `SC` (Servicios Centrales) y `COD_PROVINCIA_MAT` sí.

| Código | Provincia |
|---|---|
| A | Alicante/Alacant |
| AB | Albacete |
| AL | Almería |
| AV | Ávila |
| B | Barcelona |
| BA | Badajoz |
| BI | Bizkaia |
| BU | Burgos |
| C | Coruña (A) |
| CA | Cádiz |
| CC | Cáceres |
| CE | Ceuta |
| CO | Córdoba |
| CR | Ciudad Real |
| CS | Castellón/Castelló |
| CU | Cuenca |
| DS | Desconocido |
| EX | Extranjero |
| GC | Palmas (Las) |
| GI | Girona |
| GR | Granada |
| GU | Guadalajara |
| H | Huelva |
| HU | Huesca |
| IB | Balears (Illes) |
| J | Jaén |
| L | Lleida |
| LE | León |
| LO | Rioja (La) |
| LU | Lugo |
| M | Madrid |
| MA | Málaga |
| ML | Melilla |
| MU | Murcia |
| NA | Navarra |
| O | Asturias |
| OU | Ourense |
| P | Palencia |
| PO | Pontevedra |
| S | Cantabria |
| SA | Salamanca |
| SC | Servicios Centrales (sólo en `COD_PROVINCIA_MAT`) |
| SE | Sevilla |
| SG | Segovia |
| SO | Soria |
| SS | Gipuzkoa |
| T | Tarragona |
| TE | Teruel |
| TF | Santa Cruz de Tenerife |
| TO | Toledo |
| V | Valencia/València |
| VA | Valladolid |
| VI | Araba/Álava |
| Z | Zaragoza |
| ZA | Zamora |

## Lo que el Anexo I no cubre

Hay campos codificados cuyo diccionario **no viene** en el documento oficial, y que habrá que reconstruir a partir de los propios datos o de otra fuente:

- `CATEGORIA_HOMOLOGACION_EUROPEA_ITV` (M1, N1, L3e…), `CARROCERIA` y `CLASIFICACION_REGLAMENTO_VEHICULOS_ITV` (Anexo II del RD 2822/1998, que el PDF cita pero no reproduce).
- `NIVEL_EMISIONES_EURO_ITV`, cuyos valores literales no están tabulados.
- `CODIGO_ITV`.
