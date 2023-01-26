import logging

from natcap.invest import carbon

logging.basicConfig(level=logging.INFO)


ARGS = {
    'workspace_dir': 'carbon-url-workspace',
    'lulc_cur_path':
        'https://bitbucket.org/natcap/invest-sample-data/raw/cc61f5f09d5ee0d21afdb42ec1fbbc33333e690f/Carbon/lulc_current_willamette.tif',
    'carbon_pools_path':
        'https://bitbucket.org/natcap/invest-sample-data/raw/cc61f5f09d5ee0d21afdb42ec1fbbc33333e690f/Carbon/carbon_pools_willamette.csv'
}

carbon.execute(ARGS)
