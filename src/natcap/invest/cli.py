# coding=UTF-8
"""Single entry point for all InVEST applications."""
import argparse
import codecs
import datetime
import gettext
import importlib
import json
import logging
import multiprocessing
import pprint
import sys
import textwrap
import warnings

import natcap.invest
from natcap.invest import datastack
from natcap.invest import set_locale
from natcap.invest import spec
from natcap.invest import ui_server
from natcap.invest import utils
from natcap.invest import models
from pygeoprocessing.geoprocessing_core import GDALUseExceptions

DEFAULT_EXIT_CODE = 1
LOGGER = logging.getLogger(__name__)


def build_model_list_table(locale_code):
    """Build a table of model names, aliases and other details.

    This table is a table only in the sense that its contents are aligned
    into columns, but are not separated by a delimiter.  This table
    is intended to be printed to stdout.

    Args:
        locale_code (str): Language code to pass to gettext. The model names
            will be returned in this language.

    Returns:
        A string representation of the formatted table.
    """
    from natcap.invest import LOCALE_DIR
    translation = gettext.translation(
        'messages',
        languages=[locale_code],
        localedir=LOCALE_DIR,
        # fall back to a NullTranslation, which returns the English messages
        fallback=True)
    max_model_id_length = max(
        len(_id) for _id in models.model_id_to_spec.keys())

    # Adding 3 to max alias name length for the parentheses plus some padding.
    max_alias_name_length = max(len(', '.join(
        model_spec.aliases)) for model_spec in models.model_id_to_spec.values()) + 3
    template_string = '    {model_id} {aliases} {model_title}'
    strings = [translation.gettext('Available models:')]
    for model_id, model_spec in models.model_id_to_spec.items():

        alias_string = ', '.join(model_spec.aliases)
        if alias_string:
            alias_string = f'({alias_string})'

        strings.append(template_string.format(
            model_id=model_id.ljust(max_model_id_length),
            aliases=alias_string.ljust(max_alias_name_length),
            model_title=translation.gettext(model_spec.model_title)))
    return '\n'.join(strings) + '\n'


def build_model_list_json(locale_code):
    """Build a json object of relevant information for the CLI.

    The json object returned uses the human-readable model names for keys
    and the values are another dict containing the internal name
    of the model and the aliases recognized by the CLI.

    Args:
        locale_code (str): Language code to pass to gettext. The model names
            will be returned in this language.

    Returns:
        A string representation of the JSON object.

    """
    from natcap.invest import LOCALE_DIR
    translation = gettext.translation(
        'messages',
        languages=[locale_code],
        localedir=LOCALE_DIR,
        # fall back to a NullTranslation, which returns the English messages
        fallback=True)

    json_object = {}
    for model_id, model_spec in models.model_id_to_spec.items():
        json_object[model_id] = {
            'model_title': translation.gettext(model_spec.model_title),
            'aliases': list(model_spec.aliases)
        }

    return json.dumps(json_object)


def export_to_python(target_filepath, model_id, args_dict=None):
    """Generate a python script that executes a model.

    Args:
        target_filepath (str): path to generate the python file
        model_id (str): ID of the model to generate the script for
        args_dict (dict): If provided, prefill these arg values in the script

    Returns:
        None
    """
    script_template = textwrap.dedent("""\
    # coding=UTF-8
    # -----------------------------------------------
    # Generated by InVEST {invest_version} on {today}
    # Model: {model_title}

    import logging
    import sys

    import {pyname}
    import natcap.invest.utils

    LOGGER = logging.getLogger(__name__)
    root_logger = logging.getLogger()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt=natcap.invest.utils.LOG_FMT,
        datefmt='%m/%d/%Y %H:%M:%S ')
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    args = {model_args}

    if __name__ == '__main__':
        {pyname}.execute(args)
    """)

    if args_dict is None:
        cast_args = {
            arg_spec.id: '' for arg_spec in models.model_id_to_spec[model_id].inputs}
    else:
        cast_args = dict((str(key), value) for (key, value)
                         in args_dict.items())

    with codecs.open(target_filepath, 'w', encoding='utf-8') as py_file:
        args = pprint.pformat(cast_args, indent=4)  # 4 spaces
        # Tweak formatting from pprint:
        # * Bump parameter inline with starting { to next line
        # * add trailing comma to last item item pair
        # * add extra space to spacing before first item
        args = args.replace('{', '{\n ')
        args = args.replace('}', ',\n}')
        py_file.write(script_template.format(
            invest_version=natcap.invest.__version__,
            today=datetime.datetime.now().strftime('%c'),
            model_title=models.model_id_to_spec[model_id].model_title,
            pyname=models.model_id_to_pyname[model_id],
            model_args=args))


class SelectModelAction(argparse.Action):
    """Given a possibly-ambiguous model string, identify the model to run.

    This is a subclass of ``argparse.Action`` and is executed when the argparse
    interface detects that the user has attempted to select a model by name.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        """Given the user's input, determine which model they're referring to.

        When the user didn't provide a model name, we print the help and exit
        with a nonzero exit code.

        Identifiable model names are:

            * the model id (exactly matching the MODEL_SPEC.model_id)
            * a uniquely identifiable prefix for the model name (e.g. "d"
              matches "delineateit", but "co" matches both
              "coastal_vulnerability" and "coastal_blue_carbon").
            * a known model alias, as registered in MODEL_SPEC.aliases

        If no single model can be identified based on these rules, an error
        message is printed and the parser exits with a nonzero exit code.

        See https://docs.python.org/3.7/library/argparse.html#action-classes
        for the full documentation for argparse classes and this __call__
        method.

        Overridden from argparse.Action.__call__.
        """
        known_models = sorted(list(models.model_id_to_spec.keys()))

        matching_models = [model for model in known_models if
                           model.startswith(values)]

        exact_matches = [model for model in known_models if
                         model == values]

        if len(matching_models) == 1:  # match an identifying substring
            model_id = matching_models[0]
        elif len(exact_matches) == 1:  # match an exact model id
            model_id = exact_matches[0]
        elif values in models.model_alias_to_id:  # match an alias
            model_id = models.model_alias_to_id[values]
        elif len(matching_models) == 0:
            parser.exit(status=1, message=(
                "Error: '%s' not a known model" % values))
        else:
            parser.exit(
                status=1,
                message=(
                    "Model string '{model}' is ambiguous:\n"
                    "    {matching_models}").format(
                        model=values,
                        matching_models=' '.join(matching_models)))
        setattr(namespace, self.dest, model_id)


def main(user_args=None):
    """CLI entry point for launching InVEST runs and other useful utilities.

    This command-line interface supports two methods of launching InVEST models
    from the command-line:

        * through its GUI
        * in headless mode, without its GUI.

    Running in headless mode allows us to bypass all GUI functionality,
    so models may be run in this way without having GUI packages
    installed.
    """
    with GDALUseExceptions():
        parser = argparse.ArgumentParser(
            description=(
                'Integrated Valuation of Ecosystem Services and Tradeoffs. '
                'InVEST (Integrated Valuation of Ecosystem Services and '
                'Tradeoffs) is a family of tools for quantifying the values of '
                'natural capital in clear, credible, and practical ways. In '
                'promising a return (of societal benefits) on investments in '
                'nature, the scientific community needs to deliver knowledge and '
                'tools to quantify and forecast this return. InVEST enables '
                'decision-makers to quantify the importance of natural capital, '
                'to assess the tradeoffs associated with alternative choices, '
                'and to integrate conservation and human development.  \n\n'
                'Older versions of InVEST ran as script tools in the ArcGIS '
                'ArcToolBox environment, but have almost all been ported over to '
                'a purely open-source python environment.'),
            prog='invest'
        )
        parser.add_argument('--version', action='version',
                            version=natcap.invest.__version__)
        verbosity_group = parser.add_mutually_exclusive_group()
        verbosity_group.add_argument(
            '-v', '--verbose', dest='verbosity', default=0, action='count',
            help=('Increase verbosity.  Affects how much logging is printed to '
                  'the console and (if running in headless mode) how much is '
                  'written to the logfile.'))
        verbosity_group.add_argument(
            '--debug', dest='log_level', default=logging.ERROR,
            action='store_const', const=logging.DEBUG,
            help='Enable debug logging. Alias for -vvv')

        parser.add_argument(
            '--taskgraph-log-level', dest='taskgraph_log_level', default='ERROR',
            type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            help=('Set the logging level for Taskgraph. Affects how much logging '
                  'Taskgraph prints to the console and (if running in headless '
                  'mode) how much is written to the logfile.'))

        # list the language code and corresponding language name (in that language)
        supported_languages_string = ', '.join([
            f'{locale} ({display_name})'
            for locale, display_name in natcap.invest.LOCALE_NAME_MAP.items()])
        parser.add_argument(
            '-L', '--language', default='en',
            choices=natcap.invest.LOCALES,
            help=('Choose a language. Model specs, names, and validation messages '
                  'will be translated. Log messages are not translated. Value '
                  'should be an ISO 639-1 language code. Supported options are: '
                  f'{supported_languages_string}.'))

        subparsers = parser.add_subparsers(dest='subcommand')

        listmodels_subparser = subparsers.add_parser(
            'list', help='List the available InVEST models')
        listmodels_subparser.add_argument(
            '--json', action='store_true', help='Write output as a JSON object')

        run_subparser = subparsers.add_parser(
            'run', help='Run an InVEST model')
        # Recognize '--headless' for backwards compatibility.
        # This arg is otherwise unused.
        run_subparser.add_argument(
            '-l', '--headless', action='store_true',
            help=argparse.SUPPRESS)
        run_subparser.add_argument(
            '-d', '--datastack', default=None, nargs='?',
            help=('Run the specified model with this JSON datastack. '
                  'Required if using --headless'))
        run_subparser.add_argument(
            '-w', '--workspace', default=None, nargs='?',
            help=('The workspace in which outputs will be saved. '
                  'Required if using --headless'))
        run_subparser.add_argument(
            'model', action=SelectModelAction,  # Assert valid model name
            help=('The model to run.  Use "invest list" to list the available '
                  'models.'))

        validate_subparser = subparsers.add_parser(
            'validate', help=(
                'Validate the parameters of a datastack'))
        validate_subparser.add_argument(
            '--json', action='store_true', help='Write output as a JSON object')
        validate_subparser.add_argument(
            'datastack', help=('Path to a JSON datastack.'))

        getspec_subparser = subparsers.add_parser(
            'getspec', help=('Get the specification of a model.'))
        getspec_subparser.add_argument(
            '--json', action='store_true', help='Write output as a JSON object')
        getspec_subparser.add_argument(
            'model', action=SelectModelAction,  # Assert valid model name
            help=('The model for which the spec should be fetched.  Use "invest '
                  'list" to list the available models.'))

        serve_subparser = subparsers.add_parser(
            'serve', help=('Start the flask app on the localhost.'))
        serve_subparser.add_argument(
            '--port', type=int, default=56789,
            help='Port number for the Flask server')

        export_py_subparser = subparsers.add_parser(
            'export-py', help=('Save a python script that executes a model.'))
        export_py_subparser.add_argument(
            'model', action=SelectModelAction,  # Assert valid model name
            help=('The model that the python script will execute.  Use "invest '
                  'list" to list the available models.'))
        export_py_subparser.add_argument(
            '-f', '--filepath', default=None,
            help='Define a location for the saved .py file')

        args = parser.parse_args(user_args)
        natcap.invest.set_locale(args.language)

        root_logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt='%(asctime)s %(name)-18s %(levelname)-8s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S ')
        handler.setFormatter(formatter)

        # Set the log level based on what the user provides in the available
        # arguments.  Verbosity: the more v's the lower the logging threshold.
        # If --debug is used, the logging threshold is 10.
        # If the user goes lower than logging.DEBUG, default to logging.DEBUG.
        log_level = min(args.log_level, logging.ERROR - (args.verbosity*10))
        handler.setLevel(max(log_level, logging.DEBUG))  # don't go below DEBUG
        root_logger.addHandler(handler)
        LOGGER.info('Setting handler log level to %s', log_level)

        # Set the log level for taskgraph.
        taskgraph_log_level = logging.getLevelName(args.taskgraph_log_level.upper())
        logging.getLogger('taskgraph').setLevel(taskgraph_log_level)
        LOGGER.debug('Setting taskgraph log level to %s', taskgraph_log_level)

        # FYI: Root logger by default has a level of logging.WARNING.
        # To capture ALL logging produced in this system at runtime, use this:
        # logging.getLogger().setLevel(logging.DEBUG)
        # Also FYI: using logging.DEBUG means that the logger will defer to
        # the setting of the parent logger.
        logging.getLogger('natcap').setLevel(logging.DEBUG)

        if args.subcommand == 'list':
            if args.json:
                message = build_model_list_json(args.language)
            else:
                message = build_model_list_table(args.language)

            sys.stdout.write(message)
            parser.exit()

        if args.subcommand == 'validate':
            try:
                parsed_datastack = datastack.extract_parameter_set(args.datastack)
            except Exception as error:
                parser.exit(
                    1, "Error when parsing JSON datastack:\n    " + str(error))

            # reload validation module first so it's also in the correct language
            importlib.reload(importlib.import_module('natcap.invest.validation'))
            model_module = importlib.reload(importlib.import_module(
                name=models.model_id_to_pyname[parsed_datastack.model_id]))

            try:
                validation_result = model_module.validate(parsed_datastack.args)
            except KeyError as missing_keys_error:
                if args.json:
                    message = json.dumps(
                        {'validation_results': {
                            str(list(missing_keys_error.args)): 'Key is missing'}})
                else:
                    message = ('Datastack is missing keys:\n    ' +
                               str(missing_keys_error.args))

                # Missing keys have an exit code of 1 because that would indicate
                # probably programmer error.
                sys.stdout.write(message)
                parser.exit(1)
            except Exception as error:
                parser.exit(
                    1, ('Datastack could not be validated:\n    ' +
                        str(error)))

            # Even validation errors will have an exit code of 0
            if args.json:
                message = json.dumps({
                    'validation_results': validation_result})
            else:
                message = pprint.pformat(validation_result)

            sys.stdout.write(message)
            parser.exit(0)

        if args.subcommand == 'getspec':
            target_model = models.model_id_to_pyname[args.model]
            model_module = importlib.reload(
                importlib.import_module(name=target_model))
            model_spec = model_module.MODEL_SPEC

            message = model_spec.to_json()
            sys.stdout.write(message)
            parser.exit(0)

        if args.subcommand == 'run':
            if args.headless:
                warnings.warn(
                    '--headless (-l) is now the default (and only) behavior '
                    'for `invest run`. This flag will not be recognized '
                    'in the future.', FutureWarning, stacklevel=2)  # 2 for brevity
            if not args.datastack:
                parser.exit(1, 'Datastack required for execution.')

            try:
                parsed_datastack = datastack.extract_parameter_set(args.datastack)
            except Exception as error:
                parser.exit(
                    1, "Error when parsing JSON datastack:\n    " + str(error))

            if not args.workspace:
                if ('workspace_dir' not in parsed_datastack.args or
                        parsed_datastack.args['workspace_dir'] in ['', None]):
                    parser.exit(
                        1, ('Workspace must be defined at the command line '
                            'or in the datastack file'))
            else:
                parsed_datastack.args['workspace_dir'] = args.workspace

            target_model = models.model_id_to_pyname[args.model]
            model_module = importlib.import_module(name=target_model)
            LOGGER.info('Imported target %s from %s',
                        model_module.__name__, model_module)

            with utils.prepare_workspace(parsed_datastack.args['workspace_dir'],
                                         model_id=parsed_datastack.model_id,
                                         logging_level=log_level):
                LOGGER.log(
                    datastack.ARGS_LOG_LEVEL,
                    'Starting model with parameters: \n%s',
                    datastack.format_args_dict(
                        parsed_datastack.args,
                        parsed_datastack.model_id))

                # We're deliberately not validating here because the user
                # can just call ``invest validate <datastack>`` to validate.
                #
                # Exceptions will already be logged to the logfile but will ALSO be
                # written to stdout if this exception is uncaught.  This is by
                # design.
                model_module.execute(parsed_datastack.args)
                LOGGER.info('Generating metadata for results')
                try:
                    # If there's an exception from creating metadata
                    # I don't think we want to indicate a model failure
                    spec.generate_metadata_for_outputs(
                        model_module, parsed_datastack.args)
                except Exception as exc:
                    LOGGER.warning(
                        'Something went wrong while generating metadata', exc_info=exc)

        if args.subcommand == 'serve':
            ui_server.app.run(port=args.port)
            parser.exit(0)

        if args.subcommand == 'export-py':
            target_filepath = args.filepath
            if not args.filepath:
                target_filepath = f'{args.model}_execute.py'
            export_to_python(target_filepath, args.model)
            parser.exit()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
