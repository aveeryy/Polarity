import os
from datetime import datetime

from polarity.utils import version_to_tuple
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


def main() -> None:
    # get today's date
    dt = datetime.now()
    # change into scripts directory
    os.chdir(os.path.dirname(__file__))
    # convert current version to a tuple
    current_version = version_to_tuple(__version__)
    new_version = f"{dt.year}.{dt.month}.{dt.day}"
    # check if current version is today
    if current_version[:3] == version_to_tuple(new_version):
        revision = 1
        if len(current_version) > 3:
            # already has a revision
            revision = int(current_version[3]) + 1
        new_version += f"-{revision}"
    response = input(
        f"current polarity version is {__version__}, bump to {new_version}? (Y/n) "
    )
    if response in ("Y", "y", ""):
        bump_version("../polarity/version.py", __version__, new_version)
        bump_version("../setup.cfg", __version__, new_version)
        print(f"bumped to {new_version}!")
        return True
    return False


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("exiting")
        os._exit(0)
