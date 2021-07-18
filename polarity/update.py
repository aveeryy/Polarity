# Git-less selfupdater
import os
import shutil
import sys

from requests import get
from time import sleep
from zipfile import ZipFile

from polarity.paths import temp_dir, binaries_dir
from polarity.utils import vprint, humanbytes

PYTHON_GIT = 'https://github.com/Aveeryy/Polarity/archive/refs/heads/main.zip'

def selfupdate(mode='git'):
    'Self-update Polarity from the latest release'

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

def windows_install() -> None:
    'User-friendly install-finisher for Windows users'

    LATEST = 'https://www.gyan.dev/ffmpeg/builds/release-version'
    FFMPEG = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'

    TESTING_TOGGLE = True

    if sys.platform != 'win32' and not TESTING_TOGGLE:
        raise NotImplementedError('Unsupported OS')

    hb = humanbytes

    print('[-] Installing dependencies')
    os.system('pip install --no-input -q -q -q -r requirements.txt')
    print('[-] Downloading FFmpeg')
    download = get(FFMPEG, stream=True)
    total = int(download.headers["Content-Length"])
    downloaded = 0
    with open('ffmpeg.zip', 'wb') as output:
        for chunk in download.iter_content(chunk_size=1024):
            output.write(chunk)
            downloaded += len(chunk)
            print(f'[-] {hb(downloaded)} / {hb(total)}    ', end='\r')
    print('[-] Extracting FFmpeg')
    ZipFile('ffmpeg.zip', 'r').extractall(temp_dir)
    os.remove('ffmpeg.zip')
    version = get(LATEST).text
    version_str = f'ffmpeg-{version}-essentials_build'
    os.rename(f'{temp_dir}{version_str}/bin/ffmpeg.exe', f'{binaries_dir}ffmpeg.exe')
    os.rename(f'{temp_dir}{version_str}/bin/ffprobe.exe', f'{binaries_dir}ffprobe.exe')
    print('[-] Cleaning up')
    shutil.rmtree(f'{temp_dir}{version_str}')
    print('[-] Installation complete')
    print('[-] Exiting in 2 seconds')
    sleep(2)
    os._exit(0)
