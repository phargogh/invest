# coding=UTF-8
"""Module for Testing the Urban Recreation model."""
import unittest
import tempfile
import shutil
import os

from osgeo import gdal
from osgeo import osr
import pygeoprocessing
import numpy


class UrbanRecreationTests(unittest.TestCase):
    """Tests for the Urban Recreation Model."""

    def setUp(self):
        """Override setUp function to create temp workspace directory."""
        # this lets us delete the workspace after its done no matter the
        # the rest result
        self.workspace_dir = tempfile.mkdtemp(suffix='\U0001f60e')  # smiley
        print('TODO BE SURE TO DELETE THIS WHEN DONE')
        try:
            self.workspace_dir = 'TEMP_TEST_DIR_URBAN'
            os.makedirs(self.workspace_dir)
        except OSError:
            pass

    def tearDown(self):
        """Override tearDown function to remove temporary directory."""
        print('TODO BE SURE TO PUT THIS RMTREE BACK')
        #shutil.rmtree(self.workspace_dir)

    def _create_urban_rec_args(self, data_dir):
        """Create urban rec args."""
        try:
            os.makedirs(data_dir)
        except OSError:
            pass
        lulc_raster_path = os.path.join(data_dir, 'lulc.tif')
        population_count_raster_path = os.path.join(data_dir, 'pop_count.tif')
        greenspace_lulc_table_path = os.path.join(
            data_dir, 'greenspace_lulc_table.csv')
        args = {
            'workspace_dir': self.workspace_dir,
            'results_suffix': 'from_test',
            'lulc_raster_path': lulc_raster_path,
            'greenspace_lulc_table_path': greenspace_lulc_table_path,
            'population_count_raster_path': '',
            'admin_unit_boundary_vector_path': '',
            'greenspace_demand_c': '',
            'search_radius': '',
        }
        # These are seattle area coords
        utm_10n_epsg = 32610
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(utm_10n_epsg)

        lulc_bounds = [546367.7, 5269863.3, 558837.0, 5277269.4]
        lulc_cell_size = 30.0
        n_col = int((lulc_bounds[2]-lulc_bounds[0])/lulc_cell_size)
        n_row = int((lulc_bounds[3]-lulc_bounds[1])/lulc_cell_size)

        lulc_array = numpy.zeros((n_row, n_col), dtype=numpy.uint8)
        lulc_array[:, n_row//2] = 1

        pygeoprocessing.numpy_array_to_raster(
            lulc_array, None, (lulc_cell_size, -lulc_cell_size),
            (lulc_bounds[0], lulc_bounds[3]),
            srs.ExportToWkt(), lulc_raster_path)

        with open(greenspace_lulc_table_path, 'w') as greenspace_file:
            greenspace_file.write('lucode, is_greenspace\n')
            greenspace_file.write('0, 1\n')
            greenspace_file.write('1, 0\n')

        population_count_raster_path = os.path.join(data_dir, 'pop_count.tif')

        pop_count_bounds = [540000.0, 5200000.3, 580000.0, 5300000.4]
        pop_count_cell_size = 300.0
        n_col = int(
            (pop_count_bounds[2]-pop_count_bounds[0])/pop_count_cell_size)
        n_row = int(
            (pop_count_bounds[3]-pop_count_bounds[1])/pop_count_cell_size)

        pop_array = numpy.zeros((n_row, n_col), dtype=numpy.int32)
        pop_array[:] = 123
        pygeoprocessing.numpy_array_to_raster(
            pop_array, None, (pop_count_cell_size, -pop_count_cell_size),
            (pop_count_bounds[0], pop_count_bounds[3]),
            srs.ExportToWkt(), population_count_raster_path)

        return args

    def test_urban_recreation(self):
        """Carbon: full model run."""
        from natcap.invest import urban_recreation
        data_dir = os.path.join(self.workspace_dir, '_data_dir')
        args = self._create_urban_rec_args(data_dir)
        urban_recreation.execute(args)
