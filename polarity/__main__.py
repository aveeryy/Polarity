import logging
import os
import sys
import traceback
import pretty_errors
import tqdm

from platform import system, version, python_version

from polarity.arguments import argument_parser
from polarity.config import lang
from polarity.Polarity import Polarity
from polarity.paths import LOGS
from polarity.utils import vprint, filename_datetime
from polarity.version import __version__


def main():
    urls, opts = argument_parser()
    # Launches Polarity
    Polarity(urls=urls, options=opts).start()

if __name__ == '__main__':
    if '--update-git' in sys.argv:
        from polarity.update import selfupdate
        selfupdate(mode='git')
    # Launch main function and handle 
    try:
        main()
    except KeyboardInterrupt:
        vprint(lang['main']['exit_msg'], 1)
        os._exit(0)
    except Exception:
        # Dump exception traceback to file
        exception_filename = LOGS + f'exception_{filename_datetime()}.log'
        with open(exception_filename, 'w', encoding='utf-8') as log:
            log.write('Polarity version: %s\nOS: %s %s\nPython %s\n%s' %(
                __version__,
                system(),
                version(),
                python_version(),
                traceback.format_exc()
                )
            )
        # Re-raise exception
        raise