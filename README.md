# confplugs - configurable plugin modules

confplugs is a simple plugin framework for Python that uses .yaml configuration files with schema validation to provide a fully configurable app.
The goal is to provide swappable implementations, for example for machine learning pipelines.

For a usage example, check out the ``.\example`` directory.

### structure of config files

The config structure of each plugin contains 3 items
````yaml
# the name of the module of the plugin
module: "plugins.myplugin1"

# configuration for the plugin
config:
  max_items: 3
  scale: 0.8
  output_path: "my_output.txt"

# optional child plugins, with the same structure
plugins:
  ...
````

The config has to contain one main plugin that optionally loads child plugins. A complete config file could look like this:

````yaml
module: "app"

config:
  path: "example_path.txt"

plugins:

  plugin1:
    # every plugin requires a module name that points to
    # where the plugin should be loaded from
    module: "plugin1.implementation"

    config:
    # any additional items will be available to this plugin
        max_iter: 5
        scale: 0.8
        output_path: "my_output.txt"

  plugin2:
    # module path
    module: "plugin2.implementation3"

    # config is optional and not used here

````

### structure of plugin files
````python
from dataclasses import dataclass

# plugins can for example be implemented as a class
class Plugin1:
    def __init__(self, plugin_config, plugins):
        ...

# optionally a parser for the config can be provided (see below)
@dataclass
class Plugin1Config:
    max_iter: int
    scale: float
    output_path: str


# The plugin loader expects a plugin_init function that will be
# called to initialize the plugin.
# It will receive
#  - the plugin config
#  - reference to the child plugins (if available)
# and should return a reference to the plugin object
plugin_init = Plugin1

# The schema is used to validate the plugin-specific configuration
# in the config file. It uses the yamale schema language.
# If no config is needed for the plugin, this var can be omitted.
plugin_config_schema = """
max_iter: int(min=0)
scale: num(min=0, max=1)
output_path: str()
"""

# An optional config parser function can be provided to convert
# the config dictionary into some other format like a dataclass.
# The parser will be called with the config items as keyword 
# arguments.
plugin_config_parser = Plugin1Config
````

### includes from other config files

Instead of providing the complete config in one file, it is possible to reference configs of child plugins as a path, like in the nested example:

````yaml
module: "app"

config:
  path: "example_path.txt"

plugins:

  plugin1: "plugins/config_nested_plugin1.yaml"
  plugin2:
    # module path
    module: "plugin2.implementation3"

    # config is optional and not used here
````
Paths to child plugins are relative to the path of the parent config file.
