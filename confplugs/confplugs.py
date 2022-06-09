import importlib
import logging
import sys
import warnings
from pathlib import Path
from typing import Protocol, Any
import re

import yamale
import yaml
from yamlinclude import YamlIncludeConstructor

logger = logging.getLogger(__name__)


class TemplateVariableMissingException(Exception):
    """Caused when a template variable is missing, but was required in the replacement process."""


def _replace_template_variables(config_string, template_variables):
    # check for variables in string
    pattern = re.compile("\$[A-Z_0-9]+\$")
    variables_found = pattern.findall(config_string)

    if len(variables_found) == 0 and template_variables is None:
        return config_string

    for var in variables_found:
        if var not in template_variables:
            raise TemplateVariableMissingException(
                f"The template variable '{var}' is present in the config file, but no replacement "
                f"was given in the template_variables list: {template_variables}.")

    for var in template_variables:
        if var not in variables_found:
            warnings.warn(RuntimeWarning(
                f"The template variable '{var}' was given in the template_variables list, but it "
                f"is not present in the config file."))

    for name, value in template_variables.items():
        config_string = config_string.replace(name, value)

    return config_string


class PluginModule(Protocol):
    plugin_config_schema: str

    @staticmethod
    def plugin_init(config: dict, plugins: dict) -> Any:
        pass

    @staticmethod
    def plugin_config_parser(**kwargs) -> Any:
        pass


class MissingConfigSchemaException(Exception):
    """The plugin config is not empty, but no schema is given in the plugin module."""


_base_schema = yamale.make_schema(content="""
include("plugin")
---
plugin:
    module: str()
    config: any(required=False)
    plugins: map(include("plugin"), required=False)
""")


def validate_config_dict(schema, config):
    yamale.validate(schema, [(config, None)])


def _load_plugin(config: dict):
    # validate basic structure

    validate_config_dict(_base_schema, config)

    # load plugin module and validate its config

    logger.info(f"Loading plugin module {config['module']}")

    # noinspection PyTypeChecker
    plugin_module: PluginModule = importlib.import_module(config['module'])

    # try to get the plugin config from the config file
    try:
        plugin_config = config['config']
    except KeyError:
        plugin_config = dict()

    # try to get the plugin_config_schema from module and validate
    try:
        plugin_schema = yamale.make_schema(content=plugin_module.plugin_config_schema)
        validate_config_dict(plugin_schema, plugin_config)
    except AttributeError:
        # if the schema does not exist, the config has to be empty
        if len(plugin_config) > 0:
            raise MissingConfigSchemaException(
                f"The config of plugin '{config['module']}' is not empty, but no schema is given "
                f"in the plugin module.")
    except yamale.YamaleError:
        print(f"yamale threw an error while parsing config of '{plugin_module}'", sys.stderr)

    # optionally parse config if parser is provided
    try:
        plugin_config = plugin_module.plugin_config_parser(**plugin_config)
    except AttributeError:
        pass

    # load child plugins recursively
    if 'plugins' in config:
        child_plugins = {name: _load_plugin(conf) for name, conf in config['plugins'].items()}
    else:
        child_plugins = dict()

    logger.info(f"Initializing plugin {config['module']}")
    return plugin_module.plugin_init(
        config=plugin_config,
        plugins=child_plugins
    )


def load_plugin(config_path: str, template_variables: dict = None):
    """
    Loads a plugin using the config at the given config_path.

    :param config_path: Path to the plugin config.
    :return: The initialized plugin.
    """
    config_path = Path(config_path)
    YamlIncludeConstructor.add_to_loader_class(
        loader_class=yaml.FullLoader,
        base_dir=config_path.parent
    )

    with open(config_path) as config_file:
        config_string = config_file.read()
        config_string = _replace_template_variables(config_string, template_variables)
        config = yaml.load(config_string, Loader=yaml.FullLoader)

    return _load_plugin(config)
