# Git-less selfupdater
import os
import shutil
import sys

from requests import get
from time import sleep
from zipfile import ZipFile

from polarity.paths import temp_dir
from polarity.utils import vprint

PYTHON_GIT = 'https://github.com/Aveeryy/Polarity/archive/refs/heads/main.zip'

def selfupdate(mode='git'):
    if sys.argv[0].endswith('.py'):
        # Update python package
        installation_path = os.path.dirname(sys.argv[0]).removesuffix('/polarity')
        vprint(f'Installing to {installation_path}')
        if mode == 'git':
            vprint('Downloading latest git release')
            update_zip = get(PYTHON_GIT)
            with open('update.zip', 'wb') as f:
                f.write(update_zip.content)
            ZipFile('update.zip').extractall(temp_dir)
            # Wipe current installation directory without removing it
            vprint('Updating...')
            for item in os.listdir(installation_path):
                if os.path.isdir(f'{installation_path}/{item}'):
                    shutil.rmtree(f'{installation_path}/{item}')
                else:
                    os.remove(f'{installation_path}/{item}')
            for item in os.listdir(f'{temp_dir}Polarity-main/'):
                shutil.move(f'{temp_dir}Polarity-main/{item}', installation_path)
            # Clean up
            os.rmdir(f'{temp_dir}Polarity-main/')
            vprint('Success! Exiting in 3 seconds')
            sleep(3)
            os._exit(0)
        elif mode == 'release':
            raise NotImplementedError('Updating to a release version is not yet supported')
    else:
        raise NotImplementedError('Updating native binaries is not yet supported ')