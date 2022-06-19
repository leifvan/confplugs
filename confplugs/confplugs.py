import importlib
import logging
import sys
import warnings
from os import PathLike
from pathlib import Path
from typing import Protocol, Any, Union, Set, Dict
import re

import yamale
import yaml

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
        template_variables.mark_as_used(var)

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


class _TemplateVariables(dict):
    def __init__(self, d: Union[Dict[str, str], '_TemplateVariables']):
        super(_TemplateVariables, self).__init__(d)

        if isinstance(d, _TemplateVariables):
            self.used: Set[str] = d.used
        else:
            self.used: Set[str] = set()

    def mark_as_used(self, key: str) -> None:
        if key not in self:
            raise KeyError(f"Given key '{key}' does not exist in the dictionary.")
        self.used.add(key)

    def warn_about_unused_vars(self) -> None:
        for var in self:
            if var not in self.used:
                warnings.warn(RuntimeWarning(
                    f"The template variable '{var}' was given in the template_variables list, but "
                    f"it is not present in the config file."))


_base_schema = yamale.make_schema(content="""
any(include("plugin"), str())
---
plugin:
    module: str()
    config: any(required=False)
    plugins: map(any(include("plugin"), str()), required=False)
""")


def _validate_config_dict(schema, config: Dict):
    yamale.validate(schema, [(config, None)])


def _load_plugin(
        config_or_path: Union[Dict, PathLike, str],
        template_variables: _TemplateVariables
):
    # if a path is given, load yaml file there

    try:
        config_path = Path(config_or_path)  # type: ignore
        with open(config_path) as config_file:
            config_string = config_file.read()
            config_string = _replace_template_variables(config_string, template_variables)
            config: Dict = yaml.load(config_string, Loader=yaml.FullLoader)
    except TypeError:
        config: Dict = config_or_path

    # validate basic structure

    _validate_config_dict(_base_schema, config)

    # load plugin module and validate its config

    logger.info(f"Loading plugin module {config['module']}")
    plugin_module: PluginModule = importlib.import_module(config['module'])  # type: ignore

    # try to get the plugin config from the config file

    try:
        plugin_config = config['config']
    except KeyError:
        plugin_config = dict()

    # try to get the plugin_config_schema from module and validate

    try:
        plugin_schema = yamale.make_schema(content=plugin_module.plugin_config_schema)
        _validate_config_dict(plugin_schema, plugin_config)
    except AttributeError:
        # if the schema does not exist, the config has to be empty
        if len(plugin_config) > 0:
            raise MissingConfigSchemaException(
                f"The config of plugin '{config['module']}' is not empty, but no schema is given "
                f"in the plugin module.")
    except yamale.YamaleError as e:
        print(f"yamale threw an error while parsing config of '{plugin_module}'", sys.stderr)
        raise e

    # optionally parse config if parser is provided

    try:
        plugin_config = plugin_module.plugin_config_parser(**plugin_config)
    except AttributeError:
        pass

    # load child plugins recursively

    if 'plugins' in config:
        child_plugins = {name: load_plugin(conf, template_variables) for name, conf in config['plugins'].items()}
    else:
        child_plugins = dict()

    # run init method and return

    logger.info(f"Initializing plugin {config['module']}")
    return plugin_module.plugin_init(
        config=plugin_config,
        plugins=child_plugins
    )


def load_plugin(
        config_or_path: Union[Dict, PathLike, str],
        template_variables: dict = None
):
    """
    Loads a plugin using the config at the given config_path.

    :param config_or_path: Path to the plugin config or an already parsed dict object.
    :param template_variables: A dictionary of variables to replace in the config file.
    :return: The initialized plugin.
    """

    # create a _TemplateVariables instance to track which vars were used and warn about unused ones

    if template_variables is None:
        template_variables = dict()

    template_variables = _TemplateVariables(template_variables)
    plugin = _load_plugin(config_or_path, template_variables)
    template_variables.warn_about_unused_vars()
    return plugin
