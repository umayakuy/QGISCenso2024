# -*- coding: utf-8 -*-

import csv
import os
import re

from qgis.PyQt.QtGui import QPixmap

from qt_compat import (
    QT_ALIGN_CENTER,
    QT_KEEP_ASPECT_RATIO,
    QT_SMOOTH_TRANSFORMATION,
)

from qgis.PyQt.QtWidgets import (
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


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

# Archivo base de municipios.
RUTA_CSV = os.path.join(os.path.dirname(__file__), "00.csv")

# Archivo con la lista de poblaciones urbanas.
# Debe contener mínimamente las columnas: ID, nombre, MCOD
RUTA_CODLISTA = os.path.join(os.path.dirname(__file__), "codlista.csv")

# Logo que aparecerá en la parte superior de la ventana.
# Guarde el archivo GEOC.jpg junto al script.
RUTA_LOGO = os.path.join(os.path.dirname(__file__), "GEOC.jpg")

TEXTO_CREDITOS = (
    "Sistematizado y Desarrollado por: "
    "Ing. MSc. Jorge Ayala Niño de Guzmán"
)


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


def normalizar_codigo(valor):
    """
    Normaliza códigos para comparación exacta como texto.
    No convierte a número para no perder ceros a la izquierda.
    """

    if valor is None:
        return ""

    return str(valor).strip()


def leer_csv_dict(ruta_csv, columnas_requeridas, nombre_archivo):
    """
    Lee un CSV con separador automático ; o , y valida columnas.
    Devuelve todas las filas con valores limpios.
    """

    if not os.path.exists(ruta_csv):
        raise FileNotFoundError(
            f"No se encontró el archivo {nombre_archivo}:\n{ruta_csv}"
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

        faltantes = [
            columna for columna in columnas_requeridas
            if columna not in columnas
        ]

        if faltantes:
            raise ValueError(
                f"El archivo {nombre_archivo} no tiene las columnas requeridas:\n"
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
        raise ValueError(f"El archivo {nombre_archivo} está vacío.")

    return datos


# ==========================================================
# VENTANA PRINCIPAL
# ==========================================================

class Censo2024Dialog(QDialog):
    def __init__(self, ruta_csv, ruta_codlista, parent=None):
        super().__init__(parent)

        self.ruta_csv = ruta_csv
        self.ruta_codlista = ruta_codlista

        self.datos = self.leer_csv(ruta_csv)
        self.datos_codlista = self.leer_codlista_csv(ruta_codlista)

        self.cod_actual = ""
        self.id_lista_actual = ""
        self.nombre_poblacion_actual = ""
        self.mcod_actual = ""

        self.setWindowTitle("CENSO 2024 - Población Urbana")
        self.setMinimumWidth(660)
        self.setMinimumHeight(470)

        self.crear_interfaz()
        self.cargar_departamentos()

    def leer_csv(self, ruta_csv):
        return leer_csv_dict(
            ruta_csv,
            [
                "DEPARTAMENTO",
                "PROVINCIA",
                "MUNICIPIO",
                "COD",
            ],
            "00.csv"
        )

    def leer_codlista_csv(self, ruta_csv):
        return leer_csv_dict(
            ruta_csv,
            [
                "ID",
                "nombre",
                "MCOD",
            ],
            "codlista.csv"
        )

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
                "Logo no encontrado: GEOC.jpg"
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

        grupo_seleccion = QGroupBox("Selección de Población Urbana")
        grid = QGridLayout(grupo_seleccion)

        self.cmb_departamento = QComboBox()
        self.cmb_provincia = QComboBox()
        self.cmb_municipio = QComboBox()
        self.cmb_poblacion_urbana = QComboBox()

        self.cmb_departamento.currentTextChanged.connect(
            self.cargar_provincias
        )
        self.cmb_provincia.currentTextChanged.connect(
            self.cargar_municipios
        )
        self.cmb_municipio.currentTextChanged.connect(
            self.seleccionar_municipio
        )
        self.cmb_poblacion_urbana.currentIndexChanged.connect(
            self.seleccionar_poblacion_urbana
        )

        grid.addWidget(QLabel("Departamento:"), 0, 0)
        grid.addWidget(self.cmb_departamento, 0, 1)

        grid.addWidget(QLabel("Provincia:"), 1, 0)
        grid.addWidget(self.cmb_provincia, 1, 1)

        grid.addWidget(QLabel("Municipio:"), 2, 0)
        grid.addWidget(self.cmb_municipio, 2, 1)

        grid.addWidget(QLabel("Nombre de Población Urbana:"), 3, 0)
        grid.addWidget(self.cmb_poblacion_urbana, 3, 1)

        layout_principal.addWidget(grupo_seleccion)

        self.lbl_estado = QLabel(
            f"Registros cargados: {len(self.datos)} municipios / "
            f"{len(self.datos_codlista)} poblaciones urbanas"
        )
        self.lbl_estado.setWordWrap(True)
        layout_principal.addWidget(self.lbl_estado)

        layout_botones = QHBoxLayout()

        self.btn_descargar = QPushButton("Descargar Mapa")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_cerrar = QPushButton("Cerrar")

        # Por ahora el botón queda sin descarga real.
        # Se habilita cuando se seleccione una población urbana, pero solo muestra aviso.
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
        combo.addItem(texto_inicial, None)
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

    def poblaciones_por_id(self, id_lista):
        """
        Busca en codlista.csv todos los registros cuyo ID sea igual
        al COD generado desde el municipio seleccionado.
        """

        id_lista = normalizar_codigo(id_lista)
        poblaciones = []

        for fila in self.datos_codlista:
            if normalizar_codigo(fila.get("ID", "")) == id_lista:
                poblaciones.append({
                    "ID": fila.get("ID", ""),
                    "nombre": fila.get("nombre", ""),
                    "MCOD": fila.get("MCOD", ""),
                })

        return poblaciones

    def resetear_estado_seleccion(self):
        self.cod_actual = ""
        self.id_lista_actual = ""
        self.nombre_poblacion_actual = ""
        self.mcod_actual = ""
        self.btn_descargar.setEnabled(False)

    def cargar_departamentos(self):
        self.resetear_estado_seleccion()

        self.cmb_departamento.blockSignals(True)
        self.cmb_departamento.clear()
        self.cmb_departamento.addItem("-- Seleccione departamento --", None)

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
        self.limpiar_combo(
            self.cmb_poblacion_urbana,
            "-- Seleccione población urbana --"
        )

        self.lbl_estado.setText(
            f"Registros cargados: {len(self.datos)} municipios / "
            f"{len(self.datos_codlista)} poblaciones urbanas"
        )

    def cargar_provincias(self):
        self.resetear_estado_seleccion()

        departamento = self.cmb_departamento.currentText()

        self.cmb_provincia.blockSignals(True)
        self.cmb_provincia.clear()
        self.cmb_provincia.addItem("-- Seleccione provincia --", None)

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
            self.lbl_estado.setText(
                f"Registros cargados: {len(self.datos)} municipios / "
                f"{len(self.datos_codlista)} poblaciones urbanas"
            )

        self.cmb_provincia.blockSignals(False)

        self.limpiar_combo(
            self.cmb_municipio,
            "-- Seleccione municipio --"
        )
        self.limpiar_combo(
            self.cmb_poblacion_urbana,
            "-- Seleccione población urbana --"
        )

    def cargar_municipios(self):
        self.resetear_estado_seleccion()

        departamento = self.cmb_departamento.currentText()
        provincia = self.cmb_provincia.currentText()

        self.cmb_municipio.blockSignals(True)
        self.cmb_municipio.clear()
        self.cmb_municipio.addItem("-- Seleccione municipio --", None)

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

        self.limpiar_combo(
            self.cmb_poblacion_urbana,
            "-- Seleccione población urbana --"
        )

    def seleccionar_municipio(self):
        self.resetear_estado_seleccion()

        departamento = self.cmb_departamento.currentText()
        provincia = self.cmb_provincia.currentText()
        municipio = self.cmb_municipio.currentText()

        self.limpiar_combo(
            self.cmb_poblacion_urbana,
            "-- Seleccione población urbana --"
        )

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
                self.id_lista_actual = self.cod_actual

                poblaciones = self.poblaciones_por_id(self.id_lista_actual)
                self.cargar_poblaciones_urbanas(poblaciones)

                if poblaciones:
                    self.lbl_estado.setText(
                        f"Poblaciones urbanas encontradas: {len(poblaciones)}"
                    )
                else:
                    self.lbl_estado.setText(
                        "Poblaciones urbanas encontradas: 0"
                    )

                return

        self.lbl_estado.setText(
            "No se encontró el municipio para la selección realizada."
        )

    def cargar_poblaciones_urbanas(self, poblaciones):
        self.cmb_poblacion_urbana.blockSignals(True)
        self.cmb_poblacion_urbana.clear()
        self.cmb_poblacion_urbana.addItem(
            "-- Seleccione población urbana --",
            None
        )

        for poblacion in poblaciones:
            nombre = poblacion.get("nombre", "").strip()
            mcod = poblacion.get("MCOD", "").strip()

            # En el combo se muestra solo el nombre de la población.
            # El MCOD queda guardado internamente en currentData().
            if nombre:
                texto_item = nombre
            elif mcod:
                texto_item = f"MCOD: {mcod}"
            else:
                texto_item = "Sin nombre"

            self.cmb_poblacion_urbana.addItem(texto_item, poblacion)

        self.cmb_poblacion_urbana.blockSignals(False)

    def seleccionar_poblacion_urbana(self):
        self.nombre_poblacion_actual = ""
        self.mcod_actual = ""
        self.btn_descargar.setEnabled(False)

        datos_poblacion = self.cmb_poblacion_urbana.currentData()

        if not datos_poblacion:
            return

        self.nombre_poblacion_actual = datos_poblacion.get("nombre", "")
        self.mcod_actual = datos_poblacion.get("MCOD", "")
        self.id_lista_actual = datos_poblacion.get("ID", self.id_lista_actual)

        self.btn_descargar.setEnabled(True)

        self.lbl_estado.setText(
            f"Población urbana seleccionada: {self.nombre_poblacion_actual}"
        )

    def descargar_mapa(self):
        """
        Acción del botón Descargar Mapa.

        El MCOD viene de la aplicación/codlista.csv.
        El archivo GeoParquet NO necesita tener campo MCOD; solo debe tener COD.

        Flujo:
        1. Toma los primeros 4 caracteres del MCOD para armar el archivo.
           Ejemplo: U801206 -> U801.geoparquet
        2. Descarga ese GeoParquet desde GitHub.
        3. Filtra las geometrías donde el campo COD del GeoParquet coincide
           con el MCOD seleccionado, usando código de 7 caracteres.
        4. Calcula elementos filtrados y sumatoria total de personas.
        5. Muestra una ventana informativa y carga el resultado como capa temporal.
        """

        import tempfile
        import urllib.error
        import urllib.parse
        import urllib.request

        from qgis.core import (
            QgsFeature,
            QgsProject,
            QgsVectorLayer,
            QgsWkbTypes,
        )

        mcod = normalizar_codigo(self.mcod_actual)
        nombre_poblacion = normalizar_codigo(self.nombre_poblacion_actual)

        if not mcod:
            QMessageBox.warning(
                self,
                "Sin MCOD",
                "Seleccione una población urbana válida antes de descargar el mapa."
            )
            return

        if len(mcod) < 4:
            QMessageBox.warning(
                self,
                "MCOD inválido",
                f"El MCOD seleccionado no permite identificar el archivo GeoParquet:\n{mcod}"
            )
            return

        # Archivo GeoParquet: primeros 4 caracteres del MCOD + extensión .geoparquet
        codigo_archivo = mcod[:4]
        archivo = f"{codigo_archivo}.geoparquet"

        # Código de relación: MCOD de la aplicación en 7 caracteres.
        # En el GeoParquet se compara contra el campo COD.
        cod_relacion = mcod[:7]

        url_base = (
            "https://raw.githubusercontent.com/"
            "umayakuy/QGISCenso2024/main/data/poligonos"
        )
        url_archivo = f"{url_base}/{urllib.parse.quote(archivo)}"

        try:
            carpeta_temp = os.path.join(
                tempfile.gettempdir(),
                "QGISCenso2024_geoparquet"
            )
            os.makedirs(carpeta_temp, exist_ok=True)

            ruta_local = os.path.join(carpeta_temp, archivo)

            with urllib.request.urlopen(url_archivo, timeout=90) as respuesta:
                if respuesta.status != 200:
                    raise RuntimeError(
                        f"GitHub respondió con estado HTTP {respuesta.status}."
                    )

                with open(ruta_local, "wb") as salida:
                    salida.write(respuesta.read())

            capa_origen = QgsVectorLayer(ruta_local, archivo, "ogr")

            if not capa_origen.isValid():
                raise RuntimeError(
                    "El archivo fue descargado, pero QGIS no pudo abrirlo como GeoParquet."
                )

            def obtener_campo(capa, nombre_buscado):
                for campo in capa.fields():
                    if campo.name().strip().upper() == nombre_buscado.upper():
                        return campo.name()
                return ""

            campo_cod = obtener_campo(capa_origen, "COD")

            if not campo_cod:
                campos_disponibles = [campo.name() for campo in capa_origen.fields()]
                raise RuntimeError(
                    f"El archivo {archivo} no tiene el campo requerido COD.\n\n"
                    "Campos encontrados:\n"
                    + ", ".join(campos_disponibles)
                )

            def normalizar_nombre_campo(nombre):
                texto = str(nombre or "").strip().upper()
                reemplazos = {
                    "Á": "A", "É": "E", "Í": "I",
                    "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N",
                }

                for origen, destino in reemplazos.items():
                    texto = texto.replace(origen, destino)

                texto = re.sub(r"[^A-Z0-9]", "", texto)
                return texto

            def obtener_campo_personas(capa):
                """
                Identifica el campo de población/personas en el GeoParquet.
                Se usa solo para mostrar la sumatoria en la ventana informativa.
                """

                nombres_campos = [campo.name() for campo in capa.fields()]
                mapa_campos = {
                    normalizar_nombre_campo(nombre): nombre
                    for nombre in nombres_campos
                }

                candidatos_exactos = [
                    "PERSONAS",
                    "TOTAL_PERSONAS",
                    "TOTALPERSONAS",
                    "POBLACION",
                    "POBLACIÓN",
                    "POB_TOTAL",
                    "POBTOTAL",
                    "TOTAL_POB",
                    "TOTALPOB",
                    "POBLACION_TOTAL",
                    "POBLACIONTOTAL",
                    "HABITANTES",
                    "TOTAL_HABITANTES",
                    "TOTALHABITANTES",
                    "POB",
                    "POB2024",
                    "POB_2024",
                    "POBTOTAL2024",
                    "PERSONAS2024",
                    "HABITANTES2024",
                ]

                for candidato in candidatos_exactos:
                    clave = normalizar_nombre_campo(candidato)
                    if clave in mapa_campos:
                        return mapa_campos[clave]

                exclusiones = [
                    "COD", "ID", "NOM", "NOMBRE", "MCOD",
                    "AREA", "SUPERF", "GEOM", "SHAPE",
                    "LONG", "LAT", "X", "Y",
                ]

                for nombre in nombres_campos:
                    clave = normalizar_nombre_campo(nombre)
                    tiene_indicador = (
                        "POB" in clave
                        or "PERSON" in clave
                        or "HABIT" in clave
                    )
                    tiene_exclusion = any(exclusion in clave for exclusion in exclusiones)

                    if tiene_indicador and not tiene_exclusion:
                        return nombre

                return ""

            def convertir_personas_a_entero(valor):
                if valor is None:
                    return 0

                if isinstance(valor, int):
                    return valor

                if isinstance(valor, float):
                    return int(round(valor))

                texto = str(valor).strip()

                if not texto:
                    return 0

                # Para población, normalmente el dato debe ser entero.
                # Se eliminan separadores y texto adicional.
                texto = texto.replace(" ", "")
                texto = re.sub(r"[^0-9\-]", "", texto)

                if texto in ("", "-"):
                    return 0

                try:
                    return int(texto)
                except Exception:
                    return 0

            def formatear_entero(valor):
                return f"{int(valor):,}".replace(",", ".")

            campo_personas = obtener_campo_personas(capa_origen)
            total_personas = 0
            entidades_filtradas = []

            for entidad in capa_origen.getFeatures():
                valor_cod = normalizar_codigo(entidad[campo_cod])
                valor_cod7 = valor_cod[:7]

                # Relación correcta:
                # MCOD viene de la aplicación y COD viene del GeoParquet.
                if valor_cod == mcod or valor_cod7 == cod_relacion:
                    entidades_filtradas.append(entidad)

                    if campo_personas:
                        total_personas += convertir_personas_a_entero(
                            entidad[campo_personas]
                        )

            if not entidades_filtradas:
                QMessageBox.warning(
                    self,
                    "Sin coincidencias",
                    "Se descargó el archivo, pero no se encontraron elementos relacionados.\n\n"
                    f"Archivo: {archivo}\n"
                    f"MCOD de la aplicación: {mcod}\n"
                    f"COD esperado en GeoParquet: {cod_relacion}\n"
                    f"Campo usado en GeoParquet: {campo_cod}"
                )
                return

            tipo_wkb = QgsWkbTypes.flatType(capa_origen.wkbType())
            tipo_geometria = QgsWkbTypes.displayString(tipo_wkb)
            crs_authid = capa_origen.crs().authid()

            if crs_authid:
                uri_memoria = f"{tipo_geometria}?crs={crs_authid}"
            else:
                uri_memoria = tipo_geometria

            nombre_capa = nombre_poblacion or f"MCOD_{mcod}"
            capa_temporal = QgsVectorLayer(uri_memoria, nombre_capa, "memory")

            if not capa_temporal.isValid():
                raise RuntimeError(
                    "No se pudo crear la capa temporal de salida."
                )

            proveedor = capa_temporal.dataProvider()
            proveedor.addAttributes(capa_origen.fields())
            capa_temporal.updateFields()

            nuevas_entidades = []

            for entidad in entidades_filtradas:
                nueva_entidad = QgsFeature(capa_temporal.fields())
                nueva_entidad.setGeometry(entidad.geometry())
                nueva_entidad.setAttributes(entidad.attributes())
                nuevas_entidades.append(nueva_entidad)

            proveedor.addFeatures(nuevas_entidades)
            capa_temporal.updateExtents()

            QgsProject.instance().addMapLayer(capa_temporal)

            try:
                iface.mapCanvas().setExtent(capa_temporal.extent())
                iface.mapCanvas().refresh()
            except Exception:
                pass

            texto_total_personas = (
                formatear_entero(total_personas)
                if campo_personas
                else "No disponible"
            )

            self.lbl_estado.setText(
                f"Mapa cargado: {nombre_capa}"
            )

            try:
                iface.messageBar().pushSuccess(
                    "Mapa cargado",
                    f"{nombre_capa} | {len(nuevas_entidades)} elementos | "
                    f"Personas: {texto_total_personas}"
                )
            except Exception:
                pass

            QMessageBox.information(
                self,
                "Mapa cargado",
                "El mapa se cargó correctamente\n\n"
                f"Población urbana: {nombre_capa}\n"
                f"Manzanos cargados: {formatear_entero(len(nuevas_entidades))} polígonos\n"
                f"Población: {texto_total_personas} habitantes"
            )

            # Cerramos la ventana después de aceptar la ventana informativa.
            self.close()

        except urllib.error.HTTPError as error:
            QMessageBox.critical(
                self,
                "Archivo no encontrado en GitHub",
                "No se encontró el archivo GeoParquet en el repositorio.\n\n"
                f"Archivo buscado: {archivo}\n"
                f"URL: {url_archivo}\n"
                f"Detalle: HTTP {error.code}"
            )

        except urllib.error.URLError as error:
            QMessageBox.critical(
                self,
                "Error de conexión",
                "No se pudo conectar con GitHub para descargar el GeoParquet.\n\n"
                f"Archivo: {archivo}\n"
                f"Detalle: {error}"
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Error al cargar mapa",
                str(error)
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
        RUTA_CODLISTA,
        obtener_ventana_qgis()
    )
    CENSO2024_DLG.show()

except Exception as error:
    QMessageBox.critical(
        None,
        "Error CENSO 2024",
        str(error)
    )
