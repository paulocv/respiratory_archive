"""Simple utilities for handling YAML files and metadata using YAML structure.
"""

import yaml


def load_yaml(fname: str) -> dict:
    with open(fname, "r") as fp:
        return yaml.safe_load(fp)


def save_yaml(fname: str, data: dict):
    with open(fname, "w") as fp:
        yaml.safe_dump(data, fp)
