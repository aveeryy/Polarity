import os
import sys
import traceback

from platform import system, version, python_version

from polarity.config import lang, paths, urls
from polarity.Polarity import Polarity
from polarity.utils import vprint, filename_datetime
from polarity.update import selfupdate
from polarity.version import __version__


def main():
    if "--update" in sys.argv:
        selfupdate(mode="release")
    elif "--update-git" in sys.argv:
        selfupdate(mode="git")
    try:
        # Launches Polarity
        Polarity(urls=urls).start()
    except KeyboardInterrupt:
        # Exit the program
        vprint(lang["main"]["exit_msg"])
        os._exit(0)
    except Exception:
        # Dump exception traceback to file if exception happens in main thread
        exception_filename = paths["log"] + f"exception_{filename_datetime()}.log"
        with open(exception_filename, "w", encoding="utf-8") as log:
            log.write(
                "Polarity version: %s\nOS: %s %s\nPython %s\n%s"
                % (
                    __version__,
                    system(),
                    version(),
                    python_version(),
                    traceback.format_exc(),
                )
            )
        # Re-raise exception
        raise


if __name__ == "__main__":
    main()
