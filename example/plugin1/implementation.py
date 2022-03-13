"""
An example of a plugin defined as a class and using a dataclass to parse the plugin config.
"""

from dataclasses import dataclass


class Plugin1:
    def __init__(self, config, plugins):
        print("Plugin1")
        print("config:", config)
        print("plugin: ", plugins)


@dataclass
class Plugin1Config:
    max_iter: int
    scale: float
    output_path: str


plugin_init = Plugin1
plugin_config_schema = """
max_iter: int(min=0)
scale: num(min=0, max=1)
output_path: str()
"""
plugin_config_parser = Plugin1Config
