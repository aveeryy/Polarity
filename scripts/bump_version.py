import os
from datetime import datetime

from polarity.downloader.penguin import __version__ as penguin
from polarity.utils import normalize_number, version_to_tuple
from polarity.version import __version__


def bump_version(path: str, old: str, new: str):
    with open(path, "r+") as fp:
        # read and replace the value
        c = fp.read()
        c = c.replace(old, new)
        # go back to the beggining of the file and
        # remove it's current contents
        fp.seek(0)
        fp.truncate()
        # write new version string
        fp.write(c)


def main(module: str) -> None:

    current = {
        "polarity": (__version__, "../polarity/version.py"),
        "penguin": (penguin, "../polarity/downloader/penguin.py"),
    }

    dt = datetime.now()

    os.chdir(os.path.dirname(__file__))
    current_module = version_to_tuple(current[module][0])
    new_version = f"{dt.year}.{normalize_number(dt.month)}.{normalize_number(dt.day)}"
    # check if current version is today
    if current_module[:3] == version_to_tuple(new_version):
        revision = 1
        if len(current_module) > 3:
            # already has a revision
            revision = int(current_module[3]) + 1
        new_version += f"-{revision}"
    response = input(
        f"current {module} version is {current[module][0]}, bump to {new_version}? (Y/n) "
    )
    if response in ("Y", "y", ""):
        bump_version(current[module][1], current[module][0], new_version)
        print("bumped!")
        return True
    return False


if __name__ == "__main__":
    try:
        main("polarity")
        main("penguin")
    except KeyboardInterrupt:
        print("exiting")
        os._exit(0)
