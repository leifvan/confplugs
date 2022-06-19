"""
A basic example app using confplugs.
"""

from confplugs import load_plugin
import logging
logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    app = load_plugin("configs/config_nested.yaml", template_variables={"$TEST_VAR$": "my_output.txt", "$UNUSED_VAR$": "not used"})
