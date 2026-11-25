# Diccionario de variables · Artículo II

Archivo: `datos_procesados/datos_procesados_2024200495A.csv` · 1 800 filas (15 bancos × 120 meses) · 53 columnas.
Llave: **entidad + fecha**. Frecuencia: **mensual**. Los montos están en **millones de soles corrientes**, salvo que se indique otra unidad.

En las URL de la SBS, `{año}` es el año, `{Mes}` el nombre del mes y `{mm}` sus dos primeras letras (p. ej. `.../2016/Enero/B-2201-en2016.XLS`). La página de cada reporte es `https://www.sbs.gob.pe/app/stats_net/stats/EstadisticaSistemaFinancieroResultados.aspx?c={reporte}`.
URL de los archivos: `https://intranet2.sbs.gob.pe/estadistica/financiera/{año}/{Mes}/{reporte}-{mm}{año}.XLS`.
Endpoint del BCRP: `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{código}/json/2010-1/2025-12/esp`.

## Llave

| Variable | Descripción | Unidad | Fuente | Rango |
|---|---|---|---|---|
| `entidad` | Banco, con nombre armonizado (ver incidencia 10) | texto | SBS | 15 bancos |
| `fecha`, `anio`, `mes` | Mes de la observación | AAAA-MM | — | 2016-01 a 2025-12 |

## Balance y crédito (SBS, B-2201 · Vía 2)

| Variable | Descripción | Unidad | Rango |
|---|---|---|---|
| `activo_total`, `pasivo_total`, `patrimonio` | Total activo, total pasivo y patrimonio contable | mill. S/ | activo: 353,87 – 202 161,92 |
| `activo_real` | Activo / (IPC de Lima / 100) | mill. S/ de dic. 2021 | 413,71 – 199 435,32 |
| `disponible` | Caja, bancos, canje y otros disponibles | mill. S/ | 53,67 – 44 015,72 |
| `inversiones` | Inversiones netas de provisiones | mill. S/ | 0,09 – 42 631,19 |
| `creditos_vigentes` | Créditos vigentes (moneda nacional + extranjera) | mill. S/ | 114,22 – 118 636,11 |
| `creditos_vigentes_me` | Créditos vigentes en moneda extranjera (columna ME) | mill. S/ | 0,00 – 38 431,04 |
| `vig_prestamos` | Vigentes: préstamos | mill. S/ | 10,54 – 73 011,07 |
| `vig_hipotecarios` | Vigentes: hipotecarios para vivienda | mill. S/ | 0,00 – 22 990,82 |
| `vig_tarjetas` | Vigentes: tarjetas de crédito | mill. S/ | 0,00 – 8 485,51 |
| `vig_comercio_exterior` | Vigentes: comercio exterior | mill. S/ | 0,00 – 6 776,71 |
| `vig_arrendamiento` | Vigentes: arrendamiento financiero | mill. S/ | 0,00 – 9 637,42 |
| `creditos_refinanciados`, `creditos_atrasados` | Refinanciados y reestructurados; atrasados | mill. S/ | atrasados: 0,00 – 5 329,04 |
| `provisiones` | Provisiones para créditos (signo negativo, como en el balance) | mill. S/ | −7 243,96 – −1,26 |
| `creditos_directos` | Vigentes + refinanciados + atrasados (calculada) | mill. S/ | 118,73 – 125 118,21 |
| `credito_real` | Créditos directos / (IPC / 100) (calculada) | mill. S/ de dic. 2021 | 139,90 – 123 498,81 |
| `obligaciones_publico` | Obligaciones con el público (depósitos) | mill. S/ | 128,71 – 143 386,08 |
| `depositos_sistema_financiero` | Depósitos del sistema financiero y organismos internacionales | mill. S/ | 0,00 – 6 765,75 |
| `adeudos` | Adeudos y obligaciones financieras | mill. S/ | 0,00 – 17 623,80 |
| `capital_social` | Capital social | mill. S/ | 94,37 – 12 973,17 |
| `contingentes` | Créditos contingentes (avales, líneas no utilizadas, derivados y otros) | mill. S/ | 0,00 – 152 370,44 |

## Capital regulatorio (SBS, B-2402 · Vía 2)

| Variable | Descripción | Unidad | Rango |
|---|---|---|---|
| `req_credito`, `req_mercado`, `req_operacional` | Requerimiento de patrimonio efectivo por riesgo de crédito, de mercado y operacional | mill. S/ | crédito: 12,06 – 14 499,19 |
| `apr_total` | Activos y contingentes ponderados por riesgo (APR) totales (ver incidencias 4 y 15) | mill. S/ | 201,54 – 170 718,15 |
| `apr_credito` | APR por riesgo de crédito | mill. S/ | 120,65 – 146 792,95 |
| `patrimonio_efectivo` | Patrimonio efectivo (nivel 1 + nivel 2) | mill. S/ | 35,76 – 32 651,44 |
| `ratio_capital_global` | Patrimonio efectivo / APR | % | 2,89 – 68,33 |
| `ratio_cet1` | Capital ordinario de nivel 1 / APR (publicado desde 2023-06; vacío antes) | % | 8,12 – 37,81 |

## Variables construidas en `03_limpieza_datos.py`

| Variable | Definición | Unidad | Rango |
|---|---|---|---|
| `limite_global` | Límite global vigente en el mes (normas en `salidas/tabla_limite_global.csv` e incidencia 8) | % de los APR | 8,00 – 10,00 |
| `excedente_capital` | **Variable central**: `ratio_capital_global` − `limite_global` | p. p. | −5,11 – 58,33 |
| `densidad_apr` | 100 · APR / activo total (los APR incluyen contingentes, por eso puede superar 100) | % | 15,32 – 193,82 |
| `part_prestamos`, `part_hipotecario`, `part_tarjetas` | Participación de cada modalidad en el crédito vigente | % | hipotecario: 0,00 – 32,84 |
| `dolarizacion_credito` | 100 · crédito vigente en ME / crédito vigente | % | 0,00 – 97,02 |
| `depositos_activo` | 100 · obligaciones con el público / activo | % | 31,36 – 91,36 |
| `liquidez` | 100 · disponible / activo | % | 2,81 – 80,53 |
| `apalancamiento` | Activo / patrimonio (enlace con el Artículo I) | veces | 2,93 – 5 379,99 |
| `morosidad` | Créditos atrasados (criterio SBS) / créditos directos (SBS, B-2401) | % | 0,00 – 22,70 |

## Series macro (BCRP, API · Vía 1)

| Variable | Código | Descripción | Unidad | Rango 2016–2025 |
|---|---|---|---|---|
| `tasa_referencia` | PD04722MM | Tasa de referencia de la política monetaria | % | 0,25 – 7,75 |
| `tamn` | PN07807NM | Tasa activa promedio en moneda nacional | % | 10,49 – 17,74 |
| `tipmn` | PN07816NM | Tasa pasiva promedio en moneda nacional | % | 0,76 – 3,96 |
| `margen_tamn_tipmn` | calculada | TAMN − TIPMN | p. p. | 9,71 – 15,04 |
| `ipc_lima` | PN38705PM | IPC de Lima Metropolitana | índice dic. 2021 = 100 | 84,87 – 115,92 |
| `pbi_desestacionalizado` | PN01773AM | PBI desestacionalizado | índice 2007 = 100 | 104,36 – 193,88 |
| `credito_privado` | PN00505MM | Crédito de las sociedades creadoras de depósito al sector privado, TC constante | mill. S/ | 255 669,94 – 434 915,71 |

`datos_procesados/macro_mensual_2024200495A.csv` contiene estas series para 2010-01 a 2025-12 (192 meses) más `limite_global`; los meses 2010–2015 son la pre-muestra del filtro de Hamilton.

## Variables de trabajo construidas en `04_analisis.py`

| Variable | Definición |
|---|---|
| `ln_credito` | 100 · ln(`credito_real`) |
| `d12_ln_credito`, `d1_ln_credito` | Crecimiento real del crédito a 12 meses y mensual (diferencias de `ln_credito`, en %) |
| `d12_ln_hipotecarios`, `d12_ln_prestamos`, `d12_ln_tarjetas` | Crecimiento real a 12 meses por modalidad; solo si la modalidad pesaba ≥ 5 % del crédito vigente un año antes |
| `excedente_capital_l12`, `_l6`, `_l1` | Excedente rezagado 12, 6 y 1 meses |
| `brecha_pbi` | Residuo del filtro de Hamilton (h = 24, p = 12) sobre 100 · ln(PBI) |
| `d_tasa`, `d12_tasa` | Variación mensual y a 12 meses de la tasa de referencia (p. p.) |
| `capital_activo` | 100 · patrimonio efectivo / activo |
| `bajo_excedente` | 1 si el excedente promedio de 2022-09 a 2023-03 está por debajo de la mediana de los 14 bancos comparables (Alfin Banco excluido, incidencia 12) |
| `exposicion_z` | Versión continua: −(excedente previo − media) / D. E. |
