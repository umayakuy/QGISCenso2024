GeoCenso2024 - Complemento QGIS actualizado

Actualización aplicada:
1. Se mantiene la estructura raíz GeoCenso2024 requerida por QGIS.
2. Se conserva el menú únicamente en Complementos > GeoCenso2024.
3. Se agregó compatibilidad Qt5/Qt6 para funcionar en QGIS 3.x y QGIS 4.x.
4. Se corrigió la importación de QAction para Qt6.
5. Se centralizaron constantes Qt en qt_compat.py para evitar errores con enums de PyQt6.
6. Se actualizó metadata.txt con qgisMaximumVersion=4.99 y versión 1.2.
7. Se mantienen los módulos del menú:
   - poblacion.py
   - urbano.py
   - BDpoblacion.py
   - BDurbano.py
   - Amulticriterio.py
   - acercade.py

Instalación:
QGIS > Complementos > Administrar e instalar complementos > Instalar desde ZIP.
Seleccione GeoCenso2024_QGIS4_QT6.zip.

Estructura del menú:
GeoCenso2024
- Descarga de Mapas
  - Poblaciones por Municipio
  - Urbano por amanzanado
- Descarga de Datos
  - Poblaciones por Municipio
  - Urbano por amanzanado
- Análisis Multicriterio Ponderado
- Acerca de GeoCenso2024
