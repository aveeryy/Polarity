from polarity.utils import get_installation_path
import tomli

with open(f"{get_installation_path()}/lang/internal.toml", "rb") as fp:
    internal_lang = tomli.load(fp)
