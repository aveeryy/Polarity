# Git-less selfupdater
import os
import shutil
import sys

from requests import get
from time import sleep
from zipfile import ZipFile

from polarity.utils import vprint, humanbytes, request_webpage, request_json, version_to_tuple
from polarity.version import __version__ as version

PYTHON_GIT = 'https://github.com/Aveeryy/Polarity/archive/refs/heads/main.zip'
UPDATE_ENDPOINT = 'https://api.github.com/repos/Aveeryy/Polarity/releases'

latest_version_on_server = None


def check_for_updates() -> bool:
    global latest_version_on_server, version
    releases = request_json(UPDATE_ENDPOINT)
    latest = releases[0][0]
    # TODO: remove this before merging pull request
    if version == 'code-rewrite':
        # Set version number for testing
        version = '2021.11.08'
    latest_version_on_server = latest['tag_name']
    return version_to_tuple(version) < version_to_tuple(latest['tag_name'])


def selfupdate(mode: str = 'git'):
    'Self-update Polarity from the latest release'

    from polarity.config import paths
    if sys.argv[0].endswith('.py'):
        # Update python package
        # Get path where Polarity is currently installed
        installation_path = os.path.dirname(
            sys.argv[0]).removesuffix('polarity')
        vprint(f'Installing to {installation_path}')
        if mode == 'release':
            vprint('Downloading latest stable release using pip')
            # Check if pip is installed in enviroment
            try:
                import pip
            except ImportError:
                raise ImportError('Cannot continue, pip not installed')
            pip.main(['install', '--upgrade', 'Polarity'])
            os._exit()
        elif mode == 'git':
            vprint('Downloading latest git release')
            update_zip = get(PYTHON_GIT)
            with open('update.zip', 'wb') as f:
                f.write(update_zip.content)
            ZipFile('update.zip').extractall(paths["tmp"])
            # Wipe current installation directory without removing it
            vprint('Updating...')
            for item in os.listdir(installation_path):
                if os.path.isdir(f'{installation_path}/{item}'):
                    shutil.rmtree(f'{installation_path}/{item}')
                else:
                    os.remove(f'{installation_path}/{item}')
            for item in os.listdir(f'{paths["tmp"]}Polarity-main/'):
                shutil.move(f'{paths["tmp"]}Polarity-main/{item}',
                            installation_path)
            # Clean up
            os.rmdir(f'{paths["tmp"]}Polarity-main/')
            vprint('Success! Exiting in 3 seconds')
            sleep(3)
            os._exit(0)
    else:
        raise NotImplementedError('Updating native binaries is not supported ')


def language_install(language_list: list):

    LANGUAGE_URL = 'https://aveeryy.github.io/Polarity-Languages/%s.toml'

    failed = 0

    from polarity.config import paths

    for lang in language_list:

        response = request_webpage(url=LANGUAGE_URL % lang)
        if response.status_code == 404:
            vprint(f'Language "{lang}" not found in server', 4, 'update',
                   'warning')
            failed += 1
            continue
        vprint(f'Installing language {lang}', 4, 'update')
        with open(paths['lang'] + f'{lang}.toml', 'wb') as f:
            f.write(response.content)
        vprint(f'Language {lang} written to file', 4, 'update', 'debug')
    if failed:
        vprint('Language installer finished with warnings', 2, 'update',
               'warning')
    else:
        vprint('All languages installed successfully', 2, 'update')
    # After install reload the language strings
    from polarity.config import change_language, lang_code
    if lang_code not in ('internal', ''):
        change_language(lang_code)


def windows_install() -> None:
    'Perform installation of dependencies on Windows systems'

    LATEST = 'https://www.gyan.dev/ffmpeg/builds/release-version'
    FFMPEG = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'

    TESTING_TOGGLE = True

    from polarity.config import paths

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
            vprint(f'{hb(downloaded)} / {hb(total)}    ',
                   end='\r',
                   module_name='update')
    vprint('Extracting FFmpeg', module_name='update')
    ZipFile('ffmpeg.zip', 'r').extractall(paths["tmp"])
    os.remove('ffmpeg.zip')
    # Get latest FFmpeg version string
    version = get(LATEST).text
    version_str = f'ffmpeg-{version}-essentials_build'
    # Move binaries to their respective folder
    os.rename(f'{paths["tmp"]}{version_str}/bin/ffmpeg.exe',
              f'{paths["bin"]}ffmpeg.exe')
    os.rename(f'{paths["tmp"]}{version_str}/bin/ffprobe.exe',
              f'{paths["bin"]}ffprobe.exe')
    vprint('Cleaning up', module_name='update')
    shutil.rmtree(f'{paths["tmp"]}{version_str}')
    vprint('Installation complete', module_name='update')
    vprint('Exiting installer in 2 seconds', module_name='update')
    sleep(2)
    os._exit(0)
