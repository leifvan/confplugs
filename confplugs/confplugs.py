import importlib
import logging
from pathlib import Path
from typing import Protocol, Any

import yamale
import yaml
from yamlinclude import YamlIncludeConstructor

logger = logging.getLogger(__name__)


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

    # optionally parse config if parser is provided
    try:
        plugin_config = plugin_module.plugin_config_parser(**plugin_config)
    except AttributeError:
        pass

    # load child plugins recursively
    try:
        child_plugins = {name: _load_plugin(conf) for name, conf in config['plugins'].items()}
    except KeyError:
        child_plugins = dict()

    logger.info(f"Initializing plugin {config['module']}")
    return plugin_module.plugin_init(
        config=plugin_config,
        plugins=child_plugins
    )


def load_plugin(config_path: str):
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
        config = yaml.load(config_file, Loader=yaml.FullLoader)

    return _load_plugin(config)
