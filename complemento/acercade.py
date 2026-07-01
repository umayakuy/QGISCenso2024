# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtGui import QPixmap

from qt_compat import (
    QT_ALIGN_CENTER,
    QT_ALIGN_LEFT,
    QT_ALIGN_JUSTIFY,
    QT_ALIGN_VCENTER,
    QT_KEEP_ASPECT_RATIO,
    QT_SMOOTH_TRANSFORMATION,
    QT_TEXT_SELECTABLE_BY_MOUSE,
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

# Logo que aparecerá en la parte superior de la ventana.
# Guardar el archivo GEOC.jpg en C:\INE\GEOC.jpg
RUTA_LOGO = os.path.join(os.path.dirname(__file__), "GEOC.jpg")

TITULO_MODULO = "Acerca de GeoCenso2024 v1.9"

TEXTO_INFORMACION = """Esta aplicación es un complemento para QGIS desarrollado con el propósito de facilitar la consulta, visualización y análisis territorial de información del Censo de Población y Vivienda 2024 de Bolivia.

La información fue sistematizada a partir de las Fichas Censales extraídas del Geoportal del Instituto Nacional de Estadística — INE, permitiendo integrar datos censales con herramientas geoespaciales para apoyar procesos de planificación, análisis territorial y toma de decisiones.

Este complemento no constituye una herramienta oficial del INE. Toda información generada mediante la aplicación que sea destinada a uso oficial deberá ser previamente verificada, contrastada y validada con las fuentes oficiales disponibles en el portal del Censo 2024:

https://cpv2024.ine.gob.bo/index.php/principal/principales-resultados-v3/"""

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


# ==========================================================
# VENTANA PRINCIPAL
# ==========================================================

class Censo2024Dialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("CENSO 2024 - Acerca de")
        self.setMinimumWidth(620)
        self.setMinimumHeight(485)
        self.resize(620, 485)

        self.crear_interfaz()

    def crear_interfaz(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(12, 12, 12, 10)
        layout_principal.setSpacing(12)

        self.agregar_logo(layout_principal)
        self.agregar_titulo(layout_principal)
        self.agregar_mensaje_desarrollo(layout_principal)
        self.agregar_creditos(layout_principal)

    def agregar_logo(self, layout_principal):
        contenedor_logo = QFrame()
        contenedor_logo.setMinimumHeight(155)
        contenedor_logo.setStyleSheet(
            "background-color: white; "
            "border: 1px solid #d0d0d0;"
        )

        layout_logo = QVBoxLayout(contenedor_logo)
        layout_logo.setContentsMargins(6, 6, 6, 6)

        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(QT_ALIGN_CENTER)
        self.lbl_logo.setStyleSheet("border: none; background-color: white;")

        if os.path.exists(RUTA_LOGO):
            pixmap = QPixmap(RUTA_LOGO)

            if not pixmap.isNull():
                pixmap_escalado = pixmap.scaled(
                    575,
                    140,
                    QT_KEEP_ASPECT_RATIO,
                    QT_SMOOTH_TRANSFORMATION
                )
                self.lbl_logo.setPixmap(pixmap_escalado)
            else:
                self.lbl_logo.setText("No se pudo leer el logo GEOC.jpg")
        else:
            self.lbl_logo.setText("Logo no encontrado: C:\\INE\\GEOC.jpg")

        layout_logo.addWidget(self.lbl_logo)
        layout_principal.addWidget(contenedor_logo)

    def agregar_titulo(self, layout_principal):
        self.lbl_titulo = QLabel(TITULO_MODULO)
        self.lbl_titulo.setAlignment(QT_ALIGN_LEFT)
        self.lbl_titulo.setStyleSheet(
            "font-size: 21pt; "
            "font-weight: bold; "
        )

        layout_principal.addWidget(self.lbl_titulo)

    def agregar_mensaje_desarrollo(self, layout_principal):
        layout_principal.addStretch(1)

        self.lbl_informacion = QLabel(TEXTO_INFORMACION)
        self.lbl_informacion.setAlignment(QT_ALIGN_JUSTIFY | QT_ALIGN_VCENTER)
        self.lbl_informacion.setWordWrap(True)
        self.lbl_informacion.setTextInteractionFlags(QT_TEXT_SELECTABLE_BY_MOUSE)
        self.lbl_informacion.setStyleSheet(
            "font-size: 9.5pt; "
            "font-weight: normal; "
        )

        layout_principal.addWidget(self.lbl_informacion)
        layout_principal.addStretch(1)

    def agregar_creditos(self, layout_principal):
        self.lbl_creditos = QLabel(TEXTO_CREDITOS)
        self.lbl_creditos.setAlignment(QT_ALIGN_CENTER)
        self.lbl_creditos.setWordWrap(True)
        self.lbl_creditos.setStyleSheet(
            "font-size: 9pt; "
            "font-weight: bold; "
            "color: #0070a8; "
            "padding-bottom: 2px;"
        )

        layout_principal.addWidget(self.lbl_creditos)


# ==========================================================
# EJECUTAR VENTANA EN QGIS
# ==========================================================

try:
    CENSO2024_DLG.close()
except Exception:
    pass

try:
    CENSO2024_DLG = Censo2024Dialog(
        obtener_ventana_qgis()
    )
    CENSO2024_DLG.show()

except Exception as error:
    QMessageBox.critical(
        None,
        "Error CENSO 2024",
        str(error)
    )
