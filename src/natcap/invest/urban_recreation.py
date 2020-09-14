"""Urban Recreation Model."""
import shutil
import tempfile
import math
import logging
import os
import pickle
import time

from osgeo import gdal
from osgeo import ogr
from osgeo import osr
import pygeoprocessing
import taskgraph
import numpy
import shapely.wkb
import shapely.prepared
import rtree

from . import validation
from . import utils

LOGGER = logging.getLogger(__name__)
TARGET_NODATA = -1
_LOGGING_PERIOD = 5.0

ARGS_SPEC = {
    'model_name': 'Urban Recreation Model',
    'module': __name__,
    'userguide_html': 'urban_recreation_model.html',
    "args_with_spatial_overlap": {
        "spatial_keys": [
            "lulc_raster_path", "population_count_raster_path",
            "admin_unit_boundary_vector_path"],
        "different_projections_ok": True,
    },
    "args": {
        "workspace_dir": validation.WORKSPACE_SPEC,
        "results_suffix": validation.SUFFIX_SPEC,
        "n_workers": validation.N_WORKERS_SPEC,
        "lulc_raster_path": {
            "name": "Land Use / Land Cover Raster",
            "type": "raster",
            "required": True,
            "validation_options": {
                "projected": True,
                "projection_units": "m",
            },
            "about": (
                "A raster containing Land use and land cover codes. Only used "
                "to convert to greenspace in conjunction with the lulc table."
            )
        },
        "greenspace_lulc_table_path": {
            "name": "Greenspace Table",
            "type": "csv",
            "required": True,
            "validation_options": {
                "required_fields": ["lucode", "is_greenspace"],
            },
            "about": (
                "Table mapping codes in the landcover raster to greenspace "
                "areas.")
        },
        "population_count_raster_path": {
            "name": "Population Count Raster",
            "type": "raster",
            "required": True,
            "validation_options": {
                "projected": True,
                "projection_units": "m",
            },
            "about": (
                "A raster containing the number of people per pixel."
            )
        },
        "admin_unit_boundary_vector_path": {
            "name": "Administrative Unit Boundary Vector",
            "type": "vector",
            "required": True,
            "validation_options": {
                "required_fields": ["ws_id"],
                "projected": True,
            },
            "about": (
                "A vector delineating administrative units."
            )
        },
        "greenspace_demand_c": {
            "name": "Greenspace Demand in m^2/person.",
            "type": "number",
            "required": True,
            "validation_options": {
                "expression": "value > 0",
            },
            "about": "Per capita greenspace demand."
        },
        "search_radius": {
            "name": "Straight line search distance for greenspace (m)",
            "type": "number",
            "required": True,
            "validation_options": {
                "expression": "value > 0",
            },
            "about": (
                "Maximum distance people will travel for greenspace "
                "recreation")
        },
    }
}


def execute(args):
    """Urban Recreation Model

    Args:
        args['workspace_dir'] (str): path to target output directory.
        args['results_suffix'] (string): (optional) string to append to any
            output file names
        args['lulc_raster_path'] (str): A path to a raster containing Land use
            and land cover codes. Used to convert to greenspace mask
            conjunction with the lulc table.
        args['greenspace_lulc_table_path'] (csv): Table mapping codes in the
            landcover raster to greenspace areas.
        args['population_count_raster_path'] (str): A path to a raster
            containing the number of people per pixel.
        args['admin_unit_boundary_vector_path'] (vector): A vector delineating
            administrative units.
        args['greenspace_demand_c'] (number): Per capita greenspace demand.
        args['search_radius'] (number): Maximum distance people will travel for
            greenspace recreation.

    Returns:
        None.

    """
    LOGGER.info('Starting Urban Recreation Model')
    file_suffix = utils.make_suffix_string(args, 'results_suffix')
    intermediate_dir = os.path.join(
        args['workspace_dir'], 'intermediate')
    utils.make_directories([args['workspace_dir'], intermediate_dir])
    greenspace_lucode_map = utils.build_lookup_from_csv(
        args['greenspace_lulc_table_path'], 'lucode', to_lower=True)

