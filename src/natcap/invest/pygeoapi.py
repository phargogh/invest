import logging

from natcap.invest import carbon
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.base import ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

REWRITTEN_INPUTS = {}
for args_key, args_values in carbon.MODEL_SPEC['args'].items():
    REWRITTEN_INPUTS[args_key] = {
        'title': args_values['name'],
        'description': args_values['about'],
        'schema': {
            'type': 'string',
        },
        'minOccurs': 1 if args_values['required'] is True else 0,
        'maxOccurs': 1,
        'keywords': []
    }

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.2.0',
    'id': carbon.MODEL_SPEC['pyname'],
    'title': {
        'en': carbon.MODEL_SPEC['model_name'],
    },
    'description': {
        'en': 'The InVEST Carbon Model.',
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': [],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': REWRITTEN_INPUTS,
    'outputs': {
        'results_url': {
            'title': 'Results location',
            'description': "The URL for your results",
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json'
            }
        }
    },
    'example': {},
}


class CarbonProcessor(BaseProcessor):
    """InVEST Carbon Model Processor"""

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):
        args = {}
        for key in carbon.MODEL_SPEC['args']:
            try:
                args[key] = data[key]
            except KeyError:
                LOGGER.debug(f"{key} not provided by user")
                pass

        carbon.execute(args)

        value = args['workspace_dir']

        outputs = {
            'id': 'results_url',
            'value': value
        }

        mimetype = 'application/json'
        return mimetype, outputs

    def __repr__(self):
        return f'<CarbonProcessor> {self.name}'
