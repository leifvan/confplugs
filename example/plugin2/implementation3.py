"""
An example for a simple plugin that uses an init function directly.
"""


def plugin_init(config, plugins):
    # no need to use classes
    print("Plugin2 - impl 3")
    print("config:", config)
    print("plugin: ", plugins)

    # note that this function should return some kind of handle to the plugin.
