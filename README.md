# Artículo II · Excedente de capital regulatorio y oferta de crédito de la banca múltiple peruana en la transición a Basilea III, 2016–2025

- **Autora:** Lucia Pamela Colonio Yaringaño
- **Código de matrícula:** 2024200495A
- **Curso:** Finanzas I (055D) · Facultad de Economía · Universidad Nacional del Centro del Perú · Unidad II · 2026-II
- **Relación con el Artículo I:** complementa el Tema N.º 85 (*Apalancamiento del sistema bancario peruano y ciclo del crédito*). El Artículo I estudió la prociclicidad del apalancamiento; este estudia cómo el **excedente de capital sobre el mínimo legal** condiciona el crédito de cada banco y cómo se ajustaron los bancos cuando el regulador bajó (2021) y luego subió (2023–2025) ese mínimo.

El resultado es un panel balanceado de **15 bancos × 120 meses = 1 800 observaciones banco-mes**, construido con dos vías de extracción.

## 1. Fuentes de datos

### Vía 1 · API REST del BCRP (BCRPData)

```
https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{código}/json/2010-1/2025-12/esp
```

| Código | Serie | Uso |
|---|---|---|
| PD04722MM | Tasa de referencia de la política monetaria (%) | Choque de política (H2) |
| PN07807NM | Tasa activa promedio en MN, TAMN (%) | Precio del crédito (Figura del marco) |
| PN07816NM | Tasa pasiva promedio en MN, TIPMN (%) | Margen de intermediación |
| PN38705PM | IPC de Lima Metropolitana | Deflactor del crédito |
| PN01773AM | PBI desestacionalizado | Brecha del producto (control) |
| PN00505MM | Crédito al sector privado, TC constante | Contraste agregado |

No requiere clave de acceso. Las series se descargan desde 2010-01; los meses 2010–2015 son la pre-muestra del filtro de Hamilton.

### Vía 2 · Descarga programática del portal estadístico de la SBS

Las páginas de cada reporte se rastrean con BeautifulSoup (selector `a[href]`) y se descarga un archivo por mes:

| Reporte | Contenido | Variables extraídas |
|---|---|---|
| B-2201 | Balance general por empresa bancaria | activo, crédito vigente por modalidad (préstamos, hipotecarios, tarjetas, comercio exterior, arrendamiento) y en moneda extranjera, disponible, inversiones, depósitos, adeudos, capital social, contingentes |
| B-2401 | Indicadores financieros por empresa bancaria | morosidad |
| B-2402 | Requerimiento de patrimonio efectivo y ratio de capital global | requerimientos por riesgo de crédito, mercado y operacional; APR; patrimonio efectivo; ratio de capital global; ratio CET1 (desde 2023) |

Buenas prácticas: revisión de `robots.txt`, User-Agent identificable, pausa de 1,5 s entre solicitudes, hasta 3 reintentos y no se vuelve a descargar un archivo existente.

### Llave de integración

**Entidad + fecha (AAAA-MM).** Cada banco-mes de la SBS recibe las series del BCRP y el **límite global** vigente en ese mes.

### Marco normativo (variable construida)

El límite global (mínimo legal del ratio de capital global) se construye a partir de las normas citadas en las notas de los propios reportes B-2402 (`salidas/tabla_limite_global.csv` e incidencia 8): 10 % hasta 2021-03; 8 % entre 2021-04 y 2022-08; 8,5 % hasta 2023-03; 9 % hasta 2024-08; 9,5 % hasta 2025-02; 10 % desde 2025-03.

## 2. Ventana congelada

| Parámetro | Valor |
|---|---|
| Panel de bancos | 2016-01 a 2025-12 (120 meses) |
| Series macro del BCRP | 2010-01 a 2025-12 (192 meses) |
| Fecha de extracción | 2026-11-25 (BCRP y SBS) |

## 3. Estructura

| Carpeta o archivo | Contenido |
|---|---|
| `codigo/01_extraccion_api.py` | Vía 1: descarga las 6 series del BCRP |
| `codigo/02_scraping_web.py` | Vía 2: rastrea el portal de la SBS, descarga los 360 reportes y extrae las cifras por banco (tres formatos del B-2402) |
| `codigo/03_limpieza_datos.py` | Limpieza, validación (tres identidades), límite global, variables del estudio, unión de las dos vías y hash |
| `codigo/04_analisis.py` | Marco regulatorio, descriptivos, H1 a H4 y robustez |
| `datos_crudos/` | JSON de la API, XLS originales de la SBS, inventario de descargas y CSV crudos. **No se editan.** |
| `datos_procesados/` | Panel final, series macro y hashes SHA-256 |
| `salidas/` | Tablas (CSV) y figuras (SVG para el artículo, PNG para el dashboard) |
| `diccionario_variables.md` | Definición, unidad, fuente y rango de cada variable |
| `incidencias_fuente.md` | Particularidades de las fuentes y cómo se resolvieron |
| `log_ejecucion.txt` | Registro con fecha, hora y código HTTP de cada paso |

## 4. Cómo reproducir los resultados

**Requisitos:** Python 3.11 o superior y conexión a internet. Desde esta carpeta:

```bash
python -m pip install -r requirements.txt
python codigo/01_extraccion_api.py      # ~15 s
python codigo/02_scraping_web.py        # ~13 min la primera vez; luego solo lee los archivos
python codigo/03_limpieza_datos.py      # ~2 s
python codigo/04_analisis.py            # ~10 s
```

En Windows, si `python` no se reconoce, usar `py`. Demostración en vivo de la Vía 2 (últimos 3 meses, ~30 s): `python codigo/02_scraping_web.py --demo`.

## 5. Verificación de integridad

```
datos_procesados_2024200495A.csv   35817603ad4463ac8d60c0b198110568fc56bca4f932057cfeed540e65f50c3b
macro_mensual_2024200495A.csv      07455b9c3b56f2a10a31e804aab1206aeeb76b02f2a790d83a36eb3d922ce4bd
```

Windows: `Get-FileHash datos_procesados/datos_procesados_2024200495A.csv -Algorithm SHA256`.

## 6. Resumen del panel y controles de calidad

| Concepto | Valor |
|---|---|
| Bancos (120 meses completos) | 15: Alfin Banco, BANCOM, BanBif, Banco Falabella, Banco GNB, Banco ICBC, Banco Pichincha, Banco Ripley, Banco Santander Perú, BBVA Perú, BCP, Citibank Perú, Interbank, Mibanco, Scotiabank Perú |
| Bancos excluidos (entraron o salieron) | Banco BCI Perú, Banco Cencosud, Bank of China, Compartamos Banco, Deutsche Bank Perú, Santander Consumer Bank |
| Identidad activo = pasivo + patrimonio | se cumple en todas las filas (diferencia máxima: S/ 39) |
| Identidad ratio = PE / APR | se cumple en todas las filas (diferencia máxima: 0,005 p. p.) |
| Suma de modalidades ≤ crédito vigente | se cumple en todas las filas |
| Dato reconstruido | APR de Banco Santander Perú en 2019-07 (incidencia 15) |
| Banco-mes bajo el límite global | 13, todos de Alfin Banco (incidencia 12) |

## 7. Salidas (`salidas/`)

| Archivo | Contenido |
|---|---|
| `tabla_fuentes.csv` | Fuentes, códigos y uso de cada variable |
| `tabla_limite_global.csv` | Tramos del límite global y normas |
| `fig_marco_regulatorio.svg` | Límite global, ratio de capital global y CET1 del sistema; tasa de referencia, TAMN y TIPMN |
| `serie_sistema.csv` | Datos agregados del sistema (figura del marco y dashboard) |
| `tabla_descriptivos.csv` | Estadística descriptiva (desviación entre y dentro de bancos) |
| `tabla_bancos.csv` | Perfil de los 15 bancos y grupo de exposición |
| `fig_excedente_bancos.svg` | Excedente de capital por banco y año |
| `fig_densidad_apr.svg` | Densidad de los APR y crecimiento del crédito por grupo |
| `tabla_h1_excedente.csv` · `fig_h1_dispersion.svg` | H1: excedente y crecimiento del crédito (efectos fijos, Driscoll-Kraay) |
| `tabla_h2_proyecciones.csv` · `fig_h2_proyecciones.svg` | H2: proyecciones locales ante un alza de la tasa |
| `tabla_h3_did.csv` · `tabla_h3_eventos.csv` · `fig_h3_eventos.svg` | H3: diferencias en diferencias y estudio de eventos de la transición a Basilea III |
| `tabla_h4_descomposicion.csv` · `fig_h4_descomposicion.svg` | H4: márgenes de ajuste del ratio de capital |
| `tabla_robustez.csv` | H1 y H3 con especificaciones alternativas y placebos |
| `fig_correlaciones.svg` | Matriz de correlaciones |

Métodos implementados en `04_analisis.py` con numpy y scipy: efectos fijos de banco y de mes, errores de Driscoll y Kraay, proyecciones locales en panel, estudio de eventos, diferencias en diferencias con tendencias por banco y descomposición de Cohen y Scatigna (2016).

## 8. Uso de inteligencia artificial

El código se desarrolló con asistencia de Claude (Anthropic) como apoyo de programación y revisión metodológica. La autora ejecutó, verificó y es responsable de todo el contenido. La declaración completa figura en el artículo.
