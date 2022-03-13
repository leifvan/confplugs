"""
The main plugin of the app.
"""


class AppPlugin:
    def __init__(self, config, plugins):
        print("AppPlugin")
        print("config:", config)
        print("plugin: ", plugins)


plugin_init = AppPlugin
plugin_config_schema = """
path: str()
"""
