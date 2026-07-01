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

TITULO_MODULO = "Análisis Multicriterio Ponderado Censal"

TEXTO_DESARROLLO_1 = "EN DESARROLLO"
TEXTO_DESARROLLO_2 = "Esta sección se encuentra en desarrollo"

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

        self.setWindowTitle("CENSO 2024 - Análisis Multicriterio Ponderado")
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

        self.lbl_desarrollo_1 = QLabel(TEXTO_DESARROLLO_1)
        self.lbl_desarrollo_1.setAlignment(QT_ALIGN_CENTER)
        self.lbl_desarrollo_1.setStyleSheet(
            "font-size: 25pt; "
            "font-weight: normal; "
        )

        self.lbl_desarrollo_2 = QLabel(TEXTO_DESARROLLO_2)
        self.lbl_desarrollo_2.setAlignment(QT_ALIGN_CENTER)
        self.lbl_desarrollo_2.setStyleSheet(
            "font-size: 18pt; "
            "font-weight: normal; "
        )

        layout_principal.addWidget(self.lbl_desarrollo_1)
        layout_principal.addWidget(self.lbl_desarrollo_2)
        layout_principal.addStretch(2)

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
