"""
A basic example app using confplugs.
"""

from confplugs import load_plugin
import logging
logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    app = load_plugin("config.yaml", template_variables={"$TEST_VAR$": "my_output.txt"})
