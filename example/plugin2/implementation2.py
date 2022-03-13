"""
This is an unused implementation that could be loaded by changing the config file.
"""


def plugin_init(config, plugins):
    # no need to use classes
    print("Plugin2 - impl 2")
    print("config:", config)
    print("plugin: ", plugins)

    # note that this function should return some kind of handle to the plugin.
