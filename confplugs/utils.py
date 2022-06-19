import re
from os import PathLike
from pathlib import Path

from typing import Union, List


def get_template_variables(config_path: Union[PathLike, str]) -> List[str]:
    """
    Retrieves all template variable names from the config file at the given path. To find additional
    names in includes config files, it recursively looks into any existing .yaml or .yml path
    referenced in the config file.

    :param config_path: Path to the config file to analyze.
    :return: A sorted list of all variable names found.
    """

    config_path = Path(config_path)
    paths_to_check = [config_path.name]
    base_path = Path(config_path).parent
    template_vars = []

    while len(paths_to_check) > 0:
        path = Path(paths_to_check.pop())

        try:
            with open(base_path / path) as config_file:
                config_string = config_file.read() + "\n"

                # look for template variables
                pattern = re.compile("\$[A-Z_0-9]+\$")
                variables_found = pattern.findall(config_string)
                template_vars.extend(v.replace("$", "") for v in variables_found)

                # look for additional files to analyze
                pattern = re.compile(r"[^\s]+[^\/\n\\.\s]+\.ya?ml\n")
                paths_found = pattern.findall(config_string)
                paths_to_check.extend(p.strip() for p in paths_found)
        except FileNotFoundError:
            pass

    return sorted(set(template_vars))
