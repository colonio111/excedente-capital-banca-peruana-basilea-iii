# Autora: Lucia Pamela Colonio Yaringaño
# Código de matrícula: 2024200495A
# Artículo II (complementario al Tema N.º 85 de la Unidad II): Excedente de capital
#   regulatorio y oferta de crédito de la banca múltiple peruana en la transición a Basilea III
# Fecha de extracción: 2026-11-25
"""
02_scraping_web.py · Vía 2 de extracción: rastreo del portal estadístico de la SBS
y descarga programática de los reportes mensuales por empresa bancaria.

Reportes (Superintendencia de Banca, Seguros y AFP, Banca Múltiple):
    B-2201  Balance general por empresa bancaria: activo, crédito por modalidad
            (préstamos, hipotecarios, tarjetas, comercio exterior), crédito en
            moneda extranjera, fondeo (depósitos y adeudos) y patrimonio
    B-2401  Indicadores financieros por empresa bancaria (morosidad)
    B-2402  Requerimiento de patrimonio efectivo: requerimientos por riesgo de
            crédito, mercado y operacional, activos ponderados por riesgo (APR),
            patrimonio efectivo, ratio de capital global y, desde 2023, ratio de
            capital ordinario de nivel 1 (CET1)

Cómo funciona:
    1. Comprueba que el robots.txt de la SBS permite las rutas que se van a usar.
    2. Abre la página de cada reporte en el portal y, con BeautifulSoup, busca los
       enlaces a archivos Excel (selector CSS: a[href]; se conservan los que
       terminan en .xls/.XLS/.xlsx). Así se obtiene la lista de archivos por mes,
       que es la "paginación" del portal: una página por reporte con un enlace
       por mes y por año.
    3. Conserva solo los meses entre FECHA_INICIO y FECHA_CORTE.
    4. Descarga cada archivo tal como lo publica la SBS, con pausa entre
       solicitudes y un User-Agent identificable.
    5. Lee los archivos descargados y extrae, por banco y por mes, las cifras
       que usa el estudio (balance, crédito por modalidad y moneda, fondeo,
       morosidad, activos ponderados por riesgo y ratios de capital). Las filas se ubican por su ETIQUETA (por
       ejemplo "TOTAL ACTIVO") y no por su número, porque la posición cambia
       entre años. Los nombres de los bancos se armonizan (p. ej. Banco
       Continental -> BBVA Perú) y se conserva también el nombre original.

Salidas:
    datos_crudos/sbs/{reporte}/*.XLS                      archivos originales, sin editar
    datos_crudos/sbs_inventario_descargas_2024200495A.csv una fila por archivo: URL,
                                                          código HTTP, tamaño, fecha y hash
    datos_crudos/datos_crudos_sbs_2024200495A.csv         cifras extraídas, formato largo:
                                                          una fila por banco, mes y variable
    log_ejecucion.txt                                     registro de cada solicitud

Ejecución (desde la carpeta raíz del repositorio):
    python codigo/02_scraping_web.py           descarga completa (360 archivos, ~12 min)
    python codigo/02_scraping_web.py --demo    demostración en vivo: últimos 3 meses (~30 s)
    (en Windows sin PATH, usar  py  en lugar de  python)

Si un archivo ya fue descargado, no se vuelve a pedir (salvo en modo --demo),
para no cargar el servidor de la SBS con solicitudes repetidas.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 1. Parámetros congelados de la extracción
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200495A"
FECHA_INICIO = "2016-01"
FECHA_CORTE = "2025-12"

# Código del reporte en la SBS -> nombre corto usado en este proyecto
REPORTES_SBS = {
    "B-2201": "balance_general",
    "B-2401": "indicadores_financieros",
    "B-2402": "ratio_capital_global",
}

URL_PORTAL = "https://www.sbs.gob.pe/app/stats_net/stats/EstadisticaSistemaFinancieroResultados.aspx?c={reporte}"
USER_AGENT = "UNCP-FinanzasI-ArticuloII/1.0 (trabajo academico; L. P. Colonio Yaringano)"
PAUSA_ENTRE_SOLICITUDES = 1.5  # segundos; la consigna exige al menos 1 s
INTENTOS_MAXIMOS = 3
TIEMPO_LIMITE = 60
MESES_DEMO = 3                 # meses que se descargan en modo --demo

# Nombres de los meses tal como aparecen en las rutas de la SBS
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Patrón de las rutas de los archivos, por ejemplo:
#   .../estadistica/financiera/2016/Enero/B-2201-en2016.XLS
PATRON_ARCHIVO = re.compile(
    r"/financiera/(?P<anio>\d{4})/(?P<mes>[A-Za-z]+)/(?P<archivo>(?P<reporte>B-\d+)-[a-z]{2}\d{4}\.(?:xls|xlsx))$",
    re.IGNORECASE,
)

# Abreviatura del mes en el nombre del archivo (B-2201-en2016.XLS -> enero)
MES_EN_ARCHIVO = {"en": 1, "fe": 2, "ma": 3, "ab": 4, "my": 5, "jn": 6,
                  "jl": 7, "ag": 8, "se": 9, "oc": 10, "no": 11, "di": 12}

# Armonización de nombres de bancos: si el nombre (en minúsculas y sin tildes)
# contiene el fragmento, se le asigna el nombre armonizado. El orden importa:
# "santander consumer" debe revisarse antes que "santander".
BANCOS = [
    ("continental", "BBVA Perú"), ("bbva", "BBVA Perú"),
    ("comercio", "BANCOM"), ("bancom", "BANCOM"),
    ("credito del peru", "BCP"), ("credito con sucursales", "BCP"),
    ("financiero", "Banco Pichincha"), ("pichincha", "Banco Pichincha"),
    ("interamericano", "BanBif"),
    ("scotiabank", "Scotiabank Perú"),
    ("citibank", "Citibank Perú"),
    ("interbank", "Interbank"),
    ("mibanco", "Mibanco"),
    ("gnb", "Banco GNB"),
    ("falabella", "Banco Falabella"),
    ("santander consumer", "Santander Consumer Bank"), ("santander", "Banco Santander Perú"),
    ("ripley", "Banco Ripley"),
    ("azteca", "Alfin Banco"), ("alfin", "Alfin Banco"),
    ("icbc", "Banco ICBC"),
    ("deutsche", "Deutsche Bank Perú"),
    ("cencosud", "Banco Cencosud"),
    ("china", "Bank of China"),
    ("bci", "Banco BCI Perú"),
    ("compartamos", "Compartamos Banco"),
]

# Filas que se extraen del balance (B-2201), buscadas por su etiqueta.
# Cada fila: (variable, patrón, sección, columnas). El patrón se aplica a la
# etiqueta en minúsculas y sin tildes. La sección indica desde dónde se busca:
# "inicio" (todo el balance) o "creditos" (después de "CRÉDITOS NETOS...",
# porque hay otras filas llamadas "Vigentes" o "Provisiones" en otras partes).
# Columnas: TOTAL (MN + ME) y, cuando interesa la dolarización, también ME.
FILAS_BALANCE = [
    ("activo_total", r"^total activo$", "inicio", ("TOTAL",)),
    ("pasivo_total", r"^total pasivo$", "inicio", ("TOTAL",)),
    ("patrimonio", r"^patrimonio$", "inicio", ("TOTAL",)),
    ("disponible", r"^disponible$", "inicio", ("TOTAL",)),
    ("inversiones", r"^inversiones netas de provisiones", "inicio", ("TOTAL",)),
    ("creditos_netos", r"^creditos netos", "inicio", ("TOTAL",)),
    ("creditos_vigentes", r"^vigentes", "creditos", ("TOTAL", "ME")),
    ("vig_tarjetas", r"^tarjetas de credito", "creditos", ("TOTAL",)),
    ("vig_prestamos", r"^prestamos$", "creditos", ("TOTAL",)),
    ("vig_hipotecarios", r"^hipotecarios para vivienda", "creditos", ("TOTAL",)),
    ("vig_comercio_exterior", r"^comercio exterior", "creditos", ("TOTAL",)),
    ("vig_arrendamiento", r"^arrendamiento financiero", "creditos", ("TOTAL",)),
    ("creditos_refinanciados", r"^refinanciados", "creditos", ("TOTAL",)),
    ("creditos_atrasados", r"^atrasados", "creditos", ("TOTAL",)),
    ("provisiones", r"^provisiones", "creditos", ("TOTAL",)),
    ("obligaciones_publico", r"^obligaciones con el publico", "inicio", ("TOTAL",)),
    ("depositos_sistema_financiero", r"^depositos del sistema financiero", "inicio", ("TOTAL",)),
    ("adeudos", r"^adeudos y obligaciones financieras", "inicio", ("TOTAL",)),
    ("capital_social", r"^capital social", "inicio", ("TOTAL",)),
    ("resultados_acumulados", r"^resultados acumulados", "inicio", ("TOTAL",)),
    ("contingentes", r"^contingentes$", "inicio", ("TOTAL",)),
]

# ---------------------------------------------------------------------------
# 2. Rutas relativas a la carpeta del proyecto
# ---------------------------------------------------------------------------
if "__file__" in globals():
    RAIZ = Path(__file__).resolve().parent.parent
else:
    RAIZ = Path.cwd()
CARPETA_CRUDOS = RAIZ / "datos_crudos"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"


def anotar(mensaje: str) -> None:
    """Muestra el mensaje en consola y lo añade al log con fecha y hora."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [02_sbs] {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as log:
        log.write(linea + "\n")


def crear_sesion() -> requests.Session:
    """Sesión HTTP que envía siempre el mismo User-Agent identificable."""
    sesion = requests.Session()
    sesion.headers.update({"User-Agent": USER_AGENT})
    return sesion


def pedir(sesion: requests.Session, url: str) -> requests.Response:
    """
    GET con reintentos. Devuelve la respuesta si el código HTTP es 200;
    si falla INTENTOS_MAXIMOS veces, lanza un error con el último motivo.
    """
    ultimo_motivo = ""
    for intento in range(1, INTENTOS_MAXIMOS + 1):
        try:
            respuesta = sesion.get(url, timeout=TIEMPO_LIMITE)
            if respuesta.status_code == 200:
                return respuesta
            ultimo_motivo = f"HTTP {respuesta.status_code}"
        except requests.RequestException as error:
            ultimo_motivo = f"error de conexión ({error.__class__.__name__})"
        anotar(f"Intento {intento} fallido para {url}: {ultimo_motivo}")
        time.sleep(PAUSA_ENTRE_SOLICITUDES * (intento + 1))
    raise RuntimeError(f"{url} · {ultimo_motivo}")


def robots_permite(sesion: requests.Session, url: str) -> bool:
    """
    Lee el robots.txt del dominio de la URL y comprueba si nuestro User-Agent
    puede acceder a ella. Si el dominio no publica robots.txt, se permite.
    """
    partes = urlparse(url)
    url_robots = f"{partes.scheme}://{partes.netloc}/robots.txt"
    lector = robotparser.RobotFileParser()
    try:
        respuesta = sesion.get(url_robots, timeout=TIEMPO_LIMITE)
        if respuesta.status_code >= 400:
            anotar(f"robots.txt de {partes.netloc}: no publicado (HTTP {respuesta.status_code}), acceso permitido")
            return True
        lector.parse(respuesta.text.splitlines())
    except requests.RequestException:
        anotar(f"robots.txt de {partes.netloc}: no se pudo leer; se continúa con cautela")
        return True
    permitido = lector.can_fetch(USER_AGENT, url)
    anotar(f"robots.txt de {partes.netloc}: {'permite' if permitido else 'PROHÍBE'} {partes.path}")
    return permitido


def listar_archivos(sesion: requests.Session, reporte: str) -> list[dict]:
    """
    Rastrea la página del reporte en el portal y devuelve un registro por
    archivo mensual: reporte, año, mes, URL y nombre del archivo.
    Selector usado: todos los <a href> de la página cuyo destino coincide con
    PATRON_ARCHIVO (archivo Excel dentro de /estadistica/financiera/).
    """
    url_pagina = URL_PORTAL.format(reporte=reporte)
    respuesta = pedir(sesion, url_pagina)
    sopa = BeautifulSoup(respuesta.text, "html.parser")

    encontrados = {}
    for enlace in sopa.select("a[href]"):
        destino = enlace["href"].strip()
        coincidencia = PATRON_ARCHIVO.search(destino)
        if not coincidencia or coincidencia["reporte"].upper() != reporte:
            continue
        mes = MESES.get(coincidencia["mes"].lower())
        if mes is None:
            continue
        clave = (int(coincidencia["anio"]), mes)
        encontrados[clave] = {
            "reporte": reporte,
            "anio": clave[0],
            "mes": mes,
            "url": requests.compat.urljoin(url_pagina, destino),
            "archivo": coincidencia["archivo"],
        }
    anotar(f"{reporte}: página rastreada (HTTP {respuesta.status_code}) · {len(encontrados)} archivos mensuales enlazados")
    return [encontrados[clave] for clave in sorted(encontrados)]


def dentro_de_ventana(registro: dict, desde: str, hasta: str) -> bool:
    """True si el mes del archivo está entre 'desde' y 'hasta' (formato AAAA-MM)."""
    periodo = f"{registro['anio']:04d}-{registro['mes']:02d}"
    return desde <= periodo <= hasta


def meses_esperados(desde: str, hasta: str) -> list[tuple[int, int]]:
    """Lista de (año, mes) que debería existir en la ventana."""
    periodos = pd.period_range(desde, hasta, freq="M")
    return [(p.year, p.month) for p in periodos]


# ---------------------------------------------------------------------------
# 3. Lectura de los archivos descargados
#    Los archivos de la SBS mezclan dos formatos (Excel antiguo .xls y Excel
#    moderno guardado con extensión .XLS). El motor "calamine" lee ambos.
# ---------------------------------------------------------------------------
def normalizar(texto) -> str:
    """Minúsculas, sin tildes y con un solo espacio: 'Créditos  Netos' -> 'creditos netos'."""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def armonizar_banco(nombre) -> str | None:
    """
    Nombre armonizado del banco, o None si la celda no es un banco
    (vacía, 'Activo' o una fila de totales del sistema).
    """
    texto = normalizar(nombre)
    if texto in ("", "nan", "activo") or texto.startswith("total"):
        return None
    for fragmento, nombre_armonizado in BANCOS:
        if fragmento in texto:
            return nombre_armonizado
    return f"NO IDENTIFICADO: {str(nombre).strip()}"


def leer_hoja(ruta: Path) -> pd.DataFrame:
    """Primera hoja del archivo, sin encabezados (se ubican a mano)."""
    return pd.read_excel(ruta, engine="calamine", sheet_name=0, header=None)


def fila_de_bancos(hoja: pd.DataFrame) -> int:
    """Número de la fila que tiene los nombres de los bancos (al menos 5)."""
    for i in range(min(15, len(hoja))):
        nombres = [armonizar_banco(celda) for celda in hoja.iloc[i]]
        if sum(1 for n in nombres if n and not n.startswith("NO IDENTIFICADO")) >= 5:
            return i
    raise ValueError("no se encontró la fila con los nombres de los bancos")


def buscar_fila(etiquetas: list[str], patron: str, desde: int = 0) -> int | None:
    """Primera fila (desde 'desde') cuya etiqueta coincide con el patrón."""
    for i in range(desde, len(etiquetas)):
        if re.match(patron, etiquetas[i]):
            return i
    return None


def leer_balance(ruta: Path) -> list[dict]:
    """
    B-2201: cada banco ocupa tres columnas (MN, ME, TOTAL). Se toma TOTAL y,
    para el crédito vigente, también ME (moneda extranjera, para medir la
    dolarización). Se omiten las columnas 'con Sucursales en el Exterior',
    que repiten a un banco ya incluido sumándole sus oficinas fuera del Perú.
    """
    hoja = leer_hoja(ruta)
    fb = fila_de_bancos(hoja)
    etiquetas = [normalizar(x) for x in hoja.iloc[:, 0]]

    inicio = {"inicio": 0, "creditos": buscar_fila(etiquetas, r"^creditos netos") or 0}
    filas = {variable: (buscar_fila(etiquetas, patron, inicio[seccion]), columnas)
             for variable, patron, seccion, columnas in FILAS_BALANCE}
    no_halladas = [v for v, (i, _) in filas.items() if i is None]
    if no_halladas:
        raise ValueError(f"etiquetas no encontradas: {no_halladas}")

    registros = []
    for columna in range(1, hoja.shape[1]):
        nombre = hoja.iat[fb, columna]
        banco = armonizar_banco(nombre)
        if banco is None or "sucursales" in normalizar(nombre):
            continue
        # Posición de MN, ME y TOTAL de este banco (en la fila de subtítulos)
        posiciones = {normalizar(hoja.iat[fb + 1, k]).upper(): k
                      for k in range(columna, min(columna + 4, hoja.shape[1]))}
        if "TOTAL" not in posiciones:
            raise ValueError(f"no se encontró la columna TOTAL de {nombre}")
        for variable, (fila, columnas) in filas.items():
            for moneda in columnas:
                sufijo = "" if moneda == "TOTAL" else "_me"
                registros.append({"entidad_sbs": str(nombre).strip(), "entidad": banco,
                                  "variable": variable + sufijo,
                                  "valor": hoja.iat[fila, posiciones[moneda]],
                                  "unidad": "miles de soles"})
    return registros


def leer_indicadores(ruta: Path) -> list[dict]:
    """B-2401: fila 'Créditos Atrasados (criterio SBS) / Créditos Directos' (morosidad, %)."""
    hoja = leer_hoja(ruta)
    fb = fila_de_bancos(hoja)
    etiquetas = [normalizar(x) for x in hoja.iloc[:, 0]]
    fila = buscar_fila(etiquetas, r"^creditos atrasados \(criterio (sbs|contable)\).*/ creditos directos")
    if fila is None:
        raise ValueError("no se encontró la fila de morosidad")
    registros = []
    for columna in range(1, hoja.shape[1]):
        nombre = hoja.iat[fb, columna]
        banco = armonizar_banco(nombre)
        if banco is None:
            continue
        registros.append({"entidad_sbs": str(nombre).strip(), "entidad": banco,
                          "variable": "morosidad", "valor": hoja.iat[fila, columna],
                          "unidad": "porcentaje"})
    return registros


def leer_capital(ruta: Path) -> list[dict]:
    """
    B-2402: los bancos están en filas (debajo de 'EMPRESAS'). El reporte tiene
    tres formatos (ver incidencias_fuente.md):
      formato 1 (desde 2016)   requerimientos (a, b, c), patrimonio efectivo y
                               ratio de capital global = PE / [(a+b+c)/10 %]
      formato 2 (desde 2021)   además, activos ponderados por riesgo (APR) por tipo de riesgo
      formato 3 (desde 2023)   APR, ratio de capital ordinario de nivel 1 (CET1) y ratio
                               de capital global, sin la columna de patrimonio efectivo
    Las columnas se ubican por su ENCABEZADO. Cuando un dato no se publica,
    se reconstruye con las identidades del propio reporte:
      APR = (a + b + c) / 10 %      (formato 1, tal como lo indica la fórmula del ratio)
      PE  = ratio de capital global × APR / 100   (formato 3)
    """
    hoja = leer_hoja(ruta)
    etiquetas = [normalizar(x) for x in hoja.iloc[:, 0]]
    fila_empresas = buscar_fila(etiquetas, r"^empresas$")
    if fila_empresas is None:
        raise ValueError("no se encontró la fila 'EMPRESAS'")

    encabezados = [" ".join(normalizar(x) for x in hoja.iloc[max(0, fila_empresas - 3):fila_empresas + 2, c]
                            if normalizar(x) != "nan") for c in range(hoja.shape[1])]

    def columna(*fragmentos: str, ultima: bool = True) -> int | None:
        coincidencias = [c for c, h in enumerate(encabezados) if all(f in h for f in fragmentos)]
        return (coincidencias[-1] if ultima else coincidencias[0]) if coincidencias else None

    col = {
        "req_credito": 1, "req_mercado": 2, "req_operacional": 3,
        "ratio_capital_global": columna("ratio de capital global"),
        "ratio_cet1": columna("capital ordinario de nivel 1"),
        "patrimonio_efectivo": columna("patrimonio efectivo total"),
        "apr_total": columna("total (h)") or columna("totales (apr)"),
        "apr_credito": columna("ponderados por riesgo", "credito", ultima=False),
    }
    if col["ratio_capital_global"] is None:
        raise ValueError("no se encontró la columna del ratio de capital global")
    if "requerimiento" not in encabezados[1] or "mercado" not in encabezados[2] or "operacional" not in encabezados[3]:
        raise ValueError("las columnas de requerimientos no están en la posición esperada")

    registros = []
    for fila in range(fila_empresas + 1, len(hoja)):
        if etiquetas[fila].startswith("total"):
            break
        banco = armonizar_banco(hoja.iat[fila, 0])
        if banco is None:
            continue
        valor = {v: (pd.to_numeric(hoja.iat[fila, c], errors="coerce") if c is not None else float("nan"))
                 for v, c in col.items()}
        requerimiento = valor["req_credito"] + valor["req_mercado"] + valor["req_operacional"]
        if pd.isna(valor["apr_total"]):
            valor["apr_total"] = requerimiento / 0.10
        if pd.isna(valor["apr_credito"]):
            valor["apr_credito"] = valor["req_credito"] / 0.10
        if pd.isna(valor["patrimonio_efectivo"]):
            valor["patrimonio_efectivo"] = valor["ratio_capital_global"] * valor["apr_total"] / 100
        for variable, numero in valor.items():
            unidad = "porcentaje" if variable.startswith("ratio") else "miles de soles"
            registros.append({"entidad_sbs": str(hoja.iat[fila, 0]).strip(), "entidad": banco,
                              "variable": variable, "valor": numero, "unidad": unidad})
    return registros


LECTORES = {"B-2201": leer_balance, "B-2401": leer_indicadores, "B-2402": leer_capital}


def extraer_cifras(carpeta_destino: Path, archivo_salida: Path) -> int:
    """
    Recorre los archivos descargados, extrae las cifras de cada uno y las
    guarda en un CSV largo. Devuelve el número de archivos con error.
    """
    filas, errores = [], 0
    for reporte, lector in LECTORES.items():
        for ruta in sorted((carpeta_destino / reporte).glob("*.[xX][lL][sS]*")):
            clave = re.search(r"-([a-z]{2})(\d{4})\.", ruta.name.lower())
            try:
                for registro in lector(ruta):
                    filas.append({"reporte": reporte, "archivo": ruta.name,
                                  "anio": int(clave.group(2)), "mes": MES_EN_ARCHIVO[clave.group(1)],
                                  **registro})
            except (ValueError, KeyError, AttributeError) as error:
                errores += 1
                anotar(f"{ruta.name}: no se pudo leer · {error}")

    tabla = pd.DataFrame(filas)
    tabla.to_csv(archivo_salida, index=False, encoding="utf-8")
    anotar(f"Cifras extraídas: {archivo_salida.relative_to(RAIZ).as_posix()} · {len(tabla)} filas")
    if tabla.empty:
        return errores + 1

    sin_identificar = sorted(tabla.loc[tabla["entidad"].str.startswith("NO IDENTIFICADO"), "entidad"].unique())
    if sin_identificar:
        anotar(f"Bancos sin armonizar (revisar la lista BANCOS): {sin_identificar}")

    # Cobertura: observaciones banco-mes con activo y patrimonio disponibles
    balance = tabla[tabla["variable"].isin(["activo_total", "patrimonio"])]
    obs = balance.groupby(["entidad", "anio", "mes"]).size()
    anotar(f"Observaciones banco-mes en el balance: {len(obs)} · bancos distintos: {tabla['entidad'].nunique()}")
    return errores


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    argumentos = argparse.ArgumentParser(description="Descarga de reportes mensuales de la SBS")
    argumentos.add_argument("--demo", action="store_true",
                            help=f"descarga solo los últimos {MESES_DEMO} meses (demostración en vivo)")
    modo_demo = argumentos.parse_args().demo

    # En modo demostración se descargan siempre de nuevo los últimos meses,
    # en una carpeta aparte para no mezclar con la extracción completa.
    if modo_demo:
        desde = str(pd.Period(FECHA_CORTE, freq="M") - (MESES_DEMO - 1))
        carpeta_destino = CARPETA_CRUDOS / "sbs_demo"
        archivo_inventario = CARPETA_CRUDOS / f"sbs_demo_inventario_{CODIGO_MATRICULA}.csv"
    else:
        desde = FECHA_INICIO
        carpeta_destino = CARPETA_CRUDOS / "sbs"
        archivo_inventario = CARPETA_CRUDOS / f"sbs_inventario_descargas_{CODIGO_MATRICULA}.csv"

    anotar(f"Inicio de la extracción SBS · {'DEMOSTRACIÓN' if modo_demo else 'completa'} · periodo {desde} a {FECHA_CORTE}")
    sesion = crear_sesion()

    # 1. robots.txt: portal (páginas) y servidor de archivos
    ejemplo_archivo = "https://intranet2.sbs.gob.pe/estadistica/financiera/2016/Enero/B-2201-en2016.XLS"
    if not (robots_permite(sesion, URL_PORTAL.format(reporte="B-2201"))
            and robots_permite(sesion, ejemplo_archivo)):
        anotar("El robots.txt prohíbe la ruta: se detiene la extracción (ver numeral 2.4.3 de la consigna)")
        return 1

    # Si ya existe un inventario de una ejecución anterior, se conserva la fecha
    # y el código HTTP de la descarga original de cada archivo.
    previo = {}
    if archivo_inventario.exists() and not modo_demo:
        tabla_previa = pd.read_csv(archivo_inventario, dtype=str).fillna("")
        previo = {fila["archivo"]: fila for fila in tabla_previa.to_dict("records")}

    inventario = []
    faltantes = []
    errores = 0

    for reporte, nombre_corto in REPORTES_SBS.items():
        time.sleep(PAUSA_ENTRE_SOLICITUDES)
        registros = [r for r in listar_archivos(sesion, reporte)
                     if dentro_de_ventana(r, desde, FECHA_CORTE)]

        # Control de cobertura: ¿falta algún mes en el portal?
        disponibles = {(r["anio"], r["mes"]) for r in registros}
        for anio, mes in meses_esperados(desde, FECHA_CORTE):
            if (anio, mes) not in disponibles:
                faltantes.append(f"{reporte} {anio}-{mes:02d}")

        carpeta_reporte = carpeta_destino / reporte
        carpeta_reporte.mkdir(parents=True, exist_ok=True)

        for registro in registros:
            ruta_local = carpeta_reporte / registro["archivo"]
            fila = {**registro, "nombre_reporte": nombre_corto,
                    "ruta_local": ruta_local.relative_to(RAIZ).as_posix()}

            if ruta_local.exists() and not modo_demo:
                contenido = ruta_local.read_bytes()
                anterior = previo.get(registro["archivo"], {})
                fila.update(http=anterior.get("http") or "ya descargado", bytes=len(contenido),
                            sha256=hashlib.sha256(contenido).hexdigest(),
                            descargado_en=anterior.get("descargado_en", ""))
                inventario.append(fila)
                continue

            time.sleep(PAUSA_ENTRE_SOLICITUDES)
            try:
                respuesta = pedir(sesion, registro["url"])
                ruta_local.write_bytes(respuesta.content)   # archivo original, sin cambios
                fila.update(http=respuesta.status_code, bytes=len(respuesta.content),
                            sha256=hashlib.sha256(respuesta.content).hexdigest(),
                            descargado_en=f"{datetime.now():%Y-%m-%d %H:%M:%S}")
                anotar(f"{registro['archivo']}: HTTP {respuesta.status_code} · {len(respuesta.content):,} bytes")
            except RuntimeError as error:
                errores += 1
                fila.update(http="error", bytes=0, sha256="", descargado_en="")
                anotar(f"{registro['archivo']}: ERROR · {error}")
            inventario.append(fila)

    # Inventario de descargas: evidencia de qué se descargó, cuándo y con qué hash
    tabla = pd.DataFrame(inventario)
    tabla.to_csv(archivo_inventario, index=False, encoding="utf-8")
    anotar(f"Inventario guardado: {archivo_inventario.relative_to(RAIZ).as_posix()} · {len(tabla)} archivos")

    if not tabla.empty:
        anotar(f"Archivos por reporte: {tabla.groupby('reporte').size().to_dict()}")
    if faltantes:
        anotar(f"Meses no publicados en el portal: {faltantes}")

    # 5. Lectura de los archivos descargados -> CSV crudo en formato largo
    if modo_demo:
        archivo_cifras = CARPETA_CRUDOS / f"sbs_demo_cifras_{CODIGO_MATRICULA}.csv"
    else:
        archivo_cifras = CARPETA_CRUDOS / f"datos_crudos_sbs_{CODIGO_MATRICULA}.csv"
    errores += extraer_cifras(carpeta_destino, archivo_cifras)

    if errores:
        anotar(f"Extracción INCOMPLETA: {errores} archivos con error. Volver a ejecutar para reintentar solo esos.")
        return 1
    anotar("Extracción SBS terminada sin errores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
