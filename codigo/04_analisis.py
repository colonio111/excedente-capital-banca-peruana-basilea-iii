# Autora: Lucia Pamela Colonio Yaringaño
# Código de matrícula: 2024200495A
# Artículo II (complementario al Tema N.º 85 de la Unidad II): Excedente de capital
#   regulatorio y oferta de crédito de la banca múltiple peruana en la transición a Basilea III
# Fecha de extracción: 2026-11-25
"""
04_analisis.py · Análisis descriptivo y econométrico del Artículo II.

Pregunta: ¿el excedente de capital de cada banco sobre el mínimo legal vigente
condiciona su oferta de crédito, su respuesta a la política monetaria y su forma
de ajustarse cuando el regulador sube el requerimiento (transición a Basilea III)?

Entradas (generadas por 03_limpieza_datos.py):
    datos_procesados/datos_procesados_2024200495A.csv   panel de 15 bancos × 120 meses
    datos_procesados/macro_mensual_2024200495A.csv      series del BCRP 2010-01 a 2025-12

Bloques (cada uno genera sus tablas y figuras en /salidas):
    1. Fuentes y marco regulatorio
         tabla_fuentes.csv             fuentes, códigos y uso de cada variable
         tabla_limite_global.csv       tramos del límite global y normas
         fig_marco_regulatorio.svg     límite global, ratios del sistema y tasas de interés
    2. Análisis descriptivo
         tabla_descriptivos.csv        estadística descriptiva (entre y dentro de bancos)
         tabla_bancos.csv              perfil de los 15 bancos y grupo de exposición
         fig_excedente_bancos.svg      excedente de capital por banco y año
         fig_densidad_apr.svg          densidad de los APR y crecimiento del crédito
    3. H1 · Excedente de capital y crecimiento del crédito
         tabla_h1_excedente.csv        efectos fijos con errores de Driscoll y Kraay
         fig_h1_dispersion.svg         relación parcial (binscatter) excedente-crédito
    4. H2 · Canal del capital bancario de la política monetaria
         tabla_h2_proyecciones.csv     proyecciones locales (Jordà, 2005) en panel
         fig_h2_proyecciones.svg       respuesta del crédito a un alza de la tasa
    5. H3 · Transición a Basilea III (estudio de eventos y diferencias en diferencias)
         tabla_h3_did.csv              diferencias en diferencias con exposición al alza del límite
         tabla_h3_eventos.csv          coeficientes trimestrales del estudio de eventos
         fig_h3_eventos.svg            estudio de eventos: crédito, densidad APR y ratio de capital
    6. H4 · Márgenes de ajuste del ratio de capital (Cohen y Scatigna, 2016)
         tabla_h4_descomposicion.csv   capital, densidad de los APR y tamaño del balance
         fig_h4_descomposicion.svg     contribuciones por grupo y periodo
    7. Robustez
         tabla_robustez.csv            H1 y H3 con especificaciones alternativas y placebo
         fig_correlaciones.svg         matriz de correlaciones
         fig_capital_bancos.svg        ratio de capital y límite global por banco (anexo)
         fig_robustez.svg              coeficientes de robustez con IC 95 % (anexo)

Método (implementado con numpy y scipy, sin cajas negras):
    - Efectos fijos por banco (transformación within) y por mes (variables
      indicadoras), estimados por MCO.
    - Errores de Driscoll y Kraay (1998): robustos a heterocedasticidad,
      autocorrelación y dependencia entre bancos.
    - Proyecciones locales en panel con interacción banco × política (Jordà, 2005;
      Kashyap y Stein, 2000).
    - Estudio de eventos con exposición previa al alza del requerimiento.

Ejecución (desde la carpeta raíz del repositorio):
    python codigo/04_analisis.py      (en Windows sin PATH: py codigo/04_analisis.py)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # dibuja sin abrir ventanas (funciona en cualquier computadora)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# 1. Parámetros
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200495A"
SEMILLA = 495
FECHA_INICIO = "2016-01"
FECHA_CORTE = "2025-12"

HAMILTON_H, HAMILTON_P = 24, 12        # filtro de Hamilton (2018) para datos mensuales
PANDEMIA = ("2020-03", "2021-12")

REZAGO_EXCEDENTE = 12                  # H1: excedente medido 12 meses antes
PESO_MINIMO_MODALIDAD = 5.0            # H1: % mínimo de la cartera para estimar por modalidad
HORIZONTE_LP = 24                      # H2: meses de las proyecciones locales
INICIO_ALZA = "2023-04"                # H3: primer mes del alza escalonada del límite global
VENTANA_EXPOSICION = ("2022-09", "2023-03")  # H3: meses con que se mide la exposición previa
VENTANA_H3 = ("2021-04", "2025-12")    # H3: desde el régimen flexible (D. U. 037-2021)
TRIMESTRE_BASE = "2023Q1"              # H3: trimestre de referencia del estudio de eventos
PERIODOS_H4 = {                        # H4: tramos de la descomposición
    "Flexibilización\n2021-03 a 2023-03": ("2021-03", "2023-03"),
    "Alza a Basilea III\n2023-03 a 2025-12": ("2023-03", "2025-12"),
}
PLACEBO = ("2017-01", "2019-12", "2018-07")  # H3: ventana y fecha ficticia del placebo
# Banco que estuvo por debajo del límite global y en recapitalización: su capital
# no lo decide el banco sino el plan de recuperación, por lo que se excluye de la
# comparación de H3 y H4 (se incluye en la robustez)
EN_RECAPITALIZACION = ["Alfin Banco"]

# Tramos del límite global y normas (los mismos de 03_limpieza_datos.py)
NORMAS_LIMITE = [
    ("Hasta 2021-03", "10,0", "Ley 26702, art. 199 (régimen previo)"),
    ("2021-04 a 2022-08", "8,0", "D. U. 037-2021 y D. U. 003-2022 (flexibilización por la pandemia)"),
    ("2022-09 a 2023-03", "8,5", "D. U. 003-2022; Res. SBS 3952-2022 (inicio de la adecuación)"),
    ("2023-04 a 2024-08", "9,0", "Res. SBS 3952-2022, prorrogada por Res. SBS 2192-2023 y 274-2024"),
    ("2024-09 a 2025-02", "9,5", "Res. SBS 274-2024"),
    ("Desde 2025-03", "10,0", "Res. SBS 274-2024 (D. L. 1531, adecuación a Basilea III)"),
]

EVENTOS = {                            # fecha: (texto, alineación, altura en fracción del eje)
    "2021-04": ("Límite baja a 8 %", "right", 0.99),
    "2023-01": ("Ponderadores Basilea III", "right", 0.91),
    "2023-04": ("Alza del límite", "left", 0.99),
}

# Estilo común de las figuras (el mismo del Artículo I)
AZUL = "#1f3a5f"
DORADO = "#c49a2c"
ROJO = "#a23b3b"
VERDE = "#3c7a5a"
GRIS = "#8a8f98"
GRIS_CLARO = "#e6e8eb"
ANCHO_UNA_COLUMNA = 3.4
ANCHO_DOS_COLUMNAS = 7.0

# ---------------------------------------------------------------------------
# 2. Rutas relativas a la carpeta del proyecto
# ---------------------------------------------------------------------------
if "__file__" in globals():
    RAIZ = Path(__file__).resolve().parent.parent
else:
    RAIZ = Path.cwd()
CARPETA_PROCESADOS = RAIZ / "datos_procesados"
CARPETA_SALIDAS = RAIZ / "salidas"
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"
ENTRADA_PANEL = CARPETA_PROCESADOS / f"datos_procesados_{CODIGO_MATRICULA}.csv"
ENTRADA_MACRO = CARPETA_PROCESADOS / f"macro_mensual_{CODIGO_MATRICULA}.csv"


def anotar(mensaje: str) -> None:
    """Muestra el mensaje en consola y lo añade al log con fecha y hora."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [04_analisis] {mensaje}"
    print(linea)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as log:
        log.write(linea + "\n")


def guardar_tabla(tabla: pd.DataFrame, nombre: str) -> None:
    """Guarda una tabla en /salidas con formato fijo (igual en cualquier sistema)."""
    tabla.to_csv(CARPETA_SALIDAS / nombre, index=False, encoding="utf-8", lineterminator="\n")
    anotar(f"Tabla guardada: salidas/{nombre} · {len(tabla)} filas")


def configurar_graficos() -> None:
    """Estilo sobrio y uniforme para todas las figuras del artículo."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8,
        "axes.titlesize": 8.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 8, "axes.edgecolor": GRIS, "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRIS_CLARO, "grid.linewidth": 0.5,
        "xtick.color": "#333333", "ytick.color": "#333333",
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5, "legend.frameon": False, "lines.linewidth": 1.3,
        "svg.fonttype": "path", "svg.hashsalt": CODIGO_MATRICULA,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
    })


def coma_decimal(figura: plt.Figure) -> None:
    """Números de los ejes con coma decimal (0,85), como en el texto del artículo."""
    from matplotlib.ticker import ScalarFormatter

    class FormatoComa(ScalarFormatter):
        def __call__(self, valor, posicion=None):
            return super().__call__(valor, posicion).replace(".", ",")

    for eje in figura.axes:
        for eje_xy in (eje.xaxis, eje.yaxis):
            if type(eje_xy.get_major_formatter()) is ScalarFormatter:
                eje_xy.set_major_formatter(FormatoComa())


def guardar_figura(figura: plt.Figure, nombre: str) -> None:
    """Guarda la figura en SVG (vectorial) y en PNG (para el dashboard y los videos)."""
    coma_decimal(figura)
    figura.savefig(CARPETA_SALIDAS / nombre, format="svg", metadata={"Date": None})
    figura.savefig(CARPETA_SALIDAS / nombre.replace(".svg", ".png"), format="png", dpi=200)
    plt.close(figura)
    anotar(f"Figura guardada: salidas/{nombre}")


def ejes_anuales(*ejes: plt.Axes, paso: int = 2) -> None:
    """Fechas del eje x cada `paso` años, para que las etiquetas no se encimen en paneles angostos."""
    import matplotlib.dates as mdates
    for eje in ejes:
        eje.xaxis.set_major_locator(mdates.YearLocator(paso))
        eje.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def sombrear_pandemia(eje: plt.Axes) -> None:
    eje.axvspan(pd.Timestamp(PANDEMIA[0]), pd.Timestamp(PANDEMIA[1]) + pd.offsets.MonthEnd(0),
                color=GRIS_CLARO, alpha=0.8, lw=0, zorder=0)


def marcar_eventos(eje: plt.Axes, con_texto: bool = True) -> None:
    """Líneas punteadas en las fechas de EVENTOS; los textos se escalonan para no encimarse."""
    for fecha, (texto, alineacion, altura) in EVENTOS.items():
        eje.axvline(pd.Timestamp(fecha), color=GRIS, lw=0.7, ls=":", zorder=1)
        if con_texto:
            eje.annotate(texto, (pd.Timestamp(fecha), altura), xycoords=("data", "axes fraction"),
                         xytext=(-2 if alineacion == "right" else 2, 0), textcoords="offset points",
                         ha=alineacion, va="top", fontsize=5.8, color="#555555")


def miles(valor: float, decimales: int = 2) -> str:
    """Número con coma decimal y espacio como separador de miles: 12 345,67."""
    return f"{valor:,.{decimales}f}".replace(",", " ").replace(".", ",")


# ---------------------------------------------------------------------------
# 3. Herramientas econométricas
# ---------------------------------------------------------------------------
def rezagos_driscoll_kraay(meses: int) -> int:
    """Ancho de banda habitual (Hoechle, 2007): parte entera de 4·(T/100)^(2/9)."""
    return int(np.floor(4 * (meses / 100) ** (2 / 9)))


def estimar_panel(datos: pd.DataFrame, y: str, xs: list[str], efectos_tiempo: bool = True,
                  rezagos: int | None = None, tendencias_banco: bool = False) -> dict:
    """
    MCO con efectos fijos por banco (transformación within) y, si se pide, por
    mes (variables indicadoras, que funcionan también si el panel queda
    desbalanceado). Con tendencias_banco=True se añade una tendencia lineal
    propia de cada banco. Errores estándar de Driscoll y Kraay e inferencia con
    T-1 grados de libertad. Devuelve solo los coeficientes de 'xs'.
    """
    d = datos.dropna(subset=[y] + xs).copy()
    columnas = list(xs)
    extras = []
    if efectos_tiempo:
        extras.append(pd.get_dummies(d["fecha"], prefix="m", drop_first=True, dtype=float))
    if tendencias_banco:
        t = pd.to_datetime(d["fecha"]).dt.year * 12 + pd.to_datetime(d["fecha"]).dt.month
        extras.append(pd.get_dummies(d["entidad"], prefix="tb", dtype=float).mul(t - t.mean(), axis=0))
    for extra in extras:
        d = pd.concat([d, extra], axis=1)
        columnas += list(extra.columns)
    todas = [y] + columnas
    d[todas] = d[todas] - d.groupby("entidad")[todas].transform("mean")

    Y = d[y].to_numpy(dtype=float)
    X = d[columnas].to_numpy(dtype=float)
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ Y
    residuos = Y - X @ beta

    momentos = pd.DataFrame(X * residuos[:, None], index=d["fecha"].to_numpy()).groupby(level=0).sum()
    h = momentos.sort_index().to_numpy()
    T = h.shape[0]
    m = rezagos if rezagos is not None else rezagos_driscoll_kraay(T)
    S = h.T @ h
    for j in range(1, m + 1):
        G = h[j:].T @ h[:-j]
        S += (1 - j / (m + 1)) * (G + G.T)
    n_obs, k = X.shape
    bancos = d["entidad"].nunique()
    ajuste = (n_obs - 1) / (n_obs - k - bancos) * T / (T - 1)
    V = ajuste * XtX_inv @ S @ XtX_inv
    k_x = len(xs)
    errores = np.sqrt(np.diag(V)[:k_x])
    t = beta[:k_x] / errores
    p = 2 * stats.t.sf(np.abs(t), df=T - 1)
    r2 = 1 - (residuos @ residuos) / ((Y - Y.mean()) @ (Y - Y.mean()))
    return {"coef": dict(zip(xs, beta[:k_x])), "ee": dict(zip(xs, errores)), "p": dict(zip(xs, p)),
            "n": n_obs, "bancos": bancos, "meses": T, "r2_within": r2, "rezagos_dk": m,
            "efectos_tiempo": efectos_tiempo, "gl": T - 1}


def estrellas(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def tabla_de_modelos(modelos: dict[str, dict], etiquetas: dict[str, str],
                     filas_extra: dict[str, list[str]]) -> pd.DataFrame:
    """Un modelo por columna: coeficiente con estrellas y su error estándar entre paréntesis."""
    filas = []
    for variable, etiqueta in etiquetas.items():
        coeficientes, errores = [etiqueta], [""]
        for modelo in modelos.values():
            if variable in modelo["coef"]:
                coeficientes.append(f"{modelo['coef'][variable]:.3f}{estrellas(modelo['p'][variable])}")
                errores.append(f"({modelo['ee'][variable]:.3f})")
            else:
                coeficientes.append("")
                errores.append("")
        filas += [coeficientes, errores]
    filas.append(["Observaciones"] + [miles(m["n"], 0) for m in modelos.values()])
    filas.append(["Bancos"] + [str(m["bancos"]) for m in modelos.values()])
    filas.append(["Meses"] + [str(m["meses"]) for m in modelos.values()])
    filas.append(["R² within"] + [f"{m['r2_within']:.3f}" for m in modelos.values()])
    for nombre, valores in filas_extra.items():
        filas.append([nombre] + valores)
    return pd.DataFrame(filas, columns=["Variable"] + list(modelos))


def filtro_hamilton(serie: pd.Series, h: int = HAMILTON_H, p: int = HAMILTON_P) -> pd.Series:
    """
    Filtro de Hamilton (2018): y(t+h) = b0 + b1·y(t) + ... + bp·y(t-p+1) + v(t+h).
    La brecha es el residuo v(t+h). Con y = 100·ln(x), se lee en % de desviación.
    """
    y = serie.to_numpy(dtype=float)
    filas = list(range(h + p - 1, len(y)))
    X = np.column_stack([np.ones(len(filas))] + [y[[t - h - j for t in filas]] for j in range(p)])
    Y = y[filas]
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    brecha = pd.Series(np.nan, index=serie.index)
    brecha.iloc[filas] = Y - X @ coef
    return brecha


# ---------------------------------------------------------------------------
# 4. Carga y variables de trabajo
# ---------------------------------------------------------------------------
def cargar_datos() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Panel con las variables de trabajo (logaritmos, tasas de crecimiento y rezagos)."""
    macro = pd.read_csv(ENTRADA_MACRO)
    macro["brecha_pbi"] = filtro_hamilton(100 * np.log(macro["pbi_desestacionalizado"])).to_numpy()
    macro["d_tasa"] = macro["tasa_referencia"].diff()
    macro["d12_tasa"] = macro["tasa_referencia"].diff(12)

    panel = pd.read_csv(ENTRADA_PANEL)
    panel = panel.merge(macro[["fecha", "brecha_pbi", "d_tasa", "d12_tasa"]], on="fecha", how="left",
                        validate="many_to_one")
    panel = panel.sort_values(["entidad", "fecha"]).reset_index(drop=True)
    panel["fecha_dt"] = pd.to_datetime(panel["fecha"])
    panel["trimestre"] = panel["fecha_dt"].dt.to_period("Q").astype(str)
    g = panel.groupby("entidad")

    deflactor = panel["ipc_lima"] / 100
    panel["ln_credito"] = 100 * np.log(panel["credito_real"])
    for modalidad in ["hipotecarios", "prestamos", "tarjetas"]:
        real = panel[f"vig_{modalidad}"] / deflactor
        panel[f"ln_{modalidad}"] = 100 * np.log(real.where(real > 0))
    panel["ln_activo_real"] = np.log(panel["activo_real"])
    panel["capital_activo"] = 100 * panel["patrimonio_efectivo"] / panel["activo_total"]

    # Crecimiento real a 12 meses y mensual (en %, aproximado por diferencias logarítmicas)
    for v in ["ln_credito", "ln_hipotecarios", "ln_prestamos", "ln_tarjetas"]:
        panel[f"d12_{v}"] = panel[v] - g[v].shift(12)
    # Por modalidad solo se usan los bancos para los que esa cartera es relevante
    # (al menos PESO_MINIMO_MODALIDAD % del crédito vigente un año antes)
    for modalidad in ["hipotecarios", "prestamos", "tarjetas"]:
        peso_previo = g[f"vig_{modalidad}"].shift(12) / g["creditos_vigentes"].shift(12) * 100
        panel.loc[~(peso_previo >= PESO_MINIMO_MODALIDAD), f"d12_ln_{modalidad}"] = np.nan
    panel["d1_ln_credito"] = panel["ln_credito"] - g["ln_credito"].shift(1)

    # Rezagos de las variables bancarias
    for v in ["excedente_capital", "ln_activo_real", "morosidad", "liquidez", "depositos_activo",
              "densidad_apr", "part_hipotecario", "dolarizacion_credito"]:
        panel[f"{v}_l12"] = g[v].shift(12)
        panel[f"{v}_l6"] = g[v].shift(6)
        panel[f"{v}_l1"] = g[v].shift(1)
    return panel, macro


# ---------------------------------------------------------------------------
# 5. Bloque 1 · Fuentes y marco regulatorio
# ---------------------------------------------------------------------------
def tabla_fuentes() -> pd.DataFrame:
    filas = [
        ("Vía 1 · API REST", "BCRP (BCRPData)", "PD04722MM", "Tasa de referencia", "%", "Choque de política (H2)"),
        ("Vía 1 · API REST", "BCRP (BCRPData)", "PN07807NM", "Tasa activa promedio en MN (TAMN)", "%", "Precio del crédito (Figura 1)"),
        ("Vía 1 · API REST", "BCRP (BCRPData)", "PN07816NM", "Tasa pasiva promedio en MN (TIPMN)", "%", "Margen de intermediación (Figura 1)"),
        ("Vía 1 · API REST", "BCRP (BCRPData)", "PN38705PM", "IPC de Lima Metropolitana", "Índice dic. 2021 = 100", "Deflactor del crédito"),
        ("Vía 1 · API REST", "BCRP (BCRPData)", "PN01773AM", "PBI desestacionalizado", "Índice 2007 = 100", "Brecha del producto (control)"),
        ("Vía 1 · API REST", "BCRP (BCRPData)", "PN00505MM", "Crédito al sector privado", "Millones de S/", "Contraste agregado"),
        ("Vía 2 · Descarga programática", "SBS", "B-2201", "Balance: crédito por modalidad y moneda, fondeo, liquidez", "Millones de S/", "Crédito real y controles (H1-H4)"),
        ("Vía 2 · Descarga programática", "SBS", "B-2401", "Indicadores financieros: morosidad", "%", "Control de riesgo de crédito"),
        ("Vía 2 · Descarga programática", "SBS", "B-2402", "Requerimientos, APR, patrimonio efectivo, ratios de capital", "Millones de S/ y %", "Excedente de capital y densidad APR"),
    ]
    return pd.DataFrame(filas, columns=["Vía", "Fuente", "Código", "Variable", "Unidad", "Uso en el estudio"])


def serie_sistema(panel: pd.DataFrame) -> pd.DataFrame:
    """Agregados del sistema (los ratios se calculan con sumas, no con promedios simples)."""
    suma = panel.groupby("fecha")[["patrimonio_efectivo", "apr_total", "activo_total", "credito_real"]].sum()
    s = pd.DataFrame(index=suma.index)
    s["ratio_capital_global"] = 100 * suma["patrimonio_efectivo"] / suma["apr_total"]
    s["densidad_apr"] = 100 * suma["apr_total"] / suma["activo_total"]
    s["credito_real"] = suma["credito_real"]
    s["crec_credito"] = 100 * np.log(suma["credito_real"]).diff(12)
    cet1 = panel.dropna(subset=["ratio_cet1"])
    s["ratio_cet1"] = (cet1.assign(pond=cet1["ratio_cet1"] * cet1["apr_total"]).groupby("fecha")["pond"].sum()
                       / cet1.groupby("fecha")["apr_total"].sum())
    primero = panel.drop_duplicates("fecha").set_index("fecha")
    for c in ["limite_global", "tasa_referencia", "tamn", "tipmn", "margen_tamn_tipmn"]:
        s[c] = primero[c]
    s["excedente_sistema"] = s["ratio_capital_global"] - s["limite_global"]
    s.index = pd.to_datetime(s.index)
    return s


def figura_marco(s: pd.DataFrame) -> plt.Figure:
    """Figura 1: límite global, ratios de capital del sistema y tasas de interés (BCRP)."""
    figura, (a, b) = plt.subplots(1, 2, figsize=(ANCHO_DOS_COLUMNAS, 2.6), gridspec_kw={"wspace": 0.28})
    a.step(s.index, s["limite_global"], where="post", color=ROJO, lw=1.5, label="Límite global (mínimo legal)")
    a.plot(s.index, s["ratio_capital_global"], color=AZUL, label="Ratio de capital global del sistema")
    a.plot(s.index, s["ratio_cet1"], color=DORADO, label="Ratio CET1 del sistema")
    a.fill_between(s.index, s["limite_global"], s["ratio_capital_global"], color=AZUL, alpha=0.08, lw=0)
    a.set_title("A. Capital regulatorio (% de los APR)")
    a.set_ylim(0, 1.22 * s["ratio_capital_global"].max())
    marcar_eventos(a)
    a.legend(loc="lower left", fontsize=6.5)
    b.plot(s.index, s["tamn"], color=AZUL, label="TAMN (activa)")
    b.plot(s.index, s["tipmn"], color=DORADO, label="TIPMN (pasiva)")
    b.step(s.index, s["tasa_referencia"], where="post", color=ROJO, label="Tasa de referencia")
    b.set_title("B. Tasas de interés en moneda nacional (%)")
    sombrear_pandemia(b)
    b.legend(loc="center left", fontsize=6.5)
    ejes_anuales(a, b)
    return figura


def bloque_1(panel: pd.DataFrame) -> pd.DataFrame:
    anotar("Bloque 1 · Fuentes y marco regulatorio")
    guardar_tabla(tabla_fuentes(), "tabla_fuentes.csv")
    guardar_tabla(pd.DataFrame(NORMAS_LIMITE, columns=["Periodo", "Límite global (%)", "Norma"]),
                  "tabla_limite_global.csv")
    s = serie_sistema(panel)
    guardar_figura(figura_marco(s), "fig_marco_regulatorio.svg")
    s.reset_index().assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m")).round(4).to_csv(
        CARPETA_SALIDAS / "serie_sistema.csv", index=False, encoding="utf-8", lineterminator="\n")
    ultimo = s.iloc[-1]
    anotar(f"Sistema 2025-12: ratio de capital global {ultimo['ratio_capital_global']:.2f} % · "
           f"CET1 {ultimo['ratio_cet1']:.2f} % · límite {ultimo['limite_global']:.1f} % · "
           f"densidad APR {ultimo['densidad_apr']:.2f} %")
    return s


# ---------------------------------------------------------------------------
# 6. Bloque 2 · Análisis descriptivo
# ---------------------------------------------------------------------------
VARIABLES_DESCRIPTIVAS = {
    "d12_ln_credito": ("Crecimiento real del crédito (12 m)", "%"),
    "ratio_capital_global": ("Ratio de capital global", "%"),
    "excedente_capital": ("Excedente sobre el límite global", "p. p."),
    "ratio_cet1": ("Ratio CET1 (desde 2023)", "%"),
    "densidad_apr": ("Densidad de los APR", "% del activo"),
    "capital_activo": ("Patrimonio efectivo / activo", "%"),
    "morosidad": ("Morosidad", "%"),
    "liquidez": ("Disponible / activo", "%"),
    "depositos_activo": ("Depósitos del público / activo", "%"),
    "part_hipotecario": ("Hipotecario / crédito vigente", "%"),
    "dolarizacion_credito": ("Crédito en moneda extranjera", "% del vigente"),
    "ln_activo_real": ("ln activo real", "ln mill. S/"),
}


def tabla_descriptivos(panel: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for columna, (nombre, unidad) in VARIABLES_DESCRIPTIVAS.items():
        x = panel[columna]
        filas.append({
            "Variable": nombre, "Unidad": unidad, "N": int(x.count()),
            "Media": x.mean(), "D.E.": x.std(),
            "D.E. entre bancos": panel.groupby("entidad")[columna].mean().std(),
            "D.E. dentro": (x - panel.groupby("entidad")[columna].transform("mean")).std(),
            "Mín.": x.min(), "Mediana": x.median(), "Máx.": x.max(),
        })
    tabla = pd.DataFrame(filas)
    numericas = tabla.columns.drop(["Variable", "Unidad", "N"])
    tabla[numericas] = tabla[numericas].map(lambda v: f"{v:.2f}")
    return tabla


def exposicion_por_banco(panel: pd.DataFrame, excluir: list[str] | None = EN_RECAPITALIZACION) -> pd.DataFrame:
    """
    Exposición al alza del límite global: excedente promedio en los siete meses
    previos (2022-09 a 2023-03). 'Bajo excedente' = por debajo de la mediana.
    La versión continua se estandariza con signo invertido: más alto = más expuesto.
    """
    previo = panel[panel["fecha"].between(*VENTANA_EXPOSICION) & ~panel["entidad"].isin(excluir or [])]
    e = previo.groupby("entidad")["excedente_capital"].mean().rename("excedente_previo").to_frame()
    e["bajo_excedente"] = (e["excedente_previo"] < e["excedente_previo"].median()).astype(int)
    e["exposicion_z"] = -(e["excedente_previo"] - e["excedente_previo"].mean()) / e["excedente_previo"].std()
    return e


def tabla_bancos(panel: pd.DataFrame, exposicion: pd.DataFrame) -> pd.DataFrame:
    ultimo = panel[panel["fecha"] == FECHA_CORTE].set_index("entidad")
    participacion = 100 * ultimo["activo_total"] / ultimo["activo_total"].sum()
    previo = panel[panel["fecha"].between(*VENTANA_EXPOSICION)].groupby("entidad")["excedente_capital"].mean()
    filas = []
    for banco in participacion.sort_values(ascending=False).index:
        b = panel[panel["entidad"] == banco]
        filas.append({
            "Banco": banco,
            "Participación en el activo 2025-12 (%)": f"{participacion[banco]:.2f}",
            "Ratio de capital global promedio (%)": f"{b['ratio_capital_global'].mean():.2f}",
            "Excedente previo 2022-09 a 2023-03 (p. p.)": f"{previo[banco]:.2f}",
            "Grupo": ("En recapitalización (fuera de H3-H4)" if banco not in exposicion.index else
                      "Bajo excedente" if exposicion.loc[banco, "bajo_excedente"] else "Alto excedente"),
            "CET1 2025-12 (%)": f"{ultimo.loc[banco, 'ratio_cet1']:.2f}",
            "Densidad APR promedio (%)": f"{b['densidad_apr'].mean():.2f}",
            "Crecimiento real del crédito promedio (%)": f"{b['d12_ln_credito'].mean():.2f}",
        })
    return pd.DataFrame(filas)


def figura_excedente_bancos(panel: pd.DataFrame) -> plt.Figure:
    """Figura 2: excedente de capital promedio por banco y año (p. p. sobre el límite)."""
    anual = panel.pivot_table(index="entidad", columns="anio", values="excedente_capital", aggfunc="mean")
    anual = anual.loc[panel.groupby("entidad")["activo_total"].mean().sort_values(ascending=False).index]
    figura, eje = plt.subplots(figsize=(ANCHO_DOS_COLUMNAS, 4.0))
    limite = 12.0   # escala acotada a ±12 p. p. para que el ICBC (≈30 p. p.) no oculte las diferencias del resto
    imagen = eje.imshow(anual.to_numpy(), cmap="RdYlBu", vmin=-limite, vmax=limite, aspect="auto")
    eje.set_xticks(range(anual.shape[1]), anual.columns)
    eje.set_yticks(range(anual.shape[0]), anual.index)
    eje.tick_params(length=0)
    eje.grid(False)
    for lado in eje.spines.values():
        lado.set_visible(False)
    for i in range(anual.shape[0]):
        for j in range(anual.shape[1]):
            v = anual.iat[i, j]
            eje.text(j, i, f"{v:.1f}".replace(".", ","), ha="center", va="center", fontsize=6.6,
                     color="white" if abs(v) > 0.75 * limite else "#1a1a1a")
    barra = figura.colorbar(imagen, ax=eje, fraction=0.025, pad=0.01, extend="both")
    barra.set_label("p. p. sobre el límite global")
    barra.outline.set_visible(False)
    return figura


def figura_densidad(s: pd.DataFrame, panel: pd.DataFrame, exposicion: pd.DataFrame) -> plt.Figure:
    """Figura 3: densidad de los APR y crecimiento real del crédito por grupo de exposición."""
    p = panel.merge(exposicion[["bajo_excedente"]], left_on="entidad", right_index=True)
    figura, (a, b) = plt.subplots(1, 2, figsize=(ANCHO_DOS_COLUMNAS, 2.5), gridspec_kw={"wspace": 0.25})
    a.plot(s.index, s["densidad_apr"], color=AZUL, label="Sistema")
    for grupo, color, etiqueta in [(1, ROJO, "Bajo excedente"), (0, VERDE, "Alto excedente")]:
        g = p[p["bajo_excedente"] == grupo].groupby("fecha")[["apr_total", "activo_total"]].sum()
        a.plot(pd.to_datetime(g.index), 100 * g["apr_total"] / g["activo_total"], color=color, lw=1, ls="--",
               label=etiqueta)
        c = p[p["bajo_excedente"] == grupo].groupby("fecha")["credito_real"].sum()
        b.plot(pd.to_datetime(c.index), 100 * np.log(c).diff(12), color=color, lw=1.2, label=etiqueta)
    a.set_title("A. Densidad de los APR (% del activo)")
    marcar_eventos(a, con_texto=False)
    a.legend(loc="lower left", fontsize=6.5)
    b.axhline(0, color=GRIS, lw=0.8)
    b.set_title("B. Crecimiento real del crédito a 12 meses (%)")
    sombrear_pandemia(b)
    marcar_eventos(b, con_texto=False)
    b.legend(loc="upper right", fontsize=6.5)
    ejes_anuales(a, b)
    return figura


def bloque_2(panel: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    anotar("Bloque 2 · Análisis descriptivo")
    guardar_tabla(tabla_descriptivos(panel), "tabla_descriptivos.csv")
    exposicion = exposicion_por_banco(panel)
    guardar_tabla(tabla_bancos(panel, exposicion), "tabla_bancos.csv")
    guardar_figura(figura_excedente_bancos(panel), "fig_excedente_bancos.svg")
    guardar_figura(figura_densidad(s, panel, exposicion), "fig_densidad_apr.svg")
    anotar(f"Bancos con bajo excedente previo: {sorted(exposicion.index[exposicion['bajo_excedente'] == 1])}")
    return exposicion


# ---------------------------------------------------------------------------
# 7. Bloque 3 · H1: excedente de capital y crecimiento del crédito
# ---------------------------------------------------------------------------
CONTROLES_L12 = ["ln_activo_real_l12", "morosidad_l12", "liquidez_l12", "depositos_activo_l12"]
ETIQUETAS_H1 = {
    "excedente_capital_l12": "Excedente de capital (t-12)",
    "excedente_capital_l1": "Excedente de capital (t-1)",
    "ln_activo_real_l12": "ln activo real (t-12)",
    "morosidad_l12": "Morosidad (t-12)",
    "liquidez_l12": "Liquidez (t-12)",
    "depositos_activo_l12": "Depósitos / activo (t-12)",
    "brecha_pbi": "Brecha del PBI",
    "d12_tasa": "Variación de la tasa de referencia (12 m)",
}


def modelos_h1(panel: pd.DataFrame) -> dict[str, dict]:
    x = ["excedente_capital_l12"]
    controles_l1 = [c.replace("_l12", "_l1") for c in CONTROLES_L12]
    modelos = {
        "(1) Total": estimar_panel(panel, "d12_ln_credito", x + ["brecha_pbi", "d12_tasa"], efectos_tiempo=False),
        "(2) Total": estimar_panel(panel, "d12_ln_credito", x),
        "(3) Total": estimar_panel(panel, "d12_ln_credito", x + CONTROLES_L12),
        "(4) Mensual": estimar_panel(panel, "d1_ln_credito", ["excedente_capital_l1"] + controles_l1),
        "(5) Hipotecario": estimar_panel(panel, "d12_ln_hipotecarios", x + CONTROLES_L12),
        "(6) Préstamos": estimar_panel(panel, "d12_ln_prestamos", x + CONTROLES_L12),
        "(7) Tarjetas": estimar_panel(panel, "d12_ln_tarjetas", x + CONTROLES_L12),
    }
    # la columna (4) usa controles en t-1: se renombran para que compartan fila en la tabla
    m4 = modelos["(4) Mensual"]
    for clave in ("coef", "ee", "p"):
        m4[clave] = {k.replace("_l1", "_l12") if k != "excedente_capital_l1" else k: v for k, v in m4[clave].items()}
    return modelos


def figura_binscatter(panel: pd.DataFrame, beta: float) -> plt.Figure:
    """Figura 4: relación parcial entre excedente (t-12) y crecimiento del crédito, sin efectos fijos."""
    d = panel.dropna(subset=["d12_ln_credito", "excedente_capital_l12"] + CONTROLES_L12).copy()
    for v in ["d12_ln_credito", "excedente_capital_l12"]:
        d[v] = d[v] - d.groupby("entidad")[v].transform("mean")
        d[v] = d[v] - d.groupby("fecha")[v].transform("mean")
    d["bin"] = pd.qcut(d["excedente_capital_l12"], 20, labels=False)
    b = d.groupby("bin")[["excedente_capital_l12", "d12_ln_credito"]].mean()
    figura, eje = plt.subplots(figsize=(ANCHO_UNA_COLUMNA, 2.5))
    eje.scatter(d["excedente_capital_l12"], d["d12_ln_credito"], s=3, color=GRIS, alpha=0.25, lw=0)
    eje.scatter(b["excedente_capital_l12"], b["d12_ln_credito"], s=16, color=AZUL, zorder=3, label="Promedio por veintil")
    xs = np.linspace(b["excedente_capital_l12"].min(), b["excedente_capital_l12"].max(), 10)
    eje.plot(xs, beta * xs, color=DORADO, lw=1.4, label=f"Pendiente del modelo (2) = {beta:.2f}".replace(".", ","))
    eje.set_ylim(np.nanpercentile(d["d12_ln_credito"], 1), np.nanpercentile(d["d12_ln_credito"], 99))
    eje.set_xlabel("Excedente de capital en t-12 (p. p., sin efectos fijos)")
    eje.set_ylabel("Crecimiento real del crédito\n(%, sin efectos fijos)")
    eje.legend(loc="upper left", fontsize=6.3)
    return figura


def bloque_3(panel: pd.DataFrame) -> dict[str, dict]:
    anotar("Bloque 3 · H1: excedente de capital y crecimiento del crédito")
    modelos = modelos_h1(panel)
    tabla = tabla_de_modelos(modelos, ETIQUETAS_H1, {
        "Variable dependiente": ["Δ12 ln crédito"] * 3 + ["Δ1 ln crédito", "Δ12 ln hipotec.", "Δ12 ln préstamos", "Δ12 ln tarjetas"],
        "Efectos fijos de banco": ["Sí"] * 7,
        "Efectos fijos de mes": ["No"] + ["Sí"] * 6,
        "Rezagos Driscoll-Kraay": [str(m["rezagos_dk"]) for m in modelos.values()],
    })
    guardar_tabla(tabla, "tabla_h1_excedente.csv")
    for nombre, m in modelos.items():
        clave = "excedente_capital_l1" if "Mensual" in nombre else "excedente_capital_l12"
        anotar(f"H1 {nombre}: β excedente = {m['coef'][clave]:.3f} (e. e. {m['ee'][clave]:.3f}, p = {m['p'][clave]:.3f}) · N = {m['n']}")
    guardar_figura(figura_binscatter(panel, modelos["(2) Total"]["coef"]["excedente_capital_l12"]),
                   "fig_h1_dispersion.svg")
    return modelos


# ---------------------------------------------------------------------------
# 8. Bloque 4 · H2: canal del capital bancario de la política monetaria
# ---------------------------------------------------------------------------
def proyecciones_locales(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Para h = 0, ..., HORIZONTE_LP:
      (a) respuesta promedio (sin efectos de mes, con controles macro):
          ln C(t+h) - ln C(t-1) = a_i + b_h·Δtasa(t) + controles + e
      (b) respuesta diferencial según el excedente (con efectos de mes):
          ln C(t+h) - ln C(t-1) = a_i + d_t + c_h·[Δtasa(t) × excedente*(t-1)] + controles + e
    excedente* es el excedente centrado en la media del panel. c_h > 0 significa
    que los bancos con más excedente reducen menos su crédito ante un alza.
    """
    d = panel.copy()
    g = d.groupby("entidad")
    media = d["excedente_capital_l1"].mean()
    d["exc_c"] = d["excedente_capital_l1"] - media
    d["choque_x_exc"] = d["d_tasa"] * d["exc_c"]
    d["d1_ln_credito_l1"] = g["d1_ln_credito"].shift(1)
    d["d1_ln_credito_l2"] = g["d1_ln_credito"].shift(2)
    d["d_tasa_l1"] = g["d_tasa"].shift(1)
    d["d_tasa_l2"] = g["d_tasa"].shift(2)
    d["brecha_pbi_l1"] = g["brecha_pbi"].shift(1)
    controles = ["d1_ln_credito_l1", "d1_ln_credito_l2", "ln_activo_real_l1", "morosidad_l1", "liquidez_l1"]
    filas = []
    for h in range(HORIZONTE_LP + 1):
        d["y_h"] = g["ln_credito"].shift(-h) - g["ln_credito"].shift(1)
        rezagos = max(rezagos_driscoll_kraay(120), h + 1)
        a = estimar_panel(d, "y_h", ["d_tasa", "d_tasa_l1", "d_tasa_l2", "brecha_pbi_l1"] + controles,
                          efectos_tiempo=False, rezagos=rezagos)
        b = estimar_panel(d, "y_h", ["choque_x_exc", "exc_c"] + controles, efectos_tiempo=True, rezagos=rezagos)
        t_crit = stats.t.ppf(0.95, df=b["gl"])
        filas.append({
            "h": h,
            "promedio": a["coef"]["d_tasa"], "ee_promedio": a["ee"]["d_tasa"], "p_promedio": a["p"]["d_tasa"],
            "diferencial": b["coef"]["choque_x_exc"], "ee_diferencial": b["ee"]["choque_x_exc"],
            "p_diferencial": b["p"]["choque_x_exc"], "t_critico_90": t_crit, "n": b["n"],
        })
    anotar(f"H2: excedente medio del panel (centrado) = {media:.2f} p. p.")
    return pd.DataFrame(filas)


def figura_lp(lp: pd.DataFrame, de_excedente: float) -> plt.Figure:
    """Figura 5: respuesta acumulada del crédito real a un alza de 1 p. p. en la tasa de referencia."""
    figura, (a, b) = plt.subplots(1, 2, figsize=(ANCHO_DOS_COLUMNAS, 2.5), gridspec_kw={"wspace": 0.25})
    for eje, col, color, titulo, escala in [
        (a, "promedio", AZUL, "A. Respuesta promedio del crédito (%)", 1.0),
        (b, "diferencial", DORADO, "B. Diferencia por +1 D. E. de excedente", de_excedente),
    ]:
        y = lp[col] * escala
        ee = lp[f"ee_{col}"] * escala
        eje.fill_between(lp["h"], y - 1.96 * ee, y + 1.96 * ee, color=color, alpha=0.12, lw=0, label="IC 95 %")
        eje.fill_between(lp["h"], y - 1.645 * ee, y + 1.645 * ee, color=color, alpha=0.22, lw=0, label="IC 90 %")
        eje.plot(lp["h"], y, color=color, lw=1.6)
        eje.axhline(0, color=GRIS, lw=0.8)
        eje.set_title(titulo)
        eje.set_xlabel("Meses después del alza")
    a.legend(loc="lower left", fontsize=6.5)
    return figura


def bloque_4(panel: pd.DataFrame) -> pd.DataFrame:
    anotar("Bloque 4 · H2: proyecciones locales")
    lp = proyecciones_locales(panel)
    de = panel["excedente_capital"].std()
    tabla = lp.copy()
    tabla["diferencial_por_1de"] = tabla["diferencial"] * de
    guardar_tabla(tabla.round(4), "tabla_h2_proyecciones.csv")
    guardar_figura(figura_lp(lp, de), "fig_h2_proyecciones.svg")
    for h in (6, 12, 18, 24):
        f = lp[lp["h"] == h].iloc[0]
        anotar(f"H2 h={h}: promedio {f['promedio']:.3f} (p {f['p_promedio']:.3f}) · "
               f"diferencial ×1 D. E. {f['diferencial'] * de:.3f} (p {f['p_diferencial']:.3f})")
    return lp


# ---------------------------------------------------------------------------
# 9. Bloque 5 · H3: transición a Basilea III
# ---------------------------------------------------------------------------
RESULTADOS_H3 = {
    "d12_ln_credito": "Crecimiento real del crédito (12 m, %)",
    "ln_credito": "ln crédito real (×100)",
    "densidad_apr": "Densidad de los APR (%)",
    "ratio_capital_global": "Ratio de capital global (%)",
    "capital_activo": "Patrimonio efectivo / activo (%)",
    "liquidez": "Disponible / activo (%)",
}


def preparar_h3(panel: pd.DataFrame, exposicion: pd.DataFrame, ventana: tuple[str, str],
                inicio: str, variable_exposicion: str = "bajo_excedente",
                excluir: list[str] | None = None) -> pd.DataFrame:
    d = panel[panel["fecha"].between(*ventana)].merge(exposicion, left_on="entidad", right_index=True)
    if excluir:
        d = d[~d["entidad"].isin(excluir)]
    d["post"] = (d["fecha"] >= inicio).astype(int)
    d["expo_x_post"] = d[variable_exposicion] * d["post"]
    return d


def tabla_did(panel: pd.DataFrame, exposicion: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Diferencias en diferencias: exposición × (fecha >= 2023-04), con efectos de banco y de mes."""
    d = preparar_h3(panel, exposicion, VENTANA_H3, INICIO_ALZA)
    filas, modelos = [], {}
    for y, nombre in RESULTADOS_H3.items():
        m = estimar_panel(d, y, ["expo_x_post"])
        mc = estimar_panel(preparar_h3(panel, exposicion, VENTANA_H3, INICIO_ALZA, "exposicion_z"), y, ["expo_x_post"])
        mt = estimar_panel(d, y, ["expo_x_post"], tendencias_banco=True)
        modelos[y] = m
        antes = d[(d["post"] == 0)].groupby("bajo_excedente")[y].mean()
        filas.append({
            "Resultado": nombre,
            "Media previa (bajo excedente)": f"{antes.get(1, np.nan):.2f}",
            "Media previa (alto excedente)": f"{antes.get(0, np.nan):.2f}",
            "Bajo excedente × post": f"{m['coef']['expo_x_post']:.3f}{estrellas(m['p']['expo_x_post'])}",
            "e. e.": f"({m['ee']['expo_x_post']:.3f})",
            "Exposición continua × post": f"{mc['coef']['expo_x_post']:.3f}{estrellas(mc['p']['expo_x_post'])}",
            "e. e. ": f"({mc['ee']['expo_x_post']:.3f})",
            "Binaria con tendencias por banco": f"{mt['coef']['expo_x_post']:.3f}{estrellas(mt['p']['expo_x_post'])}",
            "e. e.  ": f"({mt['ee']['expo_x_post']:.3f})",
            "N": m["n"],
        })
        anotar(f"H3 DiD {y}: {m['coef']['expo_x_post']:.3f} (e. e. {m['ee']['expo_x_post']:.3f}, p {m['p']['expo_x_post']:.3f}) · "
               f"continua {mc['coef']['expo_x_post']:.3f} (p {mc['p']['expo_x_post']:.3f}) · "
               f"con tendencias {mt['coef']['expo_x_post']:.3f} (p {mt['p']['expo_x_post']:.3f})")
    return pd.DataFrame(filas), modelos


def estudio_eventos(panel: pd.DataFrame, exposicion: pd.DataFrame) -> pd.DataFrame:
    """Coeficientes trimestrales bajo_excedente × 1[trimestre = q], relativos a 2023T1."""
    d = preparar_h3(panel, exposicion, VENTANA_H3, INICIO_ALZA)
    trimestres = sorted(d["trimestre"].unique())
    nombres = [f"e_{q}" for q in trimestres if q != TRIMESTRE_BASE]
    indicadoras = pd.DataFrame({f"e_{q}": d["bajo_excedente"] * (d["trimestre"] == q).astype(int)
                                for q in trimestres if q != TRIMESTRE_BASE}, index=d.index)
    d = pd.concat([d, indicadoras], axis=1)
    filas = []
    for y in ["ln_credito", "densidad_apr", "ratio_capital_global"]:
        m = estimar_panel(d, y, nombres)
        for q in trimestres:
            if q == TRIMESTRE_BASE:
                filas.append({"resultado": y, "trimestre": q, "coef": 0.0, "ee": 0.0, "p": np.nan})
            else:
                n = f"e_{q}"
                filas.append({"resultado": y, "trimestre": q, "coef": m["coef"][n], "ee": m["ee"][n], "p": m["p"][n]})
    return pd.DataFrame(filas)


def figura_eventos(ev: pd.DataFrame) -> plt.Figure:
    """Figura 6: estudio de eventos (bajo vs. alto excedente), relativo a 2023T1."""
    titulos = {"ln_credito": "A. Crédito real (log × 100)", "densidad_apr": "B. Densidad APR (p. p.)",
               "ratio_capital_global": "C. Capital global (p. p.)"}
    figura, ejes = plt.subplots(1, 3, figsize=(ANCHO_DOS_COLUMNAS, 2.4), gridspec_kw={"wspace": 0.35})
    for eje, (y, titulo) in zip(ejes, titulos.items()):
        e = ev[ev["resultado"] == y].reset_index(drop=True)
        x = np.arange(len(e))
        eje.fill_between(x, e["coef"] - 1.96 * e["ee"], e["coef"] + 1.96 * e["ee"], color=AZUL, alpha=0.15, lw=0)
        eje.plot(x, e["coef"], color=AZUL, marker="o", ms=2.5)
        eje.axhline(0, color=GRIS, lw=0.8)
        base = int(e.index[e["trimestre"] == TRIMESTRE_BASE][0])
        eje.axvline(base + 0.5, color=ROJO, lw=0.8, ls="--")
        # Una etiqueta por año, en el primer trimestre: «2022», «2023»…
        anuales = [i for i, t in enumerate(e["trimestre"]) if t.endswith("Q1")]
        eje.set_xticks(x[anuales], [e["trimestre"][i][:4] for i in anuales], fontsize=7)
        eje.set_title(titulo)
    ejes[0].set_ylabel("Bajo menos alto excedente")
    return figura


def bloque_5(panel: pd.DataFrame, exposicion: pd.DataFrame) -> dict:
    anotar("Bloque 5 · H3: transición a Basilea III")
    tabla, modelos = tabla_did(panel, exposicion)
    guardar_tabla(tabla, "tabla_h3_did.csv")
    ev = estudio_eventos(panel, exposicion)
    guardar_tabla(ev.round(4), "tabla_h3_eventos.csv")
    guardar_figura(figura_eventos(ev), "fig_h3_eventos.svg")
    pre = ev[(ev["trimestre"] < TRIMESTRE_BASE)]
    for y in pre["resultado"].unique():
        p = pre[pre["resultado"] == y]
        anotar(f"H3 tendencias previas {y}: coeficientes previos significativos al 5 %: "
               f"{int((p['p'] < 0.05).sum())} de {len(p)}")
    return modelos


# ---------------------------------------------------------------------------
# 10. Bloque 6 · H4: márgenes de ajuste del ratio de capital
# ---------------------------------------------------------------------------
def descomposicion(panel: pd.DataFrame, exposicion: pd.DataFrame) -> pd.DataFrame:
    """
    Cohen y Scatigna (2016): con RCG = PE / APR y APR = (APR/A)·A,
        Δln RCG = Δln PE − Δln(APR/A) − Δln A
    Cada término se expresa en log × 100 (aprox. % de variación). Los grupos se
    agregan sumando montos (no promediando ratios).
    """
    p = panel.merge(exposicion[["bajo_excedente"]], left_on="entidad", right_index=True)
    grupos = {"Sistema": p, "Bajo excedente": p[p["bajo_excedente"] == 1], "Alto excedente": p[p["bajo_excedente"] == 0]}
    filas = []
    for periodo, (desde, hasta) in PERIODOS_H4.items():
        for grupo, d in grupos.items():
            suma = d[d["fecha"].isin([desde, hasta])].groupby("fecha")[["patrimonio_efectivo", "apr_total", "activo_total", "credito_real"]].sum()
            ini, fin = suma.loc[desde], suma.loc[hasta]
            d_pe = 100 * np.log(fin["patrimonio_efectivo"] / ini["patrimonio_efectivo"])
            d_apr = 100 * np.log(fin["apr_total"] / ini["apr_total"])
            d_a = 100 * np.log(fin["activo_total"] / ini["activo_total"])
            d_den = d_apr - d_a
            filas.append({
                "Periodo": periodo.replace("\n", " "), "Grupo": grupo,
                "RCG inicial (%)": round(100 * ini["patrimonio_efectivo"] / ini["apr_total"], 2),
                "RCG final (%)": round(100 * fin["patrimonio_efectivo"] / fin["apr_total"], 2),
                "Δln RCG": round(d_pe - d_apr, 2),
                "Aporte del capital (Δln PE)": round(d_pe, 2),
                "Aporte de la densidad (−Δln APR/A)": round(-d_den, 2),
                "Aporte del tamaño (−Δln A)": round(-d_a, 2),
                "Δln crédito real": round(100 * np.log(fin["credito_real"] / ini["credito_real"]), 2),
            })
    return pd.DataFrame(filas)


def figura_descomposicion(t: pd.DataFrame) -> plt.Figure:
    """Figura 7: barras apiladas de la descomposición por grupo y periodo."""
    componentes = [("Aporte del capital (Δln PE)", AZUL, "Capital (PE)"),
                   ("Aporte de la densidad (−Δln APR/A)", DORADO, "Densidad de los APR"),
                   ("Aporte del tamaño (−Δln A)", GRIS, "Tamaño del balance")]
    t = t[t["Grupo"] != "Sistema"].reset_index(drop=True)
    etiquetas = [f"{g}\n{p.split(' ')[0]}" for g, p in zip(t["Grupo"], t["Periodo"])]
    figura, eje = plt.subplots(figsize=(ANCHO_DOS_COLUMNAS, 2.6))
    x = np.arange(len(t))
    positivo, negativo = np.zeros(len(t)), np.zeros(len(t))
    for col, color, nombre in componentes:
        v = t[col].to_numpy()
        base = np.where(v >= 0, positivo, negativo)
        eje.bar(x, v, bottom=base, color=color, width=0.55, label=nombre)
        positivo += np.where(v >= 0, v, 0)
        negativo += np.where(v < 0, v, 0)
    eje.scatter(x, t["Δln RCG"], color="black", marker="D", s=18, zorder=4, label="Cambio del ratio de capital (Δln RCG)")
    eje.axhline(0, color=GRIS, lw=0.8)
    eje.set_xticks(x, etiquetas, fontsize=6.6)
    eje.set_ylabel("log × 100")
    eje.legend(loc="upper left", fontsize=6.3, ncol=2)
    return figura


def bloque_6(panel: pd.DataFrame, exposicion: pd.DataFrame) -> pd.DataFrame:
    anotar("Bloque 6 · H4: descomposición del ratio de capital")
    t = descomposicion(panel, exposicion)
    guardar_tabla(t, "tabla_h4_descomposicion.csv")
    guardar_figura(figura_descomposicion(t), "fig_h4_descomposicion.svg")
    for _, f in t.iterrows():
        anotar(f"H4 {f['Periodo']} · {f['Grupo']}: ΔlnRCG {f['Δln RCG']} = PE {f['Aporte del capital (Δln PE)']} "
               f"+ densidad {f['Aporte de la densidad (−Δln APR/A)']} + tamaño {f['Aporte del tamaño (−Δln A)']}")
    return t


# ---------------------------------------------------------------------------
# 11. Bloque 7 · Robustez
# ---------------------------------------------------------------------------
def tabla_robustez(panel: pd.DataFrame, exposicion: pd.DataFrame) -> pd.DataFrame:
    filas = []

    def fila(prueba: str, hipotesis: str, m: dict, x: str) -> None:
        filas.append({"Hipótesis": hipotesis, "Especificación": prueba,
                      "Coeficiente": f"{m['coef'][x]:.3f}{estrellas(m['p'][x])}",
                      "e. e.": f"({m['ee'][x]:.3f})", "Valor p": f"{m['p'][x]:.3f}", "N": m["n"]})

    base_x = ["excedente_capital_l12"] + CONTROLES_L12
    participacion = panel[panel["fecha"] == FECHA_CORTE].set_index("entidad")["activo_total"]
    participacion = 100 * participacion / participacion.sum()
    pequenos = list(participacion[participacion < 1].index)
    w = panel.copy()
    lo, hi = w["excedente_capital_l12"].quantile([0.01, 0.99])
    w["excedente_capital_l12"] = w["excedente_capital_l12"].clip(lo, hi)
    sin_pandemia = panel[~panel["fecha"].between(*PANDEMIA)]

    fila("Base: modelo (3) de la Tabla H1", "H1", estimar_panel(panel, "d12_ln_credito", base_x), "excedente_capital_l12")
    fila("Sin Alfin Banco", "H1", estimar_panel(panel[panel["entidad"] != "Alfin Banco"], "d12_ln_credito", base_x), "excedente_capital_l12")
    fila(f"Sin bancos con menos de 1 % del activo ({len(pequenos)})", "H1",
         estimar_panel(panel[~panel["entidad"].isin(pequenos)], "d12_ln_credito", base_x), "excedente_capital_l12")
    fila("Excedente acotado a los percentiles 1 y 99", "H1", estimar_panel(w, "d12_ln_credito", base_x), "excedente_capital_l12")
    fila("Excedente y controles en t-6", "H1",
         estimar_panel(panel, "d12_ln_credito", [c.replace("_l12", "_l6") for c in base_x]), "excedente_capital_l6")
    fila("Sin el periodo de pandemia (2020-03 a 2021-12)", "H1", estimar_panel(sin_pandemia, "d12_ln_credito", base_x), "excedente_capital_l12")
    fila("Driscoll-Kraay con 12 rezagos", "H1", estimar_panel(panel, "d12_ln_credito", base_x, rezagos=12), "excedente_capital_l12")

    con_alfin = exposicion_por_banco(panel, excluir=None)
    y_h3 = "d12_ln_credito"
    fila("Base: crecimiento del crédito, bajo excedente × post", "H3",
         estimar_panel(preparar_h3(panel, exposicion, VENTANA_H3, INICIO_ALZA), y_h3, ["expo_x_post"]), "expo_x_post")
    fila("Incluye a Alfin Banco", "H3",
         estimar_panel(preparar_h3(panel, con_alfin, VENTANA_H3, INICIO_ALZA), y_h3, ["expo_x_post"]), "expo_x_post")
    fila("Ventana desde 2022-01", "H3",
         estimar_panel(preparar_h3(panel, exposicion, ("2022-01", "2025-12"), INICIO_ALZA), y_h3, ["expo_x_post"]), "expo_x_post")
    fila("Inicio del tratamiento en 2023-01 (nuevos ponderadores)", "H3",
         estimar_panel(preparar_h3(panel, exposicion, VENTANA_H3, "2023-01"), y_h3, ["expo_x_post"]), "expo_x_post")
    fila("Densidad APR, incluye a Alfin Banco", "H3",
         estimar_panel(preparar_h3(panel, con_alfin, VENTANA_H3, INICIO_ALZA), "densidad_apr", ["expo_x_post"]), "expo_x_post")
    for y, nombre in [(y_h3, "crecimiento del crédito"), ("ln_credito", "ln crédito real")]:
        fila(f"Placebo en {nombre}: fecha ficticia {PLACEBO[2]} (ventana {PLACEBO[0]} a {PLACEBO[1]})", "H3",
             estimar_panel(preparar_h3(panel, exposicion, PLACEBO[:2], PLACEBO[2]), y, ["expo_x_post"]), "expo_x_post")
    return pd.DataFrame(filas)


VARIABLES_CORRELACION = {
    "d12_ln_credito": "Crec. crédito real",
    "excedente_capital": "Excedente de capital",
    "ratio_capital_global": "Ratio de capital global",
    "densidad_apr": "Densidad APR",
    "morosidad": "Morosidad",
    "liquidez": "Liquidez",
    "depositos_activo": "Depósitos / activo",
    "ln_activo_real": "ln activo real",
    "tasa_referencia": "Tasa de referencia",
}


def figura_correlaciones(panel: pd.DataFrame) -> plt.Figure:
    matriz = panel[list(VARIABLES_CORRELACION)].rename(columns=VARIABLES_CORRELACION).corr()
    n = len(matriz)
    figura, eje = plt.subplots(figsize=(ANCHO_UNA_COLUMNA + 0.4, 3.3))
    valores = np.where(np.triu(np.ones((n, n), dtype=bool), k=1), np.nan, matriz.to_numpy())
    imagen = eje.imshow(valores, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(n):
        for j in range(i + 1):
            eje.text(j, i, f"{matriz.iat[i, j]:.2f}".replace(".", ","), ha="center", va="center",
                     fontsize=5.8, color="white" if abs(matriz.iat[i, j]) > 0.6 else "#1a1a1a")
    eje.set_xticks(range(n), matriz.columns, rotation=45, ha="right", fontsize=6.3)
    eje.set_yticks(range(n), matriz.index, fontsize=6.3)
    eje.tick_params(length=0)
    eje.grid(False)
    for lado in eje.spines.values():
        lado.set_visible(False)
    barra = figura.colorbar(imagen, ax=eje, fraction=0.04, pad=0.02)
    barra.outline.set_visible(False)
    return figura


def figura_capital_bancos(panel: pd.DataFrame) -> plt.Figure:
    """Figura B2: ratio de capital global de cada banco frente al límite global vigente."""
    orden = panel.groupby("entidad")["activo_total"].mean().sort_values(ascending=False).index
    figura, ejes = plt.subplots(3, 5, figsize=(ANCHO_DOS_COLUMNAS, 4.6), sharex=True,
                                gridspec_kw={"wspace": 0.35, "hspace": 0.45})
    for eje, banco in zip(ejes.flat, orden):
        b = panel[panel["entidad"] == banco].sort_values("fecha")
        f = pd.to_datetime(b["fecha"])
        eje.fill_between(f, b["limite_global"], b["ratio_capital_global"], color=AZUL, alpha=0.12, lw=0)
        eje.plot(f, b["ratio_capital_global"], color=AZUL, lw=1)
        eje.step(f, b["limite_global"], where="post", color=ROJO, lw=1)
        eje.set_title(banco.replace("Banco ", "").replace(" Perú", ""), fontsize=7, loc="left")
        eje.tick_params(labelsize=6)
    ejes_anuales(*ejes.flat, paso=3)
    ejes[0, 0].plot([], [], color=AZUL, label="Ratio de capital global")
    ejes[0, 0].plot([], [], color=ROJO, label="Límite global vigente")
    figura.legend(*ejes[0, 0].get_legend_handles_labels(), loc="lower center", ncol=2,
                  bbox_to_anchor=(0.5, -0.02), fontsize=7)
    return figura


def figura_robustez(t: pd.DataFrame) -> plt.Figure:
    """Figura B3: coeficientes de la tabla de robustez con intervalos de confianza al 95 %."""
    d = t.copy()
    d["coef"] = d["Coeficiente"].astype(str).str.replace("*", "", regex=False).astype(float)
    d["ee"] = d["e. e."].astype(str).str.strip("()").astype(float)
    figura, ejes = plt.subplots(2, 1, figsize=(5.2, 4.6), gridspec_kw={"hspace": 0.45})
    for eje, h, titulo in [(ejes[0], "H1", "A. H1: excedente rezagado"),
                           (ejes[1], "H3", "B. H3: bajo excedente × post")]:
        g = d[d["Hipótesis"] == h].reset_index(drop=True)
        y = np.arange(len(g))[::-1]
        placebo = g["Especificación"].str.startswith("Placebo")
        colores = [GRIS if p else AZUL for p in placebo]
        for xi, yi, ei, ci in zip(g["coef"], y, g["ee"], colores):
            eje.errorbar(xi, yi, xerr=1.96 * ei, fmt="none", ecolor=ci, elinewidth=1, capsize=2)
        eje.scatter(g["coef"], y, color=colores, s=14, zorder=3)
        eje.axvline(0, color=ROJO, lw=0.8, ls="--")
        etiquetas = [e.split(" (ventana")[0].replace("Base: ", "Base · ") for e in g["Especificación"]]
        eje.set_yticks(y, etiquetas, fontsize=7.5)
        eje.set_title(titulo)
        eje.grid(axis="y", visible=False)
    return figura


def bloque_7(panel: pd.DataFrame, exposicion: pd.DataFrame) -> None:
    anotar("Bloque 7 · Robustez")
    t = tabla_robustez(panel, exposicion)
    guardar_tabla(t, "tabla_robustez.csv")
    for _, f in t.iterrows():
        anotar(f"Robustez {f['Hipótesis']} · {f['Especificación']}: {f['Coeficiente']} {f['e. e.']} p={f['Valor p']}")
    guardar_figura(figura_correlaciones(panel), "fig_correlaciones.svg")
    guardar_figura(figura_capital_bancos(panel), "fig_capital_bancos.svg")
    guardar_figura(figura_robustez(t), "fig_robustez.svg")


# ---------------------------------------------------------------------------
# 12. Programa principal
# ---------------------------------------------------------------------------
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    for entrada in (ENTRADA_PANEL, ENTRADA_MACRO):
        if not entrada.exists():
            print(f"Falta {entrada.relative_to(RAIZ)}: ejecutar antes los scripts 01, 02 y 03.")
            return 1

    np.random.seed(SEMILLA)
    CARPETA_SALIDAS.mkdir(exist_ok=True)
    configurar_graficos()
    anotar("Inicio del análisis")
    anotar(f"Versiones: Python {sys.version.split()[0]} · numpy {np.__version__} · pandas {pd.__version__} · "
           f"scipy {__import__('scipy').__version__} · matplotlib {matplotlib.__version__}")

    panel, _ = cargar_datos()
    s = bloque_1(panel)
    exposicion = bloque_2(panel, s)
    bloque_3(panel)
    bloque_4(panel)
    bloque_5(panel, exposicion)
    bloque_6(panel, exposicion)
    bloque_7(panel, exposicion)

    anotar("Análisis terminado sin errores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
