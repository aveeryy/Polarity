import logging
import os
import sys
import pretty_errors

from platform import system, version, python_version

from polarity.config import argument_parser
from polarity.Polarity import Polarity
from polarity.paths import logs_dir
from polarity.utils import vprint, load_language, filename_datetime
from polarity.version import __version__


def main():
    urls, opts = argument_parser()
    # Launches Polarity
    Polarity(urls=urls, options=opts).start()

if __name__ == '__main__':
    lang = load_language()
    if '--update-git' in sys.argv:
        from polarity.update import selfupdate
        selfupdate(mode='git')
    # Launch main function and handle 
    try:
        main()
    except KeyboardInterrupt:
        vprint(lang['main']['exit_msg'], 1)
        os._exit(0)
    except Exception as e:
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        exception_filename = logs_dir + f'exception_{filename_datetime()}.log'
        with open(exception_filename, 'w', encoding='utf-8') as log:
            log.write('Polarity version: %s\nOS: %s %s\nPython %s\n' %(
                __version__, system(), version(), python_version()))
        logging.basicConfig(filename=exception_filename, level=logging.ERROR)
        logging.error(e, exc_info=True)
        # Re-raise exception
        raise