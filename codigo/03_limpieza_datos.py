# Autora: Lucia Pamela Colonio Yaringaño
# Código de matrícula: 2024200495A
# Artículo II (complementario al Tema N.º 85 de la Unidad II): Excedente de capital
#   regulatorio y oferta de crédito de la banca múltiple peruana en la transición a Basilea III
# Fecha de extracción: 2026-11-25
"""
03_limpieza_datos.py · Limpieza, validación e integración de las dos vías.

Entradas (generadas por los scripts 01 y 02, no se modifican):
    datos_crudos/datos_crudos_bcrp_2024200495A.csv   series macro del BCRP (Vía 1, API)
    datos_crudos/datos_crudos_sbs_2024200495A.csv    cifras por banco de la SBS (Vía 2)

Qué hace:
    1. Convierte los valores a números y los periodos a fechas (AAAA-MM).
    2. Pasa la información de la SBS a una tabla ancha: una fila por banco y mes.
    3. Conserva solo los bancos con los 120 meses completos (panel balanceado).
    4. Valida la información con tres identidades: activo = pasivo + patrimonio,
       ratio de capital global = patrimonio efectivo / APR, y suma de las
       modalidades del crédito vigente <= crédito vigente.
    5. Añade el LÍMITE GLOBAL vigente en cada mes (requerimiento mínimo de
       capital, art. 199 de la Ley General), según las normas que lo fijaron.
    6. Calcula las variables del estudio: excedente de capital regulatorio,
       densidad de los APR, crédito real y su composición, fondeo y liquidez.
    7. Une la información de los bancos con las series del BCRP por la fecha.
       La llave del panel es Entidad + fecha.
    8. Guarda el panel, las series macro (con la pre-muestra 2010-2015) y sus
       huellas digitales SHA-256.

Salidas:
    datos_procesados/datos_procesados_2024200495A.csv   panel banco-mes final (2016-01 a 2025-12)
    datos_procesados/macro_mensual_2024200495A.csv      series del BCRP 2010-01 a 2025-12 y límite global
    datos_procesados/sha256_datos_procesados.txt         hash SHA-256 de los dos archivos
    log_ejecucion.txt                                     resumen de cada paso

Ejecución (desde la carpeta raíz del repositorio):
    python codigo/03_limpieza_datos.py      (en Windows sin PATH: py codigo/03_limpieza_datos.py)
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1. Parámetros
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200495A"
FECHA_INICIO = "2016-01"        # primer mes del panel de bancos
FECHA_INICIO_MACRO = "2010-01"  # primer mes de las series del BCRP (pre-muestra)
FECHA_CORTE = "2025-12"
MESES_ESPERADOS = len(pd.period_range(FECHA_INICIO, FECHA_CORTE, freq="M"))        # 120
MESES_MACRO = len(pd.period_range(FECHA_INICIO_MACRO, FECHA_CORTE, freq="M"))      # 192

# Meses abreviados que usa el BCRP en sus periodos ('Ene.2016', 'Set.2016'...)
MESES_BCRP = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
              "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}

# Variables de la SBS que debe tener cada banco en todos los meses
VARIABLES_CLAVE = ["activo_total", "patrimonio", "creditos_vigentes", "morosidad",
                   "ratio_capital_global", "apr_total"]

# Montos que se pasan de miles a millones de soles (la unidad del BCRP)
MONTOS = ["activo_total", "pasivo_total", "patrimonio", "disponible", "inversiones", "creditos_netos",
          "creditos_vigentes", "creditos_vigentes_me", "vig_tarjetas", "vig_prestamos",
          "vig_hipotecarios", "vig_comercio_exterior", "vig_arrendamiento", "creditos_refinanciados",
          "creditos_atrasados", "provisiones", "obligaciones_publico", "depositos_sistema_financiero",
          "adeudos", "capital_social", "resultados_acumulados", "contingentes",
          "req_credito", "req_mercado", "req_operacional", "apr_total", "apr_credito",
          "patrimonio_efectivo"]

# Límite global (requerimiento mínimo del ratio de capital global, %), por tramo.
# Cada tramo: (primer mes, último mes, límite, norma que lo fijó). Las fechas son
# las que efectivamente rigieron; el cronograma de Basilea III se postergó dos
# veces (ver incidencias_fuente.md, n.º 8).
LIMITE_GLOBAL = [
    ("2010-01", "2021-03", 10.0, "Ley 26702, art. 199"),
    ("2021-04", "2022-08", 8.0, "D. U. 037-2021 y D. U. 003-2022"),
    ("2022-09", "2023-03", 8.5, "D. U. 003-2022 y Res. SBS 3952-2022"),
    ("2023-04", "2024-08", 9.0, "Res. SBS 3952-2022, 2192-2023 y 274-2024"),
    ("2024-09", "2025-02", 9.5, "Res. SBS 274-2024"),
    ("2025-03", "2025-12", 10.0, "Res. SBS 274-2024 (D. L. 1531)"),
]

# Tolerancias de las validaciones
TOLERANCIA_IDENTIDAD = 1.0      # miles de soles (redondeo del balance)
TOLERANCIA_RATIO = 0.05         # puntos porcentuales (el ratio se publica con 2 decimales)

# ---------------------------------------------------------------------------
# 2. Rutas relativas a la carpeta del proyecto
# ---------------------------------------------------------------------------
if "__file__" in globals():
    RAIZ = Path(__file__).resolve().parent.parent
else:
    RAIZ = Path.cwd()
CARPETA_CRUDOS = RAIZ / "datos_crudos"
CARPETA_PROCESADOS = RAIZ / "datos_procesados"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"
ENTRADA_BCRP = CARPETA_CRUDOS / f"datos_crudos_bcrp_{CODIGO_MATRICULA}.csv"
ENTRADA_SBS = CARPETA_CRUDOS / f"datos_crudos_sbs_{CODIGO_MATRICULA}.csv"
SALIDA = CARPETA_PROCESADOS / f"datos_procesados_{CODIGO_MATRICULA}.csv"
SALIDA_MACRO = CARPETA_PROCESADOS / f"macro_mensual_{CODIGO_MATRICULA}.csv"
SALIDA_HASH = CARPETA_PROCESADOS / "sha256_datos_procesados.txt"


def anotar(mensaje: str) -> None:
    """Muestra el mensaje en consola y lo añade al log con fecha y hora."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [03_limpieza] {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as log:
        log.write(linea + "\n")


def fecha_texto(tabla: pd.DataFrame) -> pd.Series:
    """Columnas anio y mes -> texto 'AAAA-MM'."""
    return pd.to_datetime(dict(year=tabla["anio"], month=tabla["mes"], day=1)).dt.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# 3. Vía 1: series del BCRP y límite global
# ---------------------------------------------------------------------------
def preparar_bcrp() -> pd.DataFrame:
    """Tabla con una fila por mes y una columna por serie del BCRP."""
    crudo = pd.read_csv(ENTRADA_BCRP, dtype=str)

    # 'Ene.2016' -> 2016-01 ; los valores 'n.d.' se convierten en vacíos (NaN)
    partes = crudo["periodo_bcrp"].str.split(".", expand=True)
    crudo["anio"] = partes[1].astype(int)
    crudo["mes"] = partes[0].str.lower().str[:3].map(MESES_BCRP)
    if crudo["mes"].isna().any():
        raise ValueError(f"Mes no reconocido en el BCRP: {crudo.loc[crudo['mes'].isna(), 'periodo_bcrp'].unique()}")
    crudo["valor"] = pd.to_numeric(crudo["valor"], errors="coerce")

    macro = crudo.pivot_table(index=["anio", "mes"], columns="variable", values="valor", aggfunc="first")
    macro = macro.reset_index()
    macro.columns.name = None

    vacios = macro.drop(columns=["anio", "mes"]).isna().sum()
    anotar(f"BCRP: {len(macro)} meses · valores vacíos por serie: {vacios.to_dict()}")
    if len(macro) != MESES_MACRO:
        raise ValueError(f"El BCRP tiene {len(macro)} meses; se esperaban {MESES_MACRO}")

    # Margen de intermediación en moneda nacional (puntos porcentuales)
    macro["margen_tamn_tipmn"] = macro["tamn"] - macro["tipmn"]
    macro["fecha"] = fecha_texto(macro)
    macro["limite_global"] = macro["fecha"].map(limite_global_vigente)
    return macro


def limite_global_vigente(fecha: str) -> float:
    """Límite global (%) que regía en el mes 'AAAA-MM'."""
    for desde, hasta, limite, _ in LIMITE_GLOBAL:
        if desde <= fecha <= hasta:
            return limite
    raise ValueError(f"No hay límite global definido para {fecha}")


# ---------------------------------------------------------------------------
# 4. Vía 2: cifras por banco de la SBS
# ---------------------------------------------------------------------------
def preparar_sbs() -> pd.DataFrame:
    """Tabla con una fila por banco y mes, y una columna por variable."""
    crudo = pd.read_csv(ENTRADA_SBS)
    crudo["valor"] = pd.to_numeric(crudo["valor"], errors="coerce")
    no_numericos = int(crudo["valor"].isna().sum())

    bancos = crudo.pivot_table(index=["entidad", "anio", "mes"], columns="variable",
                               values="valor", aggfunc="first", dropna=False).reset_index()
    bancos.columns.name = None
    anotar(f"SBS: {len(bancos)} filas banco-mes · {bancos['entidad'].nunique()} bancos · "
           f"valores vacíos en el crudo (p. ej. CET1 antes de 2023): {no_numericos}")
    return bancos


def reparar_apr(bancos: pd.DataFrame) -> pd.DataFrame:
    """
    Si la SBS dejó vacío algún requerimiento (y por tanto los APR), pero publicó
    el patrimonio efectivo y el ratio de capital global, los APR se recuperan con
    la identidad del propio reporte: APR = 100 · PE / ratio. El requerimiento
    por riesgo de crédito se reconstruye como el resto (ver incidencias_fuente.md, n.º 15).
    """
    faltan = bancos["apr_total"].isna() & bancos["patrimonio_efectivo"].notna() & bancos["ratio_capital_global"].notna()
    for _, fila in bancos[faltan].iterrows():
        anotar(f"APR reconstruido con PE / ratio: {fila['entidad']} {int(fila['anio'])}-{int(fila['mes']):02d}")
    apr = 100 * bancos["patrimonio_efectivo"] / bancos["ratio_capital_global"]
    bancos.loc[faltan, "apr_total"] = apr[faltan]
    falta_credito = faltan & bancos["req_credito"].isna()
    resto = 0.10 * apr - bancos["req_mercado"].fillna(0) - bancos["req_operacional"].fillna(0)
    bancos.loc[falta_credito, "req_credito"] = resto[falta_credito]
    bancos.loc[falta_credito, "apr_credito"] = resto[falta_credito] / 0.10
    return bancos


def seleccionar_panel_balanceado(bancos: pd.DataFrame) -> pd.DataFrame:
    """
    Conserva los bancos que tienen las VARIABLES_CLAVE en los 120 meses.
    Los demás (entraron o salieron del sistema en el periodo) se excluyen y
    se anotan en el log con el número de meses que sí tienen.
    """
    completos = bancos.dropna(subset=VARIABLES_CLAVE)
    meses_por_banco = completos.groupby("entidad").size()
    incluidos = sorted(meses_por_banco[meses_por_banco == MESES_ESPERADOS].index)
    excluidos = meses_por_banco[meses_por_banco < MESES_ESPERADOS].to_dict()

    anotar(f"Bancos con los {MESES_ESPERADOS} meses completos: {len(incluidos)} · {incluidos}")
    anotar(f"Bancos excluidos (meses disponibles): {excluidos}")
    return bancos[bancos["entidad"].isin(incluidos)].copy()


def validar(panel: pd.DataFrame) -> None:
    """Controles de calidad con identidades contables y regulatorias."""
    diferencia = (panel["activo_total"] - panel["pasivo_total"] - panel["patrimonio"]).abs()
    anotar(f"Identidad activo = pasivo + patrimonio: diferencia máxima {diferencia.max():.3f} "
           f"miles de S/ · filas fuera de tolerancia: {int((diferencia > TOLERANCIA_IDENTIDAD).sum())}")

    ratio = 100 * panel["patrimonio_efectivo"] / panel["apr_total"]
    brecha = (ratio - panel["ratio_capital_global"]).abs()
    anotar(f"Identidad ratio de capital global = PE / APR: diferencia máxima {brecha.max():.4f} p. p. · "
           f"filas fuera de tolerancia ({TOLERANCIA_RATIO} p. p.): {int((brecha > TOLERANCIA_RATIO).sum())}")

    modalidades = panel[["vig_tarjetas", "vig_prestamos", "vig_hipotecarios",
                         "vig_comercio_exterior", "vig_arrendamiento"]].sum(axis=1)
    exceso = int((modalidades > panel["creditos_vigentes"] + TOLERANCIA_IDENTIDAD).sum())
    anotar(f"Suma de modalidades <= crédito vigente: filas que no la cumplen: {exceso}")

    cet1 = panel.loc[panel["ratio_cet1"].notna(), "fecha"]
    anotar(f"Ratio CET1 publicado desde {cet1.min() if len(cet1) else '—'} "
           f"({panel['ratio_cet1'].notna().sum()} observaciones banco-mes)")


# ---------------------------------------------------------------------------
# 5. Variables del estudio
# ---------------------------------------------------------------------------
def construir_variables(panel: pd.DataFrame) -> pd.DataFrame:
    """Montos en millones de soles y variables que usa el análisis."""
    for columna in MONTOS:
        panel[columna] = panel[columna] / 1000  # miles de S/ -> millones de S/

    deflactor = panel["ipc_lima"] / 100
    panel["creditos_directos"] = (panel["creditos_vigentes"] + panel["creditos_refinanciados"]
                                  + panel["creditos_atrasados"])
    panel["credito_real"] = panel["creditos_directos"] / deflactor
    panel["activo_real"] = panel["activo_total"] / deflactor

    # Variable central: excedente de capital sobre el mínimo legal vigente (p. p.)
    panel["excedente_capital"] = panel["ratio_capital_global"] - panel["limite_global"]

    # Densidad de los APR: cuánto riesgo ponderado hay por cada sol de activo (%)
    panel["densidad_apr"] = 100 * panel["apr_total"] / panel["activo_total"]

    # Composición, dolarización, fondeo y liquidez (% del total respectivo)
    vigentes = panel["creditos_vigentes"]
    panel["part_hipotecario"] = 100 * panel["vig_hipotecarios"] / vigentes
    panel["part_tarjetas"] = 100 * panel["vig_tarjetas"] / vigentes
    panel["part_prestamos"] = 100 * panel["vig_prestamos"] / vigentes
    panel["dolarizacion_credito"] = 100 * panel["creditos_vigentes_me"] / vigentes
    panel["depositos_activo"] = 100 * panel["obligaciones_publico"] / panel["activo_total"]
    panel["liquidez"] = 100 * panel["disponible"] / panel["activo_total"]
    panel["apalancamiento"] = panel["activo_total"] / panel["patrimonio"]
    return panel


# ---------------------------------------------------------------------------
# 6. Programa principal
# ---------------------------------------------------------------------------
COLUMNAS_FINALES = [
    # llave
    "entidad", "fecha", "anio", "mes",
    # balance y crédito (millones de S/)
    "activo_total", "pasivo_total", "patrimonio", "activo_real", "disponible", "inversiones",
    "creditos_directos", "credito_real", "creditos_vigentes", "creditos_vigentes_me",
    "vig_prestamos", "vig_hipotecarios", "vig_tarjetas", "vig_comercio_exterior", "vig_arrendamiento",
    "creditos_refinanciados", "creditos_atrasados", "provisiones", "obligaciones_publico",
    "depositos_sistema_financiero", "adeudos", "capital_social", "contingentes",
    # capital regulatorio
    "req_credito", "req_mercado", "req_operacional", "apr_credito", "apr_total", "patrimonio_efectivo",
    "ratio_capital_global", "ratio_cet1", "limite_global", "excedente_capital", "densidad_apr",
    # indicadores (%)
    "morosidad", "part_prestamos", "part_hipotecario", "part_tarjetas", "dolarizacion_credito",
    "depositos_activo", "liquidez", "apalancamiento",
    # macro (BCRP)
    "tasa_referencia", "tamn", "tipmn", "margen_tamn_tipmn", "ipc_lima", "pbi_desestacionalizado",
    "credito_privado",
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    for entrada in (ENTRADA_BCRP, ENTRADA_SBS):
        if not entrada.exists():
            print(f"Falta {entrada.relative_to(RAIZ)}: ejecutar antes los scripts 01 y 02.")
            return 1

    CARPETA_PROCESADOS.mkdir(exist_ok=True)
    anotar("Inicio de la limpieza e integración de datos")

    macro = preparar_bcrp()
    bancos = seleccionar_panel_balanceado(reparar_apr(preparar_sbs()))
    bancos["fecha"] = fecha_texto(bancos)
    bancos = bancos[(bancos["fecha"] >= FECHA_INICIO) & (bancos["fecha"] <= FECHA_CORTE)]

    # Unión por la fecha: cada banco-mes recibe las series macro de ese mes
    panel = bancos.merge(macro.drop(columns=["anio", "mes"]), on="fecha", how="left", validate="many_to_one")
    anotar(f"Unión SBS + BCRP por fecha: {len(panel)} filas · filas sin dato macro: "
           f"{int(panel['tasa_referencia'].isna().sum())}")
    validar(panel)

    panel = construir_variables(panel)
    panel = panel[COLUMNAS_FINALES].sort_values(["entidad", "fecha"]).reset_index(drop=True)
    if panel.duplicated(["entidad", "fecha"]).any():
        anotar("ERROR: hay filas repetidas para la llave entidad + fecha")
        return 1
    vacios = panel.drop(columns=["ratio_cet1"]).isna().sum()
    anotar(f"Valores vacíos (sin contar CET1, que se publica desde 2023): "
           f"{vacios[vacios > 0].to_dict() or 'ninguno'}")
    bajo_minimo = panel[panel["excedente_capital"] < 0]
    anotar(f"Banco-mes con ratio de capital global por debajo del límite: {len(bajo_minimo)} "
           f"{bajo_minimo.groupby('entidad').size().to_dict()}")

    columnas_macro = ["fecha", "anio", "mes", "tasa_referencia", "tamn", "tipmn", "margen_tamn_tipmn",
                      "ipc_lima", "pbi_desestacionalizado", "credito_privado", "limite_global"]
    macro = macro[columnas_macro].sort_values("fecha").reset_index(drop=True)

    # Formato fijo (6 decimales y saltos de línea '\n') para que los archivos,
    # y por tanto sus hashes, sean idénticos en Windows, macOS y Linux.
    panel.to_csv(SALIDA, index=False, encoding="utf-8", float_format="%.6f", lineterminator="\n")
    macro.to_csv(SALIDA_MACRO, index=False, encoding="utf-8", float_format="%.6f", lineterminator="\n")
    huella = hashlib.sha256(SALIDA.read_bytes()).hexdigest()
    huella_macro = hashlib.sha256(SALIDA_MACRO.read_bytes()).hexdigest()
    SALIDA_HASH.write_text(f"{huella}  {SALIDA.name}\n{huella_macro}  {SALIDA_MACRO.name}\n", encoding="utf-8")

    anotar(f"Archivo final: {SALIDA.relative_to(RAIZ).as_posix()} · {len(panel)} filas × {panel.shape[1]} columnas · "
           f"{panel['entidad'].nunique()} bancos · {panel['fecha'].nunique()} meses "
           f"({panel['fecha'].min()} a {panel['fecha'].max()})")
    anotar(f"Series macro: {SALIDA_MACRO.relative_to(RAIZ).as_posix()} · {len(macro)} meses")
    anotar(f"SHA-256 del panel: {huella}")
    anotar(f"SHA-256 de las series macro: {huella_macro}")
    anotar("Limpieza terminada sin errores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
