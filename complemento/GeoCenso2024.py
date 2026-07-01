# -*- coding: utf-8 -*-
"""
GeoCenso2024
Desarrollado por UmaYakuY Consultores SRL
"""

import os
import sys
import traceback
from pathlib import Path

from qgis.PyQt.QtWidgets import QMenu, QMessageBox
from qgis.core import Qgis, QgsMessageLog

from .qt_compat import QAction, qgis_message_critical


class GeoCenso2024:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = Path(__file__).resolve().parent
        self.menu = None
        self.actions = []
        self._script_contexts = {}

    def initGui(self):
        """Crea el menú jerárquico dentro de Complementos."""
        self.menu = QMenu("GeoCenso2024", self.iface.mainWindow())

        # Solo menú Complementos. No se crea toolbar ni botón.
        self.iface.pluginMenu().addMenu(self.menu)

        menu_mapas = QMenu("Mapas Censo2024", self.menu)
        self.menu.addMenu(menu_mapas)
        self._add_action(menu_mapas, "Poblaciones por municipio", "poblacion.py")
        self._add_action(menu_mapas, "Manzanos por población urbana", "manzanos.py")

        menu_datos = QMenu("Datos Censo2024", self.menu)
        self.menu.addMenu(menu_datos)
        self._add_action(menu_datos, "Vincular datos a poblaciones", "BDpoblacion.py")
        self._add_action(menu_datos, "Vincular datos a manzanos", "BDmanzanos.py")
        #accion = self._add_action(menu_datos, "Vincular datos a manzanos", "BDmanzanos.py")
        #accion.setEnabled(False)

        self.menu.addSeparator()
        #self._add_action(self.menu, "Análisis Multicriterio Ponderado", "Amulticriterio.py")
        accion = self._add_action(
        self.menu,
        "Análisis Multicriterio Ponderado",
        "Amulticriterio.py"
        )
        accion.setEnabled(False)

        self._add_action(self.menu, "Acerca de GeoCenso2024", "acercade.py")

    def unload(self):
        """Elimina el menú al desactivar el complemento."""
        if self.menu is not None:
            self.iface.pluginMenu().removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None

        self.actions.clear()
        self._script_contexts.clear()

    def _add_action(self, menu, text, script_name):
        action = QAction(text, self.iface.mainWindow())
        action.triggered.connect(lambda checked=False, s=script_name: self.ejecutar_script(s))
        menu.addAction(action)
        self.actions.append(action)
        return action

    def ejecutar_script(self, script_name):
        """
        Ejecuta un script Python ubicado en la carpeta del complemento.
        Mantiene un contexto por script para conservar referencias a ventanas PyQt.
        """
        script_path = self.plugin_dir / script_name

        if not script_path.exists():
            QMessageBox.critical(
                self.iface.mainWindow(),
                "GeoCenso2024",
                f"No se encontró el script:\n{script_path}\n\n"
                "Verifique que el archivo esté dentro de la carpeta del complemento.",
            )
            return

        old_cwd = os.getcwd()
        plugin_dir_str = str(self.plugin_dir)
        sys_path_inserted = False
        if plugin_dir_str not in sys.path:
            sys.path.insert(0, plugin_dir_str)
            sys_path_inserted = True

        namespace = self._script_contexts.get(script_name, {})
        namespace.update({
            "__file__": str(script_path),
            "__name__": "__main__",
            "iface": self.iface,
            "plugin_dir": str(self.plugin_dir),
        })

        try:
            os.chdir(str(self.plugin_dir))
            source = script_path.read_text(encoding="utf-8")
            exec(compile(source, str(script_path), "exec"), namespace)
            self._script_contexts[script_name] = namespace

        except Exception:
            error = traceback.format_exc()
            QgsMessageLog.logMessage(error, "GeoCenso2024", qgis_message_critical(Qgis))
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error en GeoCenso2024",
                f"Ocurrió un error al ejecutar {script_name}:\n\n{error}",
            )
        finally:
            os.chdir(old_cwd)
            if sys_path_inserted:
                try:
                    sys.path.remove(plugin_dir_str)
                except ValueError:
                    pass
