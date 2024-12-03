import os
import platform
import sys

os.environ['PROJ_LIB'] = os.path.join(sys._MEIPASS, 'proj')

if platform.system() == 'Darwin':
    # This allows Qt 5.13+ to start on Big Sur.
    # See https://bugreports.qt.io/browse/QTBUG-87014
    # and https://github.com/natcap/invest/issues/384
    os.environ['QT_MAC_WANTS_LAYER'] = '1'

    # Rtree will look in this directory first for libspatialindex_c.dylib.
    # In response to issues with github mac binary builds:
    # https://github.com/natcap/invest/issues/594
    # sys._MEIPASS is the path to where the pyinstaller entrypoint bundle
    # lives.  See the pyinstaller docs for more details.
    os.environ['SPATIALINDEX_C_LIBRARY'] = sys._MEIPASS

if platform.system() == 'Windows':
    # sys._MEIPASS contains gdal DLLs. It does not otherwise end
    # up on the PATH, which means that gdal can discover
    # incompatible DLLs from some other place on the PATH, such
    # as an anaconda gdal installation.
    os.environ['PATH'] = f"{sys._MEIPASS};{os.environ['PATH']}"
