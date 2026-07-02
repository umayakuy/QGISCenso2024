# -*- coding: utf-8 -*-
"""
Compatibilidad para QGIS 3/Qt5 y QGIS 4/Qt6.

QGIS 4 usa Qt6. En Qt6 varias clases/enums cambiaron de módulo o
pasaron a enums anidados. Este archivo centraliza esos cambios para
mantener el mismo complemento funcionando en QGIS 3 y QGIS 4.
"""

from qgis.PyQt.QtCore import Qt

# QAction está en QtWidgets con Qt5/PyQt5 y en QtGui con Qt6/PyQt6.
try:
    from qgis.PyQt.QtGui import QAction
except Exception:  # QGIS 3 / Qt5
    from qgis.PyQt.QtWidgets import QAction

# QVariant existe en Qt5. En Qt6 se debe trabajar con QMetaType.
try:
    from qgis.PyQt.QtCore import QVariant
except Exception:  # QGIS 4 / Qt6
    from qgis.PyQt.QtCore import QMetaType

    class QVariant:  # noqa: N801 - conserva el nombre usado por PyQt5
        String = QMetaType.Type.QString
        Invalid = QMetaType.Type.UnknownType


def _qt_value(legacy_name, enum_name, member_name):
    """Devuelve constantes Qt compatibles con Qt5 y Qt6."""
    value = getattr(Qt, legacy_name, None)
    if value is not None:
        return value
    return getattr(getattr(Qt, enum_name), member_name)


QT_ALIGN_CENTER = _qt_value("AlignCenter", "AlignmentFlag", "AlignCenter")
QT_ALIGN_LEFT = _qt_value("AlignLeft", "AlignmentFlag", "AlignLeft")
QT_ALIGN_VCENTER = _qt_value("AlignVCenter", "AlignmentFlag", "AlignVCenter")
QT_ALIGN_JUSTIFY = _qt_value("AlignJustify", "AlignmentFlag", "AlignJustify")
QT_KEEP_ASPECT_RATIO = _qt_value("KeepAspectRatio", "AspectRatioMode", "KeepAspectRatio")
QT_SMOOTH_TRANSFORMATION = _qt_value("SmoothTransformation", "TransformationMode", "SmoothTransformation")
QT_TEXT_SELECTABLE_BY_MOUSE = _qt_value("TextSelectableByMouse", "TextInteractionFlag", "TextSelectableByMouse")


def qgis_message_critical(Qgis):
    """Devuelve el nivel crítico del log en QGIS 3 y QGIS 4."""
    message_level = getattr(Qgis, "MessageLevel", None)
    if message_level is not None:
        return message_level.Critical
    return Qgis.Critical

def qsize_policy(QSizePolicy, policy_name):
    """Devuelve QSizePolicy compatible con Qt5 y Qt6."""
    value = getattr(QSizePolicy, policy_name, None)
    if value is not None:
        return value
    return getattr(QSizePolicy.Policy, policy_name)

