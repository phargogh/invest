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


class HelloWorldProcessor(BaseProcessor):
    """Hello World Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.hello_world.HelloWorldProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):

        mimetype = 'application/json'
        name = data.get('name')

        if name is None:
            raise ProcessorExecuteError('Cannot process without a name')

        message = data.get('message', '')
        value = f'Hello {name}! {message}'.strip()

        outputs = {
            'id': 'results_url',
            'value': value
        }

        return mimetype, outputs

    def __repr__(self):
        return f'<HelloWorldProcessor> {self.name}'


class CarbonProcess:
    pass
