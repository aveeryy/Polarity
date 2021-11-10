import os
import sys
import traceback
import pretty_errors

from platform import system, version, python_version

from polarity.config import lang, paths, urls, processes
from polarity.Polarity import Polarity
from polarity.utils import vprint, filename_datetime
from polarity.version import __version__


def main():
    # Launches Polarity
    Polarity(urls=urls).start()


if __name__ == '__main__':
    if '--update' in sys.argv:
        from polarity.update import selfupdate
        selfupdate(mode='release')
    elif '--update-git' in sys.argv:
        from polarity.update import selfupdate
        selfupdate(mode='git')
    try:
        main()
    except KeyboardInterrupt:
        # vprint(lang['main']['exit_msg'], 1)
        try:
            vprint('safe exiting')
            for proc in processes:
                proc.terminate()
        except KeyboardInterrupt:
            vprint('unsafe exit')
            for proc in processes:
                proc.kill()
        os._exit(0)

    except Exception:
        # Dump exception traceback to file
        exception_filename = paths[
            'log'] + f'exception_{filename_datetime()}.log'
        with open(exception_filename, 'w', encoding='utf-8') as log:
            log.write('Polarity version: %s\nOS: %s %s\nPython %s\n%s' %
                      (__version__, system(), version(), python_version(),
                       traceback.format_exc()))
        # Re-raise exception
        raise
