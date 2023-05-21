import importlib
import logging
import re
import sys
import warnings
from os import PathLike
from pathlib import Path
from typing import Optional, Protocol, Any, Union, Set, Dict

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

    
def _load_config(
    config_or_path: Union[Dict[str, Any], PathLike, str],
    template_variables: Dict[str, str],
    parent_dir: Path
) -> Dict[str, Any]:  
    
    # if its a path or string ending with .y[a]ml -> load as string
    
    if str(config_or_path).lower().endswith((".yml", ".yaml")):
        config_path = parent_dir / Path(config_or_path)
        child_parent_dir = config_path.parent
        with open(config_path) as config_file:
            config_or_path = config_file.read()
            config_or_path = _replace_template_variables(config_or_path, template_variables)
    else:
        child_parent_dir = parent_dir
    
    # if its a string version of the yaml -> parse to dict
    
    if isinstance(config_or_path, str):
        config_or_path = yaml.load(config_or_path, Loader=yaml.FullLoader) 
    
    # recursively load children
     
    if isinstance(config_or_path, dict):
        for key, value in config_or_path.items():
            config_or_path[key] = _load_config(value, template_variables, child_parent_dir)

    # return config dict
    
    return config_or_path

def load_config(
    config_or_path: Union[Dict[str, Any], PathLike, str],
    template_variables: Optional[Dict[str, str]] = None,
    parent_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Loads a config yaml from a path, a string or a dict object. Optionally replaces all
    template variables with the ones given in template_variables. If parent_dir is given,
    paths will be interpreted relative to that directory instead of the current working
    directory.
    
    Args:
        config_or_path (Union[Dict, PathLike, str]): A path to a config file, a YAML string
            describing the config or a (partially parsed) dictionary.
        template_variables (Dict[str, str]): A mapping from PLACEHOLDER_NAME to its replacement
            string. All occurences of "$PLACEHOLDER_NAME$" in the config will be replaced with
            template_variables[PLACEHOLDER_NAME]. 
        parent_dir (Union[Path, None], optional): If given, all paths will be interpreted as 
        relative to this one. Defaults to the current working directory.

    Returns:
        Dict[str, Any]: The parsed config dictionary.
    """
    
    if parent_dir is None:
        parent_dir = Path.cwd()
        
    if template_variables is None:
        template_variables = dict()

    template_variables = _TemplateVariables(template_variables)
    config = _load_config(config_or_path, template_variables, parent_dir)
    template_variables.warn_about_unused_vars()
    
    return config

def _load_plugin(
        config: Dict,
        require_validation: bool
):
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
            if require_validation:
                raise MissingConfigSchemaException(
                    f"The config of plugin '{config['module']}' is not empty, but no schema is given "
                    f"in the plugin module.")
            else:
                warnings.warn(RuntimeWarning(
                    f"No validation schema was given for plugin '{config['module']}'."
                ))
    except yamale.YamaleError as e:
        print(f"yamale threw an error while parsing config of '{plugin_module}'", sys.stderr)
        raise e

    # optionally parse config if parser is provided

    try:
        plugin_config = plugin_module.plugin_config_parser(**plugin_config)
    except AttributeError:
        pass

    # load child plugins recursively

    child_plugins = dict()
    if 'plugins' in config:
        for name, conf in config['plugins'].items():
            #child_plugin, child_config = _load_plugin(conf, template_variables, child_base_dir, require_validation)
            child_plugin, child_config = _load_plugin(conf, require_validation)
            child_plugins[name] = child_plugin
            config['plugins'][name] = child_config

    # run init method and return

    logger.info(f"Initializing plugin {config['module']}")
    instance = plugin_module.plugin_init(
        config=plugin_config,
        plugins=child_plugins
    )

    # secretly try add the raw config to the plugin
    try:
        instance.__config_yaml__ = config
    except AttributeError:
        pass

    return instance, config


def load_plugin(
        config_or_path: Union[Dict, PathLike, str],
        template_variables: Optional[Dict[str, str]] = None,
        require_validation: bool = True
):
    """
    Loads a plugin using the config at the given config_path.

    :param config_or_path: Path to the plugin config or an already parsed dict object.
    :param template_variables: A dictionary of variables to replace in the config file.
    :param require_validation: If True, the loader throws an error if no validation schema
        is given for a non-empty plugin configuration. If False, a warning is shown.
    :return: The initialized plugin.
    """
    # create a _TemplateVariables instance to track which vars were used and warn about unused ones
    
    config = load_config(config_or_path, template_variables)
    plugin, _ = _load_plugin(config, require_validation)
    return plugin
