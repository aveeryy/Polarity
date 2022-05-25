import os

import tomli
import tomli_w
from polarity.config import defaults
from polarity.utils import dict_merge


def create_config_file(path: str = defaults.paths["cfg"]):
    """
    Creates a configuration file in the specified path

    :param path: Path of the config file
    """
    with open(path, "wb") as fp:
        tomli_w.dump(defaults.config, fp)


def load_config_from_file(path: str = defaults.paths["cfg"]) -> dict:

    if not os.path.exists(path):
        create_config_file(path)

    with open(path, "rb") as fp:
        loaded = tomli.load(fp)

    config = merge_new_entries(loaded)

    # if new entries have been added, save the current config to file
    if loaded != config:
        with open(path, "wb") as fp:
            tomli_w.dump(config, fp)

    return config


def merge_new_entries(config: dict) -> dict:
    return dict_merge(config, defaults.config)
