import os

import tomli
from polarity.utils import dict_merge, get_installation_path, strip_extension


with open(f"{get_installation_path()}/lang/internal.toml", "rb") as fp:
    # Load the default language
    internal_lang = tomli.load(fp)
    lang = internal_lang.copy()


def change_language(code: str):
    """
    Load a language file by it's language code

    :param code: Language code
    :return: Nothing, modifies the lang variable
    """
    if code is None:
        code = "internal"
    path = f"{get_installation_path()}/lang/{code}.toml"
    if not os.path.exists(path):
        raise Exception(f"invalid language code: {code}")
    with open(path, "rb") as fp:
        loaded_lang = tomli.load(fp)
    # Change language to internal without modifying the variable
    # Doing this to avoid more languages than the internal one
    # and the currently loaded overlapping
    dict_merge(lang, internal_lang, True, True)
    # Now merge the strings from the loaded language file
    dict_merge(lang, loaded_lang, True, True)


def get_name_and_author(code: str) -> dict:
    """
    Get the name and author of a language file

    :param code: Language code
    :return: A dict with the language name and the author
    """

    if code is None:
        raise Exception("code can't be empty")
    if ".toml" in code:
        code = strip_extension(code)
    path = f"{get_installation_path()}/lang/{code}.toml"
    if not os.path.exists(path):
        raise Exception(f"invalid language code: {code}")
    with open(path, "rb") as fp:
        loaded_lang = tomli.load(fp)
    return {"name": loaded_lang["name"], "author": loaded_lang["author"]}


installed_languages = {
    strip_extension(f.name): {"path": f.path, **get_name_and_author(f.name)}
    for f in sorted(os.scandir(f"{get_installation_path()}/lang"), key=lambda x: x.name)
    if ".toml" in f.name
}
