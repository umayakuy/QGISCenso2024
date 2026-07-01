# -*- coding: utf-8 -*-
# Versión V13: evita duplicar columnas cuando la BD seleccionada ya fue cargada.

import os
import re
import csv
import tempfile
import urllib.request
import urllib.error

from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt

from qt_compat import (
    QVariant,
    QT_ALIGN_CENTER,
    QT_ALIGN_LEFT,
    QT_ALIGN_VCENTER,
    QT_KEEP_ASPECT_RATIO,
    QT_SMOOTH_TRANSFORMATION,
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QComboBox,
    QInputDialog,
)



from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsField,
    QgsFeature,
    QgsFeatureRequest,
    QgsExpression,
    QgsVectorLayerJoinInfo,
)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

# Archivos esperados en la misma carpeta del script.
RUTA_LOGO = os.path.join(os.path.dirname(__file__), "GEOC.jpg")
RUTA_LOGO_RESPALDO = r"C:\INE\GEOC.jpg"
NOMBRES_CSV = ["00.csv", "00.CSV", "00(3).csv"]
NOMBRES_DB_CSV = ["0a.csv", "0a.CSV"]

# Repositorio público donde están las bases de polígonos por departamento.
# El script intenta primero FILE.parquet y luego FILE.geoparquet,
# porque el repositorio actualmente usa archivos .geoparquet.
GITHUB_PUNTOS_RAW = "https://raw.githubusercontent.com/umayakuy/QGISCenso2024/main/data/poligonos"
EXTENSIONES_PARQUET = [".parquet", ".geoparquet"]

# Si el archivo ya fue descargado antes, se reutiliza desde la carpeta temporal.
# Esto evita volver a descargar archivos grandes en cada vinculación.
USAR_CACHE_PARQUET = True

TITULO_VENTANA = "CENSO 2024 - Base de Datos Manzanos"
TITULO_MODULO = "Vincular datos a manzanos"

TEXTO_CREDITOS = (
    "Sistematizado y Desarrollado por: "
    "Ing. MSc. Jorge Ayala Niño de Guzmán"
)

REGEX_COD = re.compile(r"^U\d{11}$")


class BaseDatosYaCargada(Exception):
    """Se usa para mostrar un mensaje informativo cuando la BD ya está cargada."""
    pass


# ==========================================================
# CATÁLOGO DE VARIABLES CENSALES
# ==========================================================

DATOS_CENSALES = {
    "Características principales de la población": [
        ("Población por grupo de edad", "A1"),      
        ("Población que acude por problemas de salud", "A2"),
        ("Población según registro al SUS o afiliación a seguros de salud", "A3"),
        ("Población mayor a 19 años según instrucción de educación alcanzado", "A4"),
    ],
    "Características económicas de la población": [
        ("Población mayor a 14 años según categoría ocupacional", "B1"),
        ("Población mayor a 14 años según actividad económica", "B2"),
    ],
    "Características de vivienda": [
        ("Tipo de vivienda y condición de ocupación", "C1"),
        ("Tenencia de vivienda de personas presentes", "C2"),
    ],
    "Servicios básicos que cuentan las viviendas": [
        ("Procedencia del agua", "D1"),
        ("Desagüe del servicio sanitario", "D2"),
        ("Disponibilidad de energía eléctrica", "D3"),
        ("Forma de eliminación de la basura", "D4"),
        ("Tecnologías de Información y Comunicación", "D5"),
        ("Combustible o energía más utilizado para cocinar", "D6"),
    ],
}


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================

def obtener_ventana_qgis():
    try:
        return iface.mainWindow()
    except Exception:
        return None


def carpeta_script():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def buscar_archivo_csv():
    carpeta = carpeta_script()
    for nombre in NOMBRES_CSV:
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            return ruta
    return os.path.join(carpeta, "00.csv")


def buscar_archivo_db():
    carpeta = carpeta_script()
    for nombre in NOMBRES_DB_CSV:
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            return ruta
    return os.path.join(carpeta, "0.csv")


def texto_limpio(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def normalizar_codigo(valor):
    """Normaliza COD de capa y Parquet para comparar de forma segura."""
    texto = texto_limpio(valor).upper()

    # Limpia caracteres invisibles o comunes cuando el COD viene desde CSV/QGIS.
    texto = texto.replace("\ufeff", "")
    texto = texto.replace("\u200b", "")
    texto = texto.replace("\u200c", "")
    texto = texto.replace("\u200d", "")
    texto = texto.replace("'", "")
    texto = texto.replace('"', "")

    # Si por alguna conversión llegó como U80110100001.0, recupera el código real.
    if texto.endswith(".0"):
        texto = texto[:-2]

    # El COD válido no usa espacios ni separadores.
    texto = re.sub(r"[^A-Z0-9]", "", texto)

    return texto


def convertir_entero(valor, nombre):
    try:
        return int(texto_limpio(valor))
    except Exception:
        raise Exception("El valor {} debe ser numérico. Valor recibido: {}".format(nombre, valor))


def url_archivo_github(file_codigo, extension):
    return "{}/{}{}".format(
        GITHUB_PUNTOS_RAW.rstrip("/"),
        texto_limpio(file_codigo).upper(),
        extension
    )


def descargar_archivo_github(file_codigo, cod_alternativo=None):
    """
    Descarga desde GitHub/data/poligonos el archivo FILE.parquet o FILE.geoparquet.

    Optimización:
    - Si el archivo ya existe en la carpeta temporal, lo reutiliza.
    - Evita descargar el mismo Parquet/GeoParquet cada vez que se vincula otra BD.

    Devuelve: ruta_local, url_usada, codigo_archivo_usado.
    """
    codigos = []
    file_codigo = texto_limpio(file_codigo).upper()
    if file_codigo:
        codigos.append(file_codigo)

    cod_alternativo = texto_limpio(cod_alternativo).upper()
    if cod_alternativo and cod_alternativo not in codigos:
        codigos.append(cod_alternativo)

    carpeta_cache = os.path.join(tempfile.gettempdir(), "GeoCenso2024", "manzanos")

    if not os.path.exists(carpeta_cache):
        os.makedirs(carpeta_cache)

    ultimo_error = None

    for codigo in codigos:
        for extension in EXTENSIONES_PARQUET:
            url = url_archivo_github(codigo, extension)
            ruta_local = os.path.join(carpeta_cache, "{}{}".format(codigo, extension))

            # Primero usa caché local si ya fue descargado.
            if USAR_CACHE_PARQUET and os.path.exists(ruta_local) and os.path.getsize(ruta_local) > 0:
                return ruta_local, url, codigo

            try:
                solicitud = urllib.request.Request(
                    url,
                    headers={"User-Agent": "QGIS-Censo2024"}
                )
                with urllib.request.urlopen(solicitud, timeout=90) as respuesta:
                    with open(ruta_local, "wb") as salida:
                        while True:
                            bloque = respuesta.read(1024 * 1024)
                            if not bloque:
                                break
                            salida.write(bloque)

                if not os.path.exists(ruta_local) or os.path.getsize(ruta_local) == 0:
                    ultimo_error = "El archivo descargado está vacío: {}".format(url)
                    continue

                return ruta_local, url, codigo

            except urllib.error.HTTPError as error:
                ultimo_error = "HTTP {} al consultar {}".format(error.code, url)
                if error.code == 404:
                    continue
            except Exception as error:
                ultimo_error = str(error)

    raise Exception(
        "No se pudo descargar el archivo desde GitHub.\n\n"
        "Códigos probados: {}\n\n{}".format(
            ", ".join(codigos),
            ultimo_error
        )
    )

def abrir_parquet_como_capa(ruta_parquet, nombre_capa):
    capa = QgsVectorLayer(ruta_parquet, nombre_capa, "ogr")

    if not capa.isValid():
        raise Exception(
            "QGIS no pudo abrir el archivo descargado como Parquet/GeoParquet.\n\n"
            "Archivo: {}\n\n"
            "Verifique que su instalación de QGIS tenga soporte GDAL/OGR para Parquet.".format(
                ruta_parquet
            )
        )

    if capa.fields().count() == 0:
        raise Exception("El archivo descargado no contiene columnas de atributos.")

    return capa


def nombre_campo_base(nombre):
    """Devuelve el nombre seguro de campo, sin agregar sufijos _2, _3, etc."""
    base = texto_limpio(nombre)
    if not base:
        base = "CAMPO"

    # Nombres más seguros para QGIS.
    base = base.replace(" ", "_").replace("-", "_").replace(".", "_")

    if base.upper() == "COD":
        base = "COD_DATO"

    return base


def nombre_campo_unico(nombre, usados):
    base = nombre_campo_base(nombre)

    candidato = base
    contador = 2
    while candidato.upper() in usados:
        candidato = "{}_{}".format(base, contador)
        contador += 1

    usados.add(candidato.upper())
    return candidato


def encontrar_campo_cod(capa):
    """Devuelve el nombre real del campo COD y su índice."""
    for campo in capa.fields():
        if campo.name().strip().upper() == "COD":
            nombre_campo = campo.name()
            indice_campo = capa.fields().indexFromName(nombre_campo)
            return nombre_campo, indice_campo
    return None, -1


def es_capa_poligonos(capa):
    if not isinstance(capa, QgsVectorLayer):
        return False
    return QgsWkbTypes.geometryType(capa.wkbType()) == QgsWkbTypes.PolygonGeometry


def valor_atributo(feature, indice_campo):
    """Lee atributo por índice para evitar incompatibilidades entre versiones de QGIS."""
    try:
        return feature.attribute(indice_campo)
    except Exception:
        pass

    try:
        atributos = feature.attributes()
        if 0 <= indice_campo < len(atributos):
            return atributos[indice_campo]
    except Exception:
        pass

    return None


def valor_atributo_request(feature, atributos, indices_solicitados, indice_origen, posicion):
    """
    Lee atributos cuando QgsFeatureRequest usa subsetOfAttributes.
    Algunas instalaciones devuelven la lista en orden original; otras devuelven solo
    los atributos solicitados. Esta función soporta ambos comportamientos.
    """
    try:
        if len(atributos) == len(indices_solicitados):
            return atributos[posicion]
    except Exception:
        pass

    try:
        if 0 <= indice_origen < len(atributos):
            return atributos[indice_origen]
    except Exception:
        pass

    try:
        return feature.attribute(indice_origen)
    except Exception:
        return None


def crear_request_solo_atributos(indices, campos=None):
    """
    Crea un QgsFeatureRequest más liviano:
    - sin geometría;
    - leyendo solamente las columnas necesarias.
    """
    request = QgsFeatureRequest()

    try:
        request.setFlags(QgsFeatureRequest.NoGeometry)
    except Exception:
        pass

    try:
        if campos is not None:
            request.setSubsetOfAttributes(indices, campos)
        else:
            request.setSubsetOfAttributes(indices)
    except Exception:
        try:
            request.setSubsetOfAttributes(indices)
        except Exception:
            pass

    return request


def escapar_qgis_texto(valor):
    """Escapa comillas simples para usar textos en expresiones QGIS."""
    return texto_limpio(valor).replace("'", "''")


def construir_filtro_prefijos_qgis(nombre_campo, prefijos):
    """
    Construye un filtro QGIS para leer solo los registros cuyo COD inicia con
    los primeros 7 caracteres requeridos.
    """
    if not prefijos:
        return ""

    campo = QgsExpression.quotedColumnRef(nombre_campo)
    partes = []

    for prefijo in prefijos:
        prefijo = normalizar_codigo(prefijo)
        if not prefijo:
            continue
        partes.append("left({}, 7) = '{}'".format(campo, escapar_qgis_texto(prefijo)))

    return " OR ".join(partes)


def abrir_csv_diccionario(ruta_csv):
    """
    Lee 00.csv y devuelve un diccionario por COD municipal.
    COD municipal esperado: U + D + PP + M. Ejemplo: U9022.
    """
    if not os.path.exists(ruta_csv):
        raise FileNotFoundError("No se encontró el archivo 00.csv en la carpeta del script.")

    contenido = None
    ultimo_error = None

    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(ruta_csv, "r", encoding=encoding, newline="") as archivo:
                contenido = archivo.read()
            break
        except Exception as error:
            ultimo_error = error

    if contenido is None:
        raise Exception("No se pudo leer 00.csv: {}".format(ultimo_error))

    lineas = contenido.splitlines()
    primera_linea = lineas[0] if lineas else ""
    separador = ";" if primera_linea.count(";") >= primera_linea.count(",") else ","

    lector = csv.DictReader(lineas, delimiter=separador)

    if not lector.fieldnames:
        raise Exception("El archivo 00.csv no tiene encabezados válidos.")

    columnas = {c.strip().upper(): c for c in lector.fieldnames}

    requeridas = ["D", "DEPARTAMENTO", "P", "PROVINCIA", "M", "MUNICIPIO"]
    faltantes = [c for c in requeridas if c not in columnas]

    if faltantes:
        raise Exception(
            "El archivo 00.csv no tiene estas columnas requeridas: {}".format(
                ", ".join(faltantes)
            )
        )

    catalogo = {}

    for fila in lector:
        d = texto_limpio(fila.get(columnas["D"], ""))
        p = texto_limpio(fila.get(columnas["P"], ""))
        m = texto_limpio(fila.get(columnas["M"], ""))

        departamento = texto_limpio(fila.get(columnas["DEPARTAMENTO"], ""))
        provincia = texto_limpio(fila.get(columnas["PROVINCIA"], ""))
        municipio = texto_limpio(fila.get(columnas["MUNICIPIO"], ""))

        cod_csv = ""
        if "COD" in columnas:
            cod_csv = normalizar_codigo(fila.get(columnas["COD"], ""))

        if cod_csv:
            cod_municipal = cod_csv[:5]
        else:
            cod_municipal = "U{}{}{}".format(d, p.zfill(2), m)

        if not cod_municipal.startswith("U") or len(cod_municipal) != 5:
            continue

        catalogo[cod_municipal] = {
            "D": d,
            "DEPARTAMENTO": departamento,
            "P": p,
            "PROVINCIA": provincia,
            "M": m,
            "MUNICIPIO": municipio,
            "COD": cod_municipal,
        }

    if not catalogo:
        raise Exception("No se pudo construir el catálogo municipal desde 00.csv.")

    return catalogo


def abrir_csv_db_variables(ruta_csv):
    """
    Lee 0.csv y devuelve un diccionario de parámetros por código interno.

    Formato esperado sin encabezado:
        A1;2;15
        A2;16;30

    Resultado para A1:
        DB1 = 2
        DB2 = 15
    """
    if not os.path.exists(ruta_csv):
        raise FileNotFoundError("No se encontró el archivo 0.csv en la carpeta del script.")

    contenido = None
    ultimo_error = None

    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(ruta_csv, "r", encoding=encoding, newline="") as archivo:
                contenido = archivo.read()
            break
        except Exception as error:
            ultimo_error = error

    if contenido is None:
        raise Exception("No se pudo leer 0.csv: {}".format(ultimo_error))

    lineas = [linea for linea in contenido.splitlines() if linea.strip()]
    if not lineas:
        raise Exception("El archivo 0.csv está vacío.")

    primera_linea = lineas[0]
    separador = ";" if primera_linea.count(";") >= primera_linea.count(",") else ","

    catalogo_db = {}
    lector = csv.reader(lineas, delimiter=separador)

    for fila in lector:
        if len(fila) < 3:
            continue

        codigo = texto_limpio(fila[0]).upper()
        db1 = texto_limpio(fila[1])
        db2 = texto_limpio(fila[2])

        # Permite encabezados accidentales y evita filas inválidas.
        if codigo in ("CODIGO", "CÓDIGO", "COD", "DB"):
            continue

        if not codigo:
            continue

        catalogo_db[codigo] = {
            "CODIGO": codigo,
            "DB1": db1,
            "DB2": db2,
        }

    if not catalogo_db:
        raise Exception("No se pudo construir el catálogo de variables desde 0.csv.")

    return catalogo_db


# ==========================================================
# VENTANA PRINCIPAL
# ==========================================================

class Censo2024Dialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.catalogo_municipal = {}
        self.catalogo_db = {}
        self.capa_seleccionada = None
        self.campo_cod = None
        self.indice_cod = -1
        self.resumen_capa = None
        self.capa_join_actual = None
        self.id_join_actual = None
        self.dialogo_vinculando = None

        self.setWindowTitle(TITULO_VENTANA)
        self.setMinimumWidth(620)
        self.setMinimumHeight(430)

        try:
            self.catalogo_municipal = abrir_csv_diccionario(buscar_archivo_csv())
        except Exception as error:
            QMessageBox.critical(self, "Error CENSO 2024", str(error))

        try:
            self.catalogo_db = abrir_csv_db_variables(buscar_archivo_db())
        except Exception as error:
            QMessageBox.critical(self, "Error CENSO 2024", str(error))

        self.crear_interfaz()
        self.aplicar_estado_inicial()

    # ------------------------------------------------------
    # INTERFAZ
    # ------------------------------------------------------

    def crear_interfaz(self):
        layout_principal = QVBoxLayout(self)

        self.agregar_logo(layout_principal)
        self.agregar_panel_variables(layout_principal)

        self.lbl_municipio = QLabel("Municipio seleccionado: Ninguno")
        layout_principal.addWidget(self.lbl_municipio)

        self.agregar_botones(layout_principal)
        self.agregar_creditos(layout_principal)

    def agregar_logo(self, layout_principal):
        """Agrega el logo institucional en la parte superior de la ventana."""

        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(QT_ALIGN_CENTER)
        self.lbl_logo.setMinimumHeight(135)
        self.lbl_logo.setStyleSheet(
            "background-color: white; "
            "border: 1px solid #d0d0d0; "
            "padding: 6px;"
        )

        ruta_logo_final = None
        if os.path.exists(RUTA_LOGO):
            ruta_logo_final = RUTA_LOGO
        elif os.path.exists(RUTA_LOGO_RESPALDO):
            ruta_logo_final = RUTA_LOGO_RESPALDO

        if ruta_logo_final:
            pixmap = QPixmap(ruta_logo_final)

            if not pixmap.isNull():
                pixmap_escalado = pixmap.scaled(
                    570,
                    145,
                    QT_KEEP_ASPECT_RATIO,
                    QT_SMOOTH_TRANSFORMATION
                )
                self.lbl_logo.setPixmap(pixmap_escalado)
            else:
                self.lbl_logo.setText("No se pudo leer el logo GEOC.jpg")
        else:
            self.lbl_logo.setText("Logo no encontrado: GEOC.jpg")

        layout_principal.addWidget(self.lbl_logo)

    def agregar_panel_variables(self, layout_principal):
        grupo_seleccion = QGroupBox(TITULO_MODULO)
        grid = QGridLayout(grupo_seleccion)

        self.btn_seleccionar_capa = QPushButton("Seleccionar Capa")
        self.btn_seleccionar_capa.clicked.connect(self.seleccionar_capa)

        self.cmb_categoria = QComboBox()
        self.cmb_grupo = QComboBox()
        self.configurar_combo(self.cmb_categoria)
        self.configurar_combo(self.cmb_grupo)

        self.cmb_categoria.addItem("-- Seleccione característica --", None)
        for categoria in DATOS_CENSALES.keys():
            self.cmb_categoria.addItem(categoria, categoria)

        self.cmb_grupo.addItem("-- Seleccione grupo de variables --", None)

        self.cmb_categoria.currentIndexChanged.connect(self.actualizar_grupo_variables)
        self.cmb_categoria.currentIndexChanged.connect(self.actualizar_estado_boton_cargar)
        self.cmb_grupo.currentIndexChanged.connect(self.actualizar_estado_boton_cargar)

        grid.addWidget(QLabel("Capa:"), 0, 0)
        grid.addWidget(self.btn_seleccionar_capa, 0, 1)

        grid.addWidget(QLabel("Característica:"), 1, 0)
        grid.addWidget(self.cmb_categoria, 1, 1)

        grid.addWidget(QLabel("Grupo de variables:"), 2, 0)
        grid.addWidget(self.cmb_grupo, 2, 1)

        layout_principal.addWidget(grupo_seleccion)

    def configurar_combo(self, combo):
        combo.setMinimumWidth(300)

    def agregar_botones(self, layout_principal):
        layout_botones = QHBoxLayout()

        self.btn_cargar = QPushButton("Vincular Datos")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_cerrar = QPushButton("Cerrar")

        self.btn_cargar.clicked.connect(self.cargar_datos)
        self.btn_limpiar.clicked.connect(self.limpiar)
        self.btn_cerrar.clicked.connect(self.close)

        layout_botones.addStretch()
        layout_botones.addWidget(self.btn_cargar)
        layout_botones.addWidget(self.btn_limpiar)
        layout_botones.addWidget(self.btn_cerrar)

        layout_principal.addLayout(layout_botones)

    def agregar_creditos(self, layout_principal):
        """Agrega el crédito del desarrollador en la parte inferior."""

        self.lbl_creditos = QLabel(TEXTO_CREDITOS)
        self.lbl_creditos.setAlignment(QT_ALIGN_CENTER)
        self.lbl_creditos.setWordWrap(True)
        self.lbl_creditos.setStyleSheet(
            "font-size: 9pt; "
            "font-weight: bold; "
            "color: #0b4d89; "
            "padding-top: 8px;"
        )

        layout_principal.addWidget(self.lbl_creditos)

    def aplicar_estado_inicial(self):
        self.cmb_categoria.setEnabled(False)
        self.cmb_grupo.setEnabled(False)
        self.btn_cargar.setEnabled(False)

    # ------------------------------------------------------
    # COMBOS
    # ------------------------------------------------------

    def actualizar_grupo_variables(self):
        self.cmb_grupo.blockSignals(True)
        self.cmb_grupo.clear()
        self.cmb_grupo.addItem("-- Seleccione grupo de variables --", None)

        categoria = self.cmb_categoria.currentData()
        if categoria in DATOS_CENSALES:
            for nombre, codigo in DATOS_CENSALES[categoria]:
                # Mostrar solo el nombre en el combo.
                # El código interno se conserva oculto en currentData().
                self.cmb_grupo.addItem(nombre, codigo)

        self.cmb_grupo.blockSignals(False)
        self.actualizar_estado_boton_cargar()

    def actualizar_estado_boton_cargar(self):
        tiene_capa = self.capa_seleccionada is not None
        tiene_categoria = self.cmb_categoria.currentData() is not None
        tiene_grupo = self.cmb_grupo.currentData() is not None
        self.btn_cargar.setEnabled(tiene_capa and tiene_categoria and tiene_grupo)

    # ------------------------------------------------------
    # VALIDACIÓN DE CAPAS
    # ------------------------------------------------------

    def analizar_capa(self, capa):
        """
        Valida que la capa sea de polígonos, tenga COD y tenga al menos un COD válido relacionado.
        Optimizado: lee solo el campo COD y no carga geometrías.
        """
        if not es_capa_poligonos(capa):
            return None

        campo_cod, indice_cod = encontrar_campo_cod(capa)
        if not campo_cod or indice_cod < 0:
            return None

        total = 0
        validos_formato = 0
        validos_relacionados = 0
        municipios = {}
        codigos_archivo = {}
        codigos_extraccion = {}
        codigos_completos = {}

        request = QgsFeatureRequest()
        try:
            request.setFlags(QgsFeatureRequest.NoGeometry)
        except Exception:
            pass

        for feature in capa.getFeatures(request):
            total += 1
            cod = normalizar_codigo(valor_atributo(feature, indice_cod))

            if not REGEX_COD.match(cod):
                continue

            validos_formato += 1
            cod_archivo = cod[:4]
            cod_municipal = cod[:5]
            cod_extraccion = cod[:7]
            referencia = self.catalogo_municipal.get(cod_municipal)

            if not referencia:
                continue

            validos_relacionados += 1

            if cod_municipal not in municipios:
                municipios[cod_municipal] = {
                    "referencia": referencia,
                    "cantidad": 0,
                }
            municipios[cod_municipal]["cantidad"] += 1

            codigos_archivo[cod_archivo] = codigos_archivo.get(cod_archivo, 0) + 1
            codigos_extraccion[cod_extraccion] = codigos_extraccion.get(cod_extraccion, 0) + 1

            if cod not in codigos_completos:
                codigos_completos[cod] = []
            codigos_completos[cod].append(feature.id())

        if validos_relacionados == 0:
            return None

        return {
            "capa": capa,
            "campo_cod": campo_cod,
            "indice_cod": indice_cod,
            "total": total,
            "validos_formato": validos_formato,
            "validos_relacionados": validos_relacionados,
            "municipios": municipios,
            "codigos_archivo": codigos_archivo,
            "codigos_extraccion": codigos_extraccion,
            "codigos_completos": codigos_completos,
        }

    def obtener_capas_validas(self):
        capas_validas = []

        for capa in QgsProject.instance().mapLayers().values():
            if not isinstance(capa, QgsVectorLayer):
                continue

            resumen = self.analizar_capa(capa)
            if not resumen:
                continue

            nombre_municipio = self.obtener_nombre_municipio_resumen(resumen)
            texto = "{}  |  {}".format(capa.name(), nombre_municipio)
            capas_validas.append((texto, capa, resumen))

        return capas_validas

    def obtener_nombre_municipio_resumen(self, resumen):
        municipios = resumen.get("municipios", {}) if resumen else {}
        if not municipios:
            return "Ninguno"

        if len(municipios) == 1:
            cod_municipal = list(municipios.keys())[0]
            referencia = municipios[cod_municipal]["referencia"]
            return referencia.get("MUNICIPIO", "Sin municipio")

        return "Varios municipios ({})".format(len(municipios))

    def seleccionar_capa(self):
        if not self.catalogo_municipal:
            QMessageBox.warning(
                self,
                "CENSO 2024",
                "No se cargó correctamente el catálogo municipal 00.csv."
            )
            return

        if not self.catalogo_db:
            QMessageBox.warning(
                self,
                "CENSO 2024",
                "No se cargó correctamente el catálogo de variables 0.csv."
            )
            return

        capas_validas = self.obtener_capas_validas()

        if not capas_validas:
            QMessageBox.information(
                self,
                "CENSO 2024",
                "No se encontró ningún mapa de manzanos por población urbana en el proyecto.\n\n"
                "Debe descargar primero un mapa desde el complemento GeoCenso2024."
                )
            self.close()
            return

        # En la ventana de selección se muestra solamente el nombre de la capa.
        # Internamente se conserva la referencia a la capa y su resumen.
        opciones = [capa.name() for _, capa, _ in capas_validas]

        seleccion, aceptado = QInputDialog.getItem(
            self,
            "Seleccionar Capa",
            "Seleccione una capa válida:",
            opciones,
            0,
            False
        )

        if not aceptado or not seleccion:
            return

        self.remover_join_anterior()

        for indice, nombre_capa in enumerate(opciones):
            if nombre_capa == seleccion:
                _, capa, resumen = capas_validas[indice]
                self.capa_seleccionada = capa
                self.campo_cod = resumen["campo_cod"]
                self.indice_cod = resumen["indice_cod"]
                self.resumen_capa = resumen
                break

        nombre_municipio = self.obtener_nombre_municipio_resumen(self.resumen_capa)
        self.lbl_municipio.setText("Municipio seleccionado: {}".format(nombre_municipio))

        self.cmb_categoria.setEnabled(True)
        self.cmb_grupo.setEnabled(True)
        self.actualizar_estado_boton_cargar()

    # ------------------------------------------------------
    # PARÁMETROS PREPARADOS
    # ------------------------------------------------------

    def obtener_cod_municipal_unico(self):
        municipios = {}
        if self.resumen_capa:
            municipios = self.resumen_capa.get("municipios", {})

        if len(municipios) != 1:
            return None

        return list(municipios.keys())[0]

    def obtener_codigo_archivo_unico(self):
        """
        Devuelve el código FILE de 4 caracteres obtenido directamente del COD de la capa.
        Ejemplo: U80110100001 -> U801, para descargar U801.parquet.
        """
        codigos_archivo = {}
        if self.resumen_capa:
            codigos_archivo = self.resumen_capa.get("codigos_archivo", {})

        if len(codigos_archivo) != 1:
            return None

        return list(codigos_archivo.keys())[0]

    def obtener_codigos_extraccion(self):
        """
        Devuelve los prefijos de 7 caracteres presentes en la capa seleccionada.
        Ejemplo: U80320100050 -> U803201.
        Estos prefijos se usan para extraer del Parquet el bloque correcto.
        """
        codigos_extraccion = {}
        if self.resumen_capa:
            codigos_extraccion = self.resumen_capa.get("codigos_extraccion", {})

        return sorted(codigos_extraccion.keys())

    def obtener_codigos_completos_capa(self):
        """
        Devuelve todos los COD completos de la capa seleccionada.
        Después de extraer por prefijo de 7 caracteres, estos COD se usan
        para conservar solo las filas del Parquet que coinciden elemento por elemento.
        """
        codigos_completos = {}
        if self.resumen_capa:
            codigos_completos = self.resumen_capa.get("codigos_completos", {})

        return sorted(codigos_completos.keys())

    def obtener_parametros_preparados(self, codigo_variable):
        """
        Construye los parámetros base para la futura carga de datos.

        FILE = primeros 4 caracteres del COD completo de la capa. Ejemplo: U801
        COD  = primeros 5 caracteres del COD municipal. Ejemplo: U8011
        COD_EXTRACCION = primeros 7 caracteres del COD de manzano. Ejemplo: U801101
        DB1  = segundo valor del archivo 0.csv según código interno. Ejemplo A1 -> 2
        DB2  = tercer valor del archivo 0.csv según código interno. Ejemplo A1 -> 15
        """
        cod_municipal = self.obtener_cod_municipal_unico()
        codigo_archivo = self.obtener_codigo_archivo_unico()
        codigos_extraccion = self.obtener_codigos_extraccion()
        codigos_completos = self.obtener_codigos_completos_capa()

        if not cod_municipal:
            raise Exception(
                "La capa seleccionada debe corresponder a un solo municipio para preparar FILE y COD."
            )

        if not codigo_archivo:
            raise Exception(
                "La capa seleccionada debe corresponder a un solo archivo base para preparar FILE.\n\n"
                "Ejemplo esperado: COD U80110100001 -> archivo U801.parquet."
            )

        if not codigos_extraccion:
            raise Exception(
                "No se pudo obtener el prefijo de extracción de 7 caracteres desde el COD de la capa seleccionada."
            )

        if not codigos_completos:
            raise Exception(
                "No se pudieron obtener los COD completos de la capa seleccionada para realizar la coincidencia final."
            )

        codigo_variable = texto_limpio(codigo_variable).upper()
        referencia_db = self.catalogo_db.get(codigo_variable)

        if not referencia_db:
            raise Exception(
                "No se encontró el código interno {} en el archivo 0.csv.".format(codigo_variable)
            )

        return {
            "FILE": codigo_archivo,
            "COD": cod_municipal,
            "COD_EXTRACCION": codigos_extraccion,
            "COD_EXTRACCION_TEXTO": "_".join(codigos_extraccion),
            "CODIGOS_CAPA": codigos_completos,
            "DB1": referencia_db.get("DB1", ""),
            "DB2": referencia_db.get("DB2", ""),
        }

    # ------------------------------------------------------
    # DESCARGA, EXTRACCIÓN Y JOIN
    # ------------------------------------------------------

    def remover_join_anterior(self):
        """Remueve un join temporal anterior si existiera de una versión previa del módulo."""
        try:
            if self.capa_seleccionada is not None and self.id_join_actual:
                self.capa_seleccionada.removeJoin(self.id_join_actual)
        except Exception:
            pass

        try:
            if self.capa_join_actual is not None:
                QgsProject.instance().removeMapLayer(self.capa_join_actual.id())
        except Exception:
            pass

        self.capa_join_actual = None
        self.id_join_actual = None

    def obtener_indices_columnas(self, capa_datos, db1, db2):
        """
        Extrae la columna 1 y el rango DB1:DB2.
        La numeración DB1/DB2 se interpreta como numeración humana, iniciando en 1.
        Ejemplo: DB1=2 y DB2=15 => columna 1 + columnas 2 a 15.
        """
        total_columnas = capa_datos.fields().count()

        db1 = convertir_entero(db1, "DB1")
        db2 = convertir_entero(db2, "DB2")

        if db1 < 1 or db2 < 1:
            raise Exception("DB1 y DB2 deben ser mayores o iguales a 1.")

        if db2 < db1:
            raise Exception("DB2 no puede ser menor que DB1. Revise el archivo 0.csv.")

        if db2 > total_columnas:
            raise Exception(
                "El rango DB1:DB2 excede la cantidad de columnas del archivo descargado.\n\n"
                "Columnas del archivo: {}\nDB1: {}\nDB2: {}".format(
                    total_columnas,
                    db1,
                    db2
                )
            )

        indices = [0]
        for indice in range(db1 - 1, db2):
            if indice not in indices:
                indices.append(indice)

        return indices

    def crear_tabla_filtrada_para_join(self, capa_datos, codigos_extraccion, codigos_capa, db1, db2, nombre_tabla):
        """
        Crea una tabla temporal sin geometría para el join.

        Optimizado:
        - Lee solo las columnas necesarias del Parquet/GeoParquet.
        - No lee geometría.
        - Aplica filtro por prefijo de 7 caracteres desde el proveedor cuando QGIS lo permite.
        - Mantiene la validación final COD-COD elemento por elemento.
        """
        indices = self.obtener_indices_columnas(capa_datos, db1, db2)
        campos_origen = capa_datos.fields()

        tabla = QgsVectorLayer("None", nombre_tabla, "memory")
        proveedor = tabla.dataProvider()

        campos_nuevos = []
        usados = set()

        for posicion, indice_origen in enumerate(indices):
            campo_origen = campos_origen[indice_origen]

            if posicion == 0:
                nombre = "COD"
                tipo = QVariant.String
            else:
                nombre = nombre_campo_unico(campo_origen.name(), usados)
                tipo = campo_origen.type()
                if tipo == QVariant.Invalid:
                    tipo = QVariant.String

            usados.add(nombre.upper())
            campos_nuevos.append(
                QgsField(
                    nombre,
                    tipo,
                    campo_origen.typeName(),
                    campo_origen.length(),
                    campo_origen.precision()
                )
            )

        proveedor.addAttributes(campos_nuevos)
        tabla.updateFields()
        campos_tabla = tabla.fields()

        if isinstance(codigos_extraccion, (list, tuple, set)):
            prefijos_extraccion = [normalizar_codigo(codigo) for codigo in codigos_extraccion if normalizar_codigo(codigo)]
        else:
            prefijos_extraccion = [normalizar_codigo(codigos_extraccion)]

        if not prefijos_extraccion:
            raise Exception("No se recibió ningún prefijo válido de 7 caracteres para filtrar el Parquet.")

        prefijos_extraccion = sorted(set(prefijos_extraccion))

        codigos_capa_set = set()
        for codigo in codigos_capa:
            codigo_normalizado = normalizar_codigo(codigo)
            if codigo_normalizado:
                codigos_capa_set.add(codigo_normalizado)

        if not codigos_capa_set:
            raise Exception("No se recibieron COD completos válidos de la capa para hacer la coincidencia elemento por elemento.")

        nombre_campo_cod_origen = campos_origen[indices[0]].name()

        def leer_features(request):
            nuevos = []
            total_revisados = 0

            for feature in capa_datos.getFeatures(request):
                total_revisados += 1
                atributos = feature.attributes()

                if not atributos:
                    continue

                cod_dato = normalizar_codigo(
                    valor_atributo_request(feature, atributos, indices, indices[0], 0)
                )

                # Validación local adicional, aunque el proveedor ya haya filtrado por prefijo.
                if cod_dato[:7] not in prefijos_extraccion:
                    continue

                # Coincidencia final elemento por elemento.
                if cod_dato not in codigos_capa_set:
                    continue

                valores = []
                for posicion, indice_origen in enumerate(indices):
                    valor = valor_atributo_request(
                        feature,
                        atributos,
                        indices,
                        indice_origen,
                        posicion
                    )
                    if posicion == 0:
                        valor = cod_dato
                    valores.append(valor)

                nuevo = QgsFeature(campos_tabla)
                nuevo.setAttributes(valores)
                nuevos.append(nuevo)

            return nuevos, total_revisados

        request_filtrado = crear_request_solo_atributos(indices, campos_origen)
        filtro_aplicado = False

        try:
            filtro = construir_filtro_prefijos_qgis(nombre_campo_cod_origen, prefijos_extraccion)
            if filtro:
                request_filtrado.setFilterExpression(filtro)
                filtro_aplicado = True
        except Exception:
            filtro_aplicado = False

        nuevos_features, total_revisados = leer_features(request_filtrado)

        # Respaldo: si el filtro del proveedor no devolvió nada, relee sin filtro.
        # Esto evita falsos negativos en instalaciones QGIS/GDAL con soporte limitado.
        if not nuevos_features and filtro_aplicado:
            request_sin_filtro = crear_request_solo_atributos(indices, campos_origen)
            nuevos_features, total_revisados = leer_features(request_sin_filtro)

        if not nuevos_features:
            raise Exception(
                "El archivo descargado no contiene registros que coincidan con la capa seleccionada.\n\n"
                "Primero se buscó por prefijo de 7 caracteres: {}.\n"
                "Luego se intentó coincidir por COD completo, elemento por elemento.\n\n"
                "Registros revisados: {}".format(
                    ", ".join(prefijos_extraccion),
                    total_revisados
                )
            )

        # Agrega por lotes para evitar una sola operación enorme en capas grandes.
        lote = []
        for nuevo in nuevos_features:
            lote.append(nuevo)
            if len(lote) >= 5000:
                proveedor.addFeatures(lote)
                lote = []

        if lote:
            proveedor.addFeatures(lote)

        tabla.updateExtents()

        return tabla, len(nuevos_features), len(indices)

    def aplicar_columnas_a_capa(self, tabla_datos, codigo_variable):
        """
        Copia los datos de la tabla preparada directamente a la capa de polígonos seleccionada.

        Optimizado:
        - Construye un diccionario COD -> valores.
        - Agrega campos en bloque.
        - Actualiza atributos por lote con dataProvider.changeAttributeValues cuando la capa no está en edición.
        - Si la capa ya está en edición, usa changeAttributeValues por entidad para respetar el modo edición.
        """
        if self.capa_seleccionada is None or not self.capa_seleccionada.isValid():
            raise Exception("La capa seleccionada no es válida.")

        if tabla_datos is None or not tabla_datos.isValid():
            raise Exception("La tabla preparada no es válida.")

        campos_tabla = tabla_datos.fields()
        indice_cod_tabla = campos_tabla.indexFromName("COD")

        if indice_cod_tabla < 0:
            raise Exception("La tabla preparada no tiene columna COD.")

        codigo_variable = texto_limpio(codigo_variable).upper()

        campos_existentes = set()
        for campo in self.capa_seleccionada.fields():
            campos_existentes.add(campo.name().upper())

        campos_a_copiar = []
        campos_repetidos = []

        for indice_origen, campo_origen in enumerate(campos_tabla):
            if indice_origen == indice_cod_tabla:
                continue

            nombre_destino = nombre_campo_base(campo_origen.name())

            if nombre_destino.upper() in campos_existentes:
                campos_repetidos.append(nombre_destino)
                continue

            campos_existentes.add(nombre_destino.upper())

            tipo = campo_origen.type()
            if tipo == QVariant.Invalid:
                tipo = QVariant.String

            campo_destino = QgsField(
                nombre_destino,
                tipo,
                campo_origen.typeName(),
                campo_origen.length(),
                campo_origen.precision()
            )

            campos_a_copiar.append({
                "indice_origen": indice_origen,
                "campo_origen": campo_origen.name(),
                "nombre_destino": nombre_destino,
                "campo_destino": campo_destino,
            })

        if campos_repetidos:
            raise BaseDatosYaCargada(
                "La capa ya tiene cargada la Base de Datos seleccionada.\n\n"
            )

        if not campos_a_copiar:
            raise Exception("No existen columnas de datos para copiar a la capa seleccionada.")

        datos_por_cod = {}
        indices_tabla = [indice_cod_tabla] + [item["indice_origen"] for item in campos_a_copiar]
        request_tabla = crear_request_solo_atributos(indices_tabla, campos_tabla)

        for feature in tabla_datos.getFeatures(request_tabla):
            atributos = feature.attributes()
            if not atributos:
                continue

            cod = normalizar_codigo(
                valor_atributo_request(feature, atributos, indices_tabla, indice_cod_tabla, 0)
            )
            if not cod:
                continue

            valores = []
            for posicion in range(1, len(indices_tabla)):
                indice_origen = indices_tabla[posicion]
                valor = valor_atributo_request(
                    feature,
                    atributos,
                    indices_tabla,
                    indice_origen,
                    posicion
                )
                valores.append(valor)

            datos_por_cod[cod] = valores

        if not datos_por_cod:
            raise Exception("No se encontraron registros válidos con COD en la tabla preparada.")

        capa = self.capa_seleccionada
        proveedor_capa = capa.dataProvider()
        estaba_en_edicion = capa.isEditable()

        try:
            if estaba_en_edicion:
                for item in campos_a_copiar:
                    if not capa.addAttribute(item["campo_destino"]):
                        raise Exception(
                            "No se pudo crear el campo {} en la capa seleccionada.".format(
                                item["nombre_destino"]
                            )
                        )
            else:
                campos_destino = [item["campo_destino"] for item in campos_a_copiar]
                if not proveedor_capa.addAttributes(campos_destino):
                    raise Exception(
                        "No se pudieron crear los campos nuevos en la capa seleccionada.\n\n"
                        "Verifique que la capa permita agregar campos y modificar atributos."
                    )

            capa.updateFields()

            indices_destino = []
            for item in campos_a_copiar:
                indice_destino = capa.fields().indexFromName(item["nombre_destino"])
                if indice_destino < 0:
                    raise Exception(
                        "El campo {} fue creado, pero QGIS no pudo ubicarlo para cargar datos.".format(
                            item["nombre_destino"]
                        )
                    )
                indices_destino.append(indice_destino)

            mapa_cod_ids = {}
            if self.resumen_capa:
                codigos_resumen = self.resumen_capa.get("codigos_completos", {})
                for cod_resumen, ids_resumen in codigos_resumen.items():
                    cod_normalizado = normalizar_codigo(cod_resumen)
                    if not cod_normalizado:
                        continue

                    if isinstance(ids_resumen, (list, tuple, set)):
                        mapa_cod_ids[cod_normalizado] = list(ids_resumen)

            if not mapa_cod_ids:
                indice_cod_capa = capa.fields().indexFromName(self.campo_cod)
                if indice_cod_capa < 0:
                    raise Exception("No se pudo ubicar el campo COD de la capa seleccionada.")

                request_capa = crear_request_solo_atributos([indice_cod_capa], capa.fields())
                for feature in capa.getFeatures(request_capa):
                    cod_capa = normalizar_codigo(valor_atributo(feature, indice_cod_capa))
                    if not cod_capa:
                        continue
                    if cod_capa not in mapa_cod_ids:
                        mapa_cod_ids[cod_capa] = []
                    mapa_cod_ids[cod_capa].append(feature.id())

            cambios = {}
            registros_coincidentes = 0

            for cod_capa, feature_ids in mapa_cod_ids.items():
                valores = datos_por_cod.get(cod_capa)

                if valores is None:
                    continue

                for feature_id in feature_ids:
                    cambios_feature = {}
                    for indice_destino, valor in zip(indices_destino, valores):
                        cambios_feature[indice_destino] = valor

                    if cambios_feature:
                        cambios[feature_id] = cambios_feature
                        registros_coincidentes += 1

            if registros_coincidentes == 0 or not cambios:
                raise Exception(
                    "No hubo coincidencias exactas COD-COD entre la capa seleccionada y la base descargada.\n\n"
                    "Primero se extrajo la base por prefijo de 7 caracteres, pero ningún COD completo coincidió elemento por elemento.\n\n"
                    "No se guardaron columnas nuevas."
                )

            celdas_actualizadas = 0

            if estaba_en_edicion:
                for feature_id, cambios_feature in cambios.items():
                    aplicado = False

                    try:
                        aplicado = capa.changeAttributeValues(feature_id, cambios_feature)
                    except Exception:
                        aplicado = False

                    if aplicado:
                        celdas_actualizadas += len(cambios_feature)
                    else:
                        for indice_destino, valor in cambios_feature.items():
                            if capa.changeAttributeValue(feature_id, indice_destino, valor):
                                celdas_actualizadas += 1
            else:
                if not proveedor_capa.changeAttributeValues(cambios):
                    raise Exception(
                        "No se pudieron actualizar los atributos de la capa seleccionada."
                    )
                celdas_actualizadas = sum(len(valores) for valores in cambios.values())

            capa.updateFields()
            capa.triggerRepaint()

            return {
                "registros_base": len(datos_por_cod),
                "registros_coincidentes": registros_coincidentes,
                "columnas_creadas": len(campos_a_copiar),
                "celdas_actualizadas": celdas_actualizadas,
                "campos_creados": [item["nombre_destino"] for item in campos_a_copiar],
                "modo_edicion": estaba_en_edicion,
            }

        except Exception:
            # Si la capa estaba en edición, los cambios quedan en el buffer de edición de QGIS.
            # No se hace rollback automático para no borrar posibles ediciones previas del usuario.
            raise


    # ------------------------------------------------------
    # MENSAJE DE PROCESO
    # ------------------------------------------------------

    def mostrar_mensaje_vinculando(self):
        """Muestra una ventana temporal sin botones mientras se vinculan los datos."""
        self.ocultar_mensaje_vinculando()

        dialogo = QDialog(self)
        dialogo.setModal(True)

        # Ventana sin barra de título, sin botón cerrar y sin botones internos.
        try:
            dialogo.setWindowFlags(dialogo.windowFlags() | Qt.FramelessWindowHint)
        except Exception:
            pass

        layout = QVBoxLayout(dialogo)

        etiqueta = QLabel("Se están vinculando los datos. Este proceso puede demorar unos minutos.")
        etiqueta.setAlignment(QT_ALIGN_CENTER)
        etiqueta.setWordWrap(True)
        etiqueta.setMinimumWidth(360)
        etiqueta.setStyleSheet(
            "font-size: 11pt; "
            "font-weight: bold; "
            "padding: 18px;"
        )
        layout.addWidget(etiqueta)
        dialogo.setFixedSize(440, 125)
        dialogo.show()
        dialogo.raise_()
        dialogo.activateWindow()

        self.dialogo_vinculando = dialogo

        # Permite que QGIS pinte la ventana antes de iniciar la descarga/proceso pesado.
        QApplication.processEvents()

    def ocultar_mensaje_vinculando(self):
        """Cierra la ventana temporal de vinculación si está visible."""
        dialogo = getattr(self, "dialogo_vinculando", None)

        if dialogo is not None:
            try:
                dialogo.close()
                dialogo.deleteLater()
            except Exception:
                pass

        self.dialogo_vinculando = None
        QApplication.processEvents()

    # ------------------------------------------------------
    # BOTONES
    # ------------------------------------------------------

    def cargar_datos(self):
        """
        Descarga FILE.parquet / FILE.geoparquet desde GitHub, extrae la base
        según COD municipal y columnas DB1:DB2, y copia las columnas directamente
        a la capa seleccionada usando la relación COD-COD.

        No carga la base Parquet/GeoParquet ni la tabla preparada al panel de capas.
        """
        if self.capa_seleccionada is None:
            QMessageBox.warning(self, "CENSO 2024", "Primero seleccione una capa válida.")
            return

        categoria = self.cmb_categoria.currentData()
        grupo_codigo = self.cmb_grupo.currentData()
        grupo_texto = self.cmb_grupo.currentText()
        nombre_municipio = self.obtener_nombre_municipio_resumen(self.resumen_capa)

        if not categoria or not grupo_codigo:
            QMessageBox.warning(
                self,
                "CENSO 2024",
                "Seleccione una característica y un grupo de variables censales."
            )
            return

        self.mostrar_mensaje_vinculando()

        try:
            parametros = self.obtener_parametros_preparados(grupo_codigo)

            # Limpia cualquier tabla/join anterior antes de cargar una nueva base.
            self.remover_join_anterior()

            ruta_parquet, url_usada, archivo_usado = descargar_archivo_github(
                parametros["FILE"]
            )
            capa_datos = abrir_parquet_como_capa(
                ruta_parquet,
                "{}_datos".format(archivo_usado)
            )

            nombre_tabla = "BD_{}_{}_{}".format(
                parametros["FILE"],
                parametros["COD_EXTRACCION_TEXTO"],
                grupo_codigo
            )

            tabla_join, filas, columnas = self.crear_tabla_filtrada_para_join(
                capa_datos,
                parametros["COD_EXTRACCION"],
                parametros["CODIGOS_CAPA"],
                parametros["DB1"],
                parametros["DB2"],
                nombre_tabla
            )

            # Copia las columnas directamente a la capa seleccionada mediante COD-COD.
            resultado_columnas = self.aplicar_columnas_a_capa(tabla_join, grupo_codigo)

        except BaseDatosYaCargada as aviso:
            self.ocultar_mensaje_vinculando()
            QMessageBox.information(self, "CENSO 2024", str(aviso))
            self.close()
            return

        except Exception as error:
            self.ocultar_mensaje_vinculando()
            QMessageBox.critical(self, "Error CENSO 2024", str(error))
            return

        self.ocultar_mensaje_vinculando()

        QMessageBox.information(
            self,
            "CENSO 2024",
            "La base de datos '{}' se cargó correctamente a la capa '{}'.\n\n"
            "Puede revisar la información en la tabla de atributos de la capa.".format(
                grupo_texto,
                self.capa_seleccionada.name(),
                nombre_municipio,
                self.campo_cod,
                categoria,
                url_usada,
                archivo_usado,
                parametros["FILE"],
                parametros["COD"],
                parametros["DB1"],
                parametros["DB2"],
                resultado_columnas["registros_base"],
                resultado_columnas["registros_coincidentes"],
                resultado_columnas["columnas_creadas"],
                resultado_columnas["celdas_actualizadas"],
                " y están pendientes de guardar porque la capa ya estaba en modo edición" if resultado_columnas["modo_edicion"] else ""
            )
        )

        self.close()

    def limpiar(self):
        self.remover_join_anterior()

        self.capa_seleccionada = None
        self.campo_cod = None
        self.indice_cod = -1
        self.resumen_capa = None
        self.capa_join_actual = None
        self.id_join_actual = None

        self.lbl_municipio.setText("Municipio seleccionado: Ninguno")

        self.cmb_categoria.blockSignals(True)
        self.cmb_categoria.setCurrentIndex(0)
        self.cmb_categoria.blockSignals(False)

        self.actualizar_grupo_variables()
        self.cmb_categoria.setEnabled(False)
        self.cmb_grupo.setEnabled(False)
        self.actualizar_estado_boton_cargar()


# ==========================================================
# EJECUTAR VENTANA EN QGIS
# ==========================================================

try:
    CENSO2024_DLG.close()
except Exception:
    pass

try:
    CENSO2024_DLG = Censo2024Dialog(obtener_ventana_qgis())
    CENSO2024_DLG.show()

except Exception as error:
    QMessageBox.critical(
        None,
        "Error CENSO 2024",
        str(error)
    )
