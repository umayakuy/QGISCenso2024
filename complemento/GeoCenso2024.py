# -*- coding: utf-8 -*-
"""
GeoCenso2024
Desarrollado por UmaYakuY Consultores SRL
"""

import traceback

from qgis.PyQt.QtWidgets import QMenu, QMessageBox
from qgis.core import Qgis, QgsMessageLog

from .qt_compat import QAction, qgis_message_critical
from . import poblacion, manzanos, BDpoblacion, BDmanzanos, acercade, Amulticriterio


class GeoCenso2024:
    def __init__(self, iface):
        self.iface = iface
        self.menu = None
        self.actions = []

    def initGui(self):
        """Crea el menú jerárquico dentro de Complementos."""
        self.menu = QMenu("GeoCenso2024", self.iface.mainWindow())

        # Solo menú Complementos. No se crea toolbar ni botón.
        self.iface.pluginMenu().addMenu(self.menu)

        menu_mapas = QMenu("Mapas Censo2024", self.menu)
        self.menu.addMenu(menu_mapas)
        self._add_action(menu_mapas, "Poblaciones por municipio", poblacion.run)
        self._add_action(menu_mapas, "Manzanos por población urbana", manzanos.run)

        menu_datos = QMenu("Datos Censo2024", self.menu)
        self.menu.addMenu(menu_datos)
        self._add_action(menu_datos, "Vincular datos a poblaciones", BDpoblacion.run)
        self._add_action(menu_datos, "Vincular datos a manzanos", BDmanzanos.run)

        self.menu.addSeparator()
        accion = self._add_action(
            self.menu,
            "Análisis Multicriterio Ponderado",
            Amulticriterio.run
        )
        accion.setEnabled(False)

        self._add_action(self.menu, "Acerca de GeoCenso2024", acercade.run)

    def unload(self):
        """Elimina el menú al desactivar el complemento."""
        if self.menu is not None:
            self.iface.pluginMenu().removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None

        self.actions.clear()

    def _add_action(self, menu, text, callback):
        action = QAction(text, self.iface.mainWindow())
        action.triggered.connect(
            lambda checked=False, cb=callback, nombre=text: self.ejecutar_modulo(cb, nombre)
        )
        menu.addAction(action)
        self.actions.append(action)
        return action

    def ejecutar_modulo(self, callback, nombre_modulo):
        """Ejecuta un módulo interno del complemento sin usar código dinámico."""
        try:
            callback(self.iface)
        except Exception:
            error = traceback.format_exc()
            QgsMessageLog.logMessage(error, "GeoCenso2024", qgis_message_critical(Qgis))
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error en GeoCenso2024",
                f"Ocurrió un error al ejecutar {nombre_modulo}:\n\n{error}",
            )
