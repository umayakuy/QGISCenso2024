# -*- coding: utf-8 -*-


def classFactory(iface):
    from .GeoCenso2024 import GeoCenso2024
    return GeoCenso2024(iface)
