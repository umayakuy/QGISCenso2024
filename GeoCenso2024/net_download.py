# -*- coding: utf-8 -*-
"""Network download helpers for GeoCenso2024.

Uses QGIS network manager instead of urllib so QGIS proxy/security settings are respected.
"""

import os

from qgis.PyQt.QtCore import QEventLoop, QTimer, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import QgsNetworkAccessManager


class DownloadError(Exception):
    """Generic network download error."""


class HttpDownloadError(DownloadError):
    """HTTP error with status code."""

    def __init__(self, code, url):
        self.code = int(code)
        self.url = url
        super().__init__("HTTP {} al consultar {}".format(self.code, url))


def _exec_event_loop(loop):
    run_loop = getattr(loop, "exec_", None)
    if run_loop is None:
        run_loop = getattr(loop, "exec")
    return run_loop()


def _http_status_attribute():
    try:
        return QNetworkRequest.Attribute.HttpStatusCodeAttribute
    except AttributeError:
        return QNetworkRequest.HttpStatusCodeAttribute


def _reply_error_code(reply):
    error = reply.error()
    try:
        return int(error)
    except TypeError:
        return int(error.value)


def download_url_to_file(url, output_path, timeout_ms=90000):
    """Download a URL to a local file using QgsNetworkAccessManager."""
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    temp_path = output_path + ".download"
    if os.path.exists(temp_path):
        os.remove(temp_path)

    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"User-Agent", b"QGIS-Censo2024")

    reply = QgsNetworkAccessManager.instance().get(request)
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)

    output = open(temp_path, "wb")

    def write_available_data():
        data = bytes(reply.readAll())
        if data:
            output.write(data)

    reply.readyRead.connect(write_available_data)
    reply.finished.connect(loop.quit)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    _exec_event_loop(loop)

    write_available_data()
    output.close()

    timed_out = not timer.isActive()
    timer.stop()

    status_value = reply.attribute(_http_status_attribute())
    status_code = int(status_value) if status_value is not None else 0
    error_code = _reply_error_code(reply)
    error_text = reply.errorString()

    if timed_out:
        try:
            reply.abort()
        except Exception:
            pass

    reply.deleteLater()

    if timed_out:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise DownloadError("Tiempo de espera agotado al descargar {}".format(url))

    if status_code >= 400:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HttpDownloadError(status_code, url)

    if error_code != 0:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise DownloadError(error_text or "Error de red al descargar {}".format(url))

    if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise DownloadError("El archivo descargado está vacío: {}".format(url))

    os.replace(temp_path, output_path)
    return output_path
