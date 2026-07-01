# -*- coding: utf-8 -*-

import csv
import os
import re
import tempfile
import urllib.request

from qgis.PyQt.QtGui import QPixmap

from qt_compat import (
    QT_ALIGN_CENTER,
    QT_KEEP_ASPECT_RATIO,
    QT_SMOOTH_TRANSFORMATION,
)

from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFillSymbol,
    QgsMarkerSymbol,
    QgsProject,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
    QgsWkbTypes,
)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

RUTA_CSV = os.path.join(os.path.dirname(__file__), "00.csv")

# Logo que aparecerá en la parte superior de la ventana.
# Guarde el archivo GEOC.jpg en C:\INE\GEOC.jpg
RUTA_LOGO = os.path.join(os.path.dirname(__file__), "GEOC.jpg")

TEXTO_CREDITOS = (
    "Sistematizado y Desarrollado por: "
    "Ing. MSc. Jorge Ayala Niño de Guzmán"
)

URL_BASE_PUNTOS = (
    "https://raw.githubusercontent.com/"
    "umayakuy/QGISCenso2024/main/data/puntos"
)

URL_BASE_MUNICIPIOS = (
    "https://raw.githubusercontent.com/"
    "umayakuy/QGISCenso2024/main/data/municipios"
)

# El script intentará descargar primero .parquet y luego .geoparquet
EXTENSIONES_GEOPARQUET = ["parquet", "geoparquet"]


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================

def obtener_ventana_qgis():
    try:
        return iface.mainWindow()
    except Exception:
        return None


def limpiar_nombre_archivo(texto):
    texto = texto.strip()
    texto = re.sub(r'[\\/:*?"<>|]', "_", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto


def crear_ruta_temporal_geoparquet(cod, municipio, tipo):
    nombre_municipio = limpiar_nombre_archivo(municipio)

    archivo_temporal = tempfile.NamedTemporaryFile(
        prefix=f"{cod}_{nombre_municipio}_{tipo}_",
        suffix=".parquet",
        delete=False
    )

    ruta_temporal = archivo_temporal.name
    archivo_temporal.close()

    return ruta_temporal


def crear_urls_geoparquet(url_base, cod):
    urls = []

    for extension in EXTENSIONES_GEOPARQUET:
        urls.append(f"{url_base}/{cod}.{extension}")

    return urls


def descargar_desde_urls_posibles(urls_posibles, ruta_temporal):
    errores = []

    for url in urls_posibles:
        try:
            urllib.request.urlretrieve(url, ruta_temporal)

            if not os.path.exists(ruta_temporal):
                raise Exception("No se pudo crear el archivo temporal.")

            if os.path.getsize(ruta_temporal) == 0:
                raise Exception("El archivo temporal descargado está vacío.")

            return url

        except Exception as error:
            errores.append(f"{url}\n  {str(error)}")

            try:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception:
                pass

    raise Exception(
        "No se pudo descargar el GeoParquet desde ninguna URL.\n\n"
        "URLs intentadas:\n\n"
        + "\n\n".join(errores)
    )


def es_geometria_poligono(capa):
    tipo = QgsWkbTypes.geometryType(capa.wkbType())

    try:
        return tipo == QgsWkbTypes.GeometryType.PolygonGeometry
    except AttributeError:
        return tipo == QgsWkbTypes.PolygonGeometry


def es_geometria_punto(capa):
    tipo = QgsWkbTypes.geometryType(capa.wkbType())

    try:
        return tipo == QgsWkbTypes.GeometryType.PointGeometry
    except AttributeError:
        return tipo == QgsWkbTypes.PointGeometry


def crear_capa_borrador_temporal(capa_origen, nombre_capa):
    """
    Convierte una capa GeoParquet descargada en una capa temporal de memoria.
    La capa final ya no depende del archivo temporal descargado.
    """

    crs = capa_origen.crs()
    wkb_type = capa_origen.wkbType()
    geometria = QgsWkbTypes.displayString(wkb_type)

    if crs.isValid() and crs.authid():
        uri = f"{geometria}?crs={crs.authid()}"
    else:
        uri = geometria

    capa_memoria = QgsVectorLayer(uri, nombre_capa, "memory")

    if not capa_memoria.isValid():
        raise Exception("No se pudo crear la capa temporal de memoria.")

    proveedor = capa_memoria.dataProvider()

    proveedor.addAttributes(capa_origen.fields())
    capa_memoria.updateFields()

    features_nuevas = []

    for feature in capa_origen.getFeatures():
        nueva_feature = QgsFeature(capa_memoria.fields())
        nueva_feature.setGeometry(feature.geometry())
        nueva_feature.setAttributes(feature.attributes())
        features_nuevas.append(nueva_feature)

    proveedor.addFeatures(features_nuevas)
    capa_memoria.updateExtents()

    return capa_memoria


def aplicar_estilo_poligono_sin_relleno(capa):
    """
    Aplica estilo sin relleno a la capa poligonal.
    """

    if not es_geometria_poligono(capa):
        return

    simbolo = QgsFillSymbol.createSimple({
        "style": "no",
        "outline_style": "solid",
        "outline_color": "0,0,0,255",
        "outline_width": "0.60",
    })

    capa.setRenderer(QgsSingleSymbolRenderer(simbolo))
    capa.triggerRepaint()


def normalizar_texto(valor):
    if valor is None:
        return ""

    texto = str(valor).strip().lower()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }

    for original, reemplazo in reemplazos.items():
        texto = texto.replace(original, reemplazo)

    return texto


def aplicar_estilo_puntos_amanzanado(capa):
    """
    Aplica estilo categorizado a la capa de puntos según la columna 'amanzanado'.

    si / sí / SI = rojo, más grande
    no / NO      = verde
    otros        = gris
    """

    if not es_geometria_punto(capa):
        return

    campo_amanzanado = None

    for campo in capa.fields():
        if campo.name().lower() == "amanzanado":
            campo_amanzanado = campo.name()
            break

    if not campo_amanzanado:
        return

    valores_unicos = []

    for feature in capa.getFeatures():
        valor = feature[campo_amanzanado]

        if valor not in valores_unicos:
            valores_unicos.append(valor)

    categorias = []

    for valor in valores_unicos:
        texto = normalizar_texto(valor)

        if texto in ["si", "s", "1", "true", "yes"]:
            simbolo = QgsMarkerSymbol.createSimple({
                "name": "circle",
                "color": "220,0,0,255",
                "outline_color": "0,0,0,255",
                "outline_width": "0.25",
                "size": "4.00",
            })

            etiqueta = "Población Urbana"

        elif texto in ["no", "n", "0", "false"]:
            simbolo = QgsMarkerSymbol.createSimple({
                "name": "circle",
                "color": "255,165,0,255",
                "outline_color": "0,0,0,255",
                "outline_width": "0.20",
                "size": "3.00",
            })

            etiqueta = "Población Rural"

        else:
            simbolo = QgsMarkerSymbol.createSimple({
                "name": "circle",
                "color": "120,120,120,255",
                "outline_color": "0,0,0,255",
                "outline_width": "0.20",
                "size": "2.60",
            })

            etiqueta = "Sin dato"

        categoria = QgsRendererCategory(
            valor,
            simbolo,
            etiqueta
        )

        categorias.append(categoria)

    renderer = QgsCategorizedSymbolRenderer(
        campo_amanzanado,
        categorias
    )

    capa.setRenderer(renderer)
    capa.triggerRepaint()


def zoom_a_capa(capa):
    """
    Hace zoom automático a la extensión de la capa cargada.
    Preferentemente se usa la capa del municipio.
    Compatible con QGIS 3 y QGIS 4.
    """

    try:
        if capa is None or not capa.isValid():
            return

        extent = capa.extent()

        if extent.isEmpty():
            return

        canvas = iface.mapCanvas()

        crs_capa = capa.crs()
        crs_proyecto = QgsProject.instance().crs()

        if crs_capa.isValid() and crs_proyecto.isValid() and crs_capa != crs_proyecto:
            transformacion = QgsCoordinateTransform(
                crs_capa,
                crs_proyecto,
                QgsProject.instance()
            )
            extent = transformacion.transformBoundingBox(extent)

        canvas.setExtent(extent)
        canvas.zoomScale(canvas.scale() * 1.15)
        canvas.refresh()

        iface.setActiveLayer(capa)

    except Exception:
        pass


def descargar_geoparquet_como_capa_temporal(urls_posibles, cod, municipio, tipo):
    """
    Descarga un GeoParquet, lo carga en QGIS, lo convierte en capa temporal
    y elimina el archivo temporal.
    """

    ruta_temporal = crear_ruta_temporal_geoparquet(cod, municipio, tipo)

    try:
        url_usada = descargar_desde_urls_posibles(
            urls_posibles,
            ruta_temporal
        )

        capa_archivo = QgsVectorLayer(ruta_temporal, municipio, "ogr")

        if not capa_archivo.isValid():
            raise Exception(
                "El archivo fue descargado, pero QGIS no pudo cargarlo como GeoParquet válido.\n\n"
                "Posibles causas:\n"
                "- El archivo no es GeoParquet válido.\n"
                "- Tu instalación de QGIS/GDAL no tiene soporte para Parquet/Arrow.\n"
                "- El archivo no tiene geometría reconocible."
            )

        capa_temporal = crear_capa_borrador_temporal(
            capa_archivo,
            municipio
        )

        return capa_temporal, url_usada

    finally:
        try:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
        except Exception:
            pass


# ==========================================================
# VENTANA PRINCIPAL
# ==========================================================

class Censo2024Dialog(QDialog):
    def __init__(self, ruta_csv, parent=None):
        super().__init__(parent)

        self.ruta_csv = ruta_csv
        self.datos = self.leer_csv(ruta_csv)
        self.cod_actual = ""

        self.setWindowTitle("CENSO 2024 - Descargar Mapa Municipal")
        self.setMinimumWidth(620)
        self.setMinimumHeight(430)

        self.crear_interfaz()
        self.cargar_departamentos()

    def leer_csv(self, ruta_csv):
        if not os.path.exists(ruta_csv):
            raise FileNotFoundError(
                f"No se encontró el archivo CSV:\n{ruta_csv}"
            )

        with open(ruta_csv, "r", encoding="utf-8-sig", newline="") as archivo:
            contenido_inicial = archivo.read(2048)
            archivo.seek(0)

            try:
                dialecto = csv.Sniffer().sniff(
                    contenido_inicial,
                    delimiters=";,"
                )
                separador = dialecto.delimiter
            except Exception:
                separador = ";"

            lector = csv.DictReader(archivo, delimiter=separador)
            columnas = lector.fieldnames or []

            columnas_requeridas = [
                "DEPARTAMENTO",
                "PROVINCIA",
                "MUNICIPIO",
                "COD",
            ]

            faltantes = [
                columna for columna in columnas_requeridas
                if columna not in columnas
            ]

            if faltantes:
                raise ValueError(
                    "El archivo CSV no tiene las columnas requeridas:\n"
                    + ", ".join(faltantes)
                    + "\n\nColumnas encontradas:\n"
                    + ", ".join(columnas)
                )

            datos = []

            for fila in lector:
                nueva_fila = {}

                for campo, valor in fila.items():
                    if valor is None:
                        nueva_fila[campo] = ""
                    else:
                        nueva_fila[campo] = str(valor).strip()

                datos.append(nueva_fila)

        if not datos:
            raise ValueError("El archivo CSV está vacío.")

        return datos

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

        if os.path.exists(RUTA_LOGO):
            pixmap = QPixmap(RUTA_LOGO)

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
            self.lbl_logo.setText(
                "Logo no encontrado: C:\\INE\\GEOC.jpg"
            )

        layout_principal.addWidget(self.lbl_logo)

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

    def crear_interfaz(self):
        layout_principal = QVBoxLayout(self)

        self.agregar_logo(layout_principal)

        grupo_seleccion = QGroupBox("Mapas Municipales (Poblaciones/Puntos)")
        grid = QGridLayout(grupo_seleccion)

        self.cmb_departamento = QComboBox()
        self.cmb_provincia = QComboBox()
        self.cmb_municipio = QComboBox()

        self.cmb_departamento.currentTextChanged.connect(
            self.cargar_provincias
        )
        self.cmb_provincia.currentTextChanged.connect(
            self.cargar_municipios
        )
        self.cmb_municipio.currentTextChanged.connect(
            self.seleccionar_municipio
        )

        grid.addWidget(QLabel("Departamento:"), 0, 0)
        grid.addWidget(self.cmb_departamento, 0, 1)

        grid.addWidget(QLabel("Provincia:"), 1, 0)
        grid.addWidget(self.cmb_provincia, 1, 1)

        grid.addWidget(QLabel("Municipio:"), 2, 0)
        grid.addWidget(self.cmb_municipio, 2, 1)

        layout_principal.addWidget(grupo_seleccion)

        self.lbl_estado = QLabel(f"Registros cargados: {len(self.datos)}")
        layout_principal.addWidget(self.lbl_estado)

        layout_botones = QHBoxLayout()

        self.btn_descargar = QPushButton("Descargar Mapa")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_cerrar = QPushButton("Cerrar")

        self.btn_descargar.setEnabled(False)

        self.btn_descargar.clicked.connect(self.descargar_mapa)
        self.btn_limpiar.clicked.connect(self.limpiar_seleccion)
        self.btn_cerrar.clicked.connect(self.close)

        layout_botones.addStretch()
        layout_botones.addWidget(self.btn_descargar)
        layout_botones.addWidget(self.btn_limpiar)
        layout_botones.addWidget(self.btn_cerrar)

        layout_principal.addLayout(layout_botones)

        self.agregar_creditos(layout_principal)

    def limpiar_combo(self, combo, texto_inicial):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(texto_inicial)
        combo.blockSignals(False)

    def valores_unicos(self, campo, filtros=None):
        filtros = filtros or {}

        vistos = set()
        valores = []

        for fila in self.datos:
            cumple = True

            for campo_filtro, valor_filtro in filtros.items():
                if fila.get(campo_filtro, "") != valor_filtro:
                    cumple = False
                    break

            if not cumple:
                continue

            valor = fila.get(campo, "")

            if valor and valor not in vistos:
                vistos.add(valor)
                valores.append(valor)

        return valores

    def cargar_departamentos(self):
        self.cod_actual = ""
        self.btn_descargar.setEnabled(False)

        self.cmb_departamento.blockSignals(True)
        self.cmb_departamento.clear()
        self.cmb_departamento.addItem("-- Seleccione departamento --")

        departamentos = self.valores_unicos("DEPARTAMENTO")
        self.cmb_departamento.addItems(departamentos)

        self.cmb_departamento.blockSignals(False)

        self.limpiar_combo(
            self.cmb_provincia,
            "-- Seleccione provincia --"
        )
        self.limpiar_combo(
            self.cmb_municipio,
            "-- Seleccione municipio --"
        )

        self.lbl_estado.setText(f"Registros cargados: {len(self.datos)}")

    def cargar_provincias(self):
        self.cod_actual = ""
        self.btn_descargar.setEnabled(False)

        departamento = self.cmb_departamento.currentText()

        self.cmb_provincia.blockSignals(True)
        self.cmb_provincia.clear()
        self.cmb_provincia.addItem("-- Seleccione provincia --")

        if departamento and not departamento.startswith("--"):
            provincias = self.valores_unicos(
                "PROVINCIA",
                {
                    "DEPARTAMENTO": departamento
                }
            )
            self.cmb_provincia.addItems(provincias)

            self.lbl_estado.setText(
                f"Departamento seleccionado: {departamento}"
            )
        else:
            self.lbl_estado.setText(f"Registros cargados: {len(self.datos)}")

        self.cmb_provincia.blockSignals(False)

        self.limpiar_combo(
            self.cmb_municipio,
            "-- Seleccione municipio --"
        )

    def cargar_municipios(self):
        self.cod_actual = ""
        self.btn_descargar.setEnabled(False)

        departamento = self.cmb_departamento.currentText()
        provincia = self.cmb_provincia.currentText()

        self.cmb_municipio.blockSignals(True)
        self.cmb_municipio.clear()
        self.cmb_municipio.addItem("-- Seleccione municipio --")

        if (
            departamento
            and provincia
            and not departamento.startswith("--")
            and not provincia.startswith("--")
        ):
            municipios = self.valores_unicos(
                "MUNICIPIO",
                {
                    "DEPARTAMENTO": departamento,
                    "PROVINCIA": provincia,
                }
            )
            self.cmb_municipio.addItems(municipios)

            self.lbl_estado.setText(
                f"Selección: {departamento} / {provincia}"
            )

        self.cmb_municipio.blockSignals(False)

    def seleccionar_municipio(self):
        self.cod_actual = ""
        self.btn_descargar.setEnabled(False)

        departamento = self.cmb_departamento.currentText()
        provincia = self.cmb_provincia.currentText()
        municipio = self.cmb_municipio.currentText()

        if (
            not departamento
            or not provincia
            or not municipio
            or departamento.startswith("--")
            or provincia.startswith("--")
            or municipio.startswith("--")
        ):
            return

        for fila in self.datos:
            if (
                fila.get("DEPARTAMENTO") == departamento
                and fila.get("PROVINCIA") == provincia
                and fila.get("MUNICIPIO") == municipio
            ):
                self.cod_actual = fila.get("COD", "")
                self.btn_descargar.setEnabled(True)

                self.lbl_estado.setText(
                    f"Municipio seleccionado: {municipio}"
                )
                return

        self.lbl_estado.setText(
            "No se encontró el mapa para la selección realizada."
        )

    def descargar_mapa(self):
        cod = self.cod_actual.strip()
        municipio = self.cmb_municipio.currentText().strip()

        if not cod or not municipio or municipio.startswith("--"):
            QMessageBox.warning(
                self,
                "Datos incompletos",
                "Primero seleccione departamento, provincia y municipio."
            )
            return

        urls_puntos = crear_urls_geoparquet(URL_BASE_PUNTOS, cod)
        urls_municipios = crear_urls_geoparquet(URL_BASE_MUNICIPIOS, cod)

        try:
            self.lbl_estado.setText(f"Descargando GeoParquet de {municipio}...")
            QApplication.processEvents()

            capa_puntos, url_puntos_usada = descargar_geoparquet_como_capa_temporal(
                urls_puntos,
                cod,
                municipio,
                "puntos"
            )

            capa_municipio, url_municipio_usada = descargar_geoparquet_como_capa_temporal(
                urls_municipios,
                cod,
                municipio,
                "municipios"
            )

            aplicar_estilo_poligono_sin_relleno(capa_municipio)
            aplicar_estilo_puntos_amanzanado(capa_puntos)

            QgsProject.instance().addMapLayer(capa_municipio)
            QgsProject.instance().addMapLayer(capa_puntos)

            # ZOOM AUTOMÁTICO A LA CAPA DEL MUNICIPIO
            zoom_a_capa(capa_municipio)

            self.lbl_estado.setText(
                f"Mapas GeoParquet cargados como capas temporales: {municipio}"
            )

            self.close()

        except Exception as error:
            QMessageBox.critical(
                self,
                "Error al descargar GeoParquet",
                f"No se pudo descargar o cargar uno de los mapas GeoParquet.\n\n"
                f"URLs puntos intentadas:\n"
                f"{chr(10).join(urls_puntos)}\n\n"
                f"URLs municipios intentadas:\n"
                f"{chr(10).join(urls_municipios)}\n\n"
                f"Detalle del error:\n{str(error)}"
            )

    def limpiar_seleccion(self):
        self.cargar_departamentos()


# ==========================================================
# EJECUTAR VENTANA EN QGIS
# ==========================================================

try:
    CENSO2024_DLG.close()
except Exception:
    pass

try:
    CENSO2024_DLG = Censo2024Dialog(
        RUTA_CSV,
        obtener_ventana_qgis()
    )
    CENSO2024_DLG.show()

except Exception as error:
    QMessageBox.critical(
        None,
        "Error CENSO 2024",
        str(error)
    )