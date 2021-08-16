# Git-less selfupdater
import os
import shutil
import sys

from requests import get
from time import sleep
from zipfile import ZipFile

from polarity.paths import LANGUAGES, TEMP, BINARIES
from polarity.utils import vprint, humanbytes, request_webpage

PYTHON_GIT = 'https://github.com/Aveeryy/Polarity/archive/refs/heads/main.zip'

def selfupdate(mode='git'):
    'Self-update Polarity from the latest release'

    if sys.argv[0].endswith('.py'):
        # Update python package
        installation_path = os.path.dirname(sys.argv[0]).removesuffix('polarity')
        vprint(f'Installing to {installation_path}')
        if mode == 'git':
            vprint('Downloading latest git release')
            update_zip = get(PYTHON_GIT)
            with open('update.zip', 'wb') as f:
                f.write(update_zip.content)
            ZipFile('update.zip').extractall(TEMP)
            # Wipe current installation directory without removing it
            vprint('Updating...')
            for item in os.listdir(installation_path):
                if os.path.isdir(f'{installation_path}/{item}'):
                    shutil.rmtree(f'{installation_path}/{item}')
                else:
                    os.remove(f'{installation_path}/{item}')
            for item in os.listdir(f'{TEMP}Polarity-main/'):
                shutil.move(f'{TEMP}Polarity-main/{item}', installation_path)
            # Clean up
            os.rmdir(f'{TEMP}Polarity-main/')
            vprint('Success! Exiting in 3 seconds')
            sleep(3)
            os._exit(0)
        elif mode == 'release':
            raise NotImplementedError('Updating to a release version is not yet supported')
    else:
        raise NotImplementedError('Updating native binaries is not yet supported ')
    
def download_languages(language_list: list):
    
    LANGUAGE_URL = 'https://aveeryy.github.io/Polarity-Languages/%s.toml' 
    
    failed = 0
    
    for lang in language_list:
        
        response = request_webpage(
            url=LANGUAGE_URL % lang
            )
        if response.status_code == 404:
            vprint(f'Language "{lang}" not found in server', 4, 'update', 'warning')
            failed += 1
            continue
        vprint(f'Installing language {lang}', 4, 'update')
        with open(LANGUAGES + f'{lang}.toml', 'wb') as f:
            f.write(response.content)
        vprint(f'Language {lang} written to file', 4, 'update', 'debug')
    if failed:
        vprint('Language installer finished with warnings', 2, 'update', 'warning')
    else:
        vprint('All languages installed successfully', 4, 'update')

def windows_install() -> None:
    'User-friendly install-finisher for Windows users'

    LATEST = 'https://www.gyan.dev/ffmpeg/builds/release-version'
    FFMPEG = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'

    TESTING_TOGGLE = True

    if sys.platform != 'win32' and not TESTING_TOGGLE:
        raise NotImplementedError('Unsupported OS')

    hb = humanbytes

    vprint('Downloading FFmpeg', module_name='update')
    download = get(FFMPEG, stream=True)
    total = int(download.headers["Content-Length"])
    downloaded = 0
    with open('ffmpeg.zip', 'wb') as output:
        for chunk in download.iter_content(chunk_size=1024):
            output.write(chunk)
            downloaded += len(chunk)
            vprint(f'{hb(downloaded)} / {hb(total)}    ', end='\r', module_name='update')
    vprint('Extracting FFmpeg', module_name='update')
    ZipFile('ffmpeg.zip', 'r').extractall(TEMP)
    os.remove('ffmpeg.zip')
    version = get(LATEST).text
    version_str = f'ffmpeg-{version}-essentials_build'
    os.rename(f'{TEMP}{version_str}/bin/ffmpeg.exe', f'{BINARIES}ffmpeg.exe')
    os.rename(f'{TEMP}{version_str}/bin/ffprobe.exe', f'{BINARIES}ffprobe.exe')
    vprint('Cleaning up', module_name='update')
    shutil.rmtree(f'{TEMP}{version_str}')
    vprint('Installation complete', module_name='update')
    vprint('Exiting installer in 2 seconds', module_name='update')
    sleep(2)
    os._exit(0)
