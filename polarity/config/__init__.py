import os
from copy import deepcopy
import sys

from polarity.config import defaults
from polarity.config.errors import ConfigError
from polarity.config.file import create_config_file, load_config_from_file
from polarity.lang import change_language
from polarity.utils import dict_merge, mkfile


def get_paths() -> dict:
    """Merge user's specified paths with defaults'"""
    new_paths = deepcopy(defaults.paths)
    __path_arguments = {
        "--accounts-directory": "account",
        "--binaries-directory": "bin",
        "--config-file": "cfg",
        "--download-log-file": "dl_log",
        "--log-directory": "log",
        "--temp-directory": "tmp",
    }

    # Set new paths from user arguments
    for arg, path_name in __path_arguments.items():
        if arg in sys.argv:
            _value = sys.argv[sys.argv.index(arg) + 1]
            if _value[-1] not in ("/", "\\") and "directory" in arg:
                separator = "\\" if sys.platform == "win32" else "/"
                _value = f"{_value}{separator}"
            new_paths[path_name] = _value
        if "directory" in arg:
            # Create the directory if it does not exist
            os.makedirs(new_paths[path_name], exist_ok=True)
    return new_paths


# First, load the default values
options = deepcopy(defaults.config)
# Merge the default paths with the user's
paths = get_paths()
# Add the binaries path to PATH enviroment variable
os.environ["PATH"] += f"{':' if sys.platform != 'win32' else ';'}{paths['bin']}"
# Load the configuration
if not os.path.exists(paths["cfg"]):
    create_config_file(paths["cfg"])
# Create the download log file
mkfile(paths["dl_log"], "")
# Second, merge the configuration from the file
dict_merge(options, load_config_from_file(paths["cfg"]), True, True, True)
# Load the language file, the --language argument has the highest priority
if "--language" in sys.argv:
    lang_code = sys.argv[sys.argv.index("--language") + 1]
elif options["language"] not in ("", "internal"):
    lang_code = options["language"]
else:
    lang_code = None
# Update the language
change_language(lang_code)
#
from polarity.config.arguments import parse_arguments, urls  # noqa: E402

dict_merge(options, parse_arguments(), True, True, True)
