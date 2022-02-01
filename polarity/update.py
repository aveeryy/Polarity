import os
import shutil
import sys

from requests import get
from time import sleep
from typing import Tuple
from zipfile import ZipFile

from polarity.version import __version__
from polarity.utils import vprint, request_webpage, request_json, version_to_tuple

GIT_REPO = "https://github.com/aveeryy/Polarity.git"
UPDATE_ENDPOINT = "https://api.github.com/repos/aveeryy/Polarity/releases"


def check_for_updates() -> Tuple[bool, str]:
    """Check if a new stable Polarity release has been uploaded"""
    releases = request_json(UPDATE_ENDPOINT)
    latest = releases[0][0]
    return (
        version_to_tuple(__version__) < version_to_tuple(latest["tag_name"]),
        latest["tag_name"],
    )


def selfupdate(mode: str = "git", version: str = None, branch: str = "main"):
    """Update Polarity to the latest release / git commit using pip"""

    from polarity.config import lang

    if sys.argv[0].endswith(".py"):
        # Update python package
        # Try to import pip
        import pip

        if mode == "release":
            vprint(lang["update"]["downloading_release"])
            command = ["install", "--upgrade", "Polarity"]
            if version is not None:
                # If version is specified append it to the command
                # It should result in the command being
                # ['install', '--upgrade', 'Polarity=={version}']
                command[-1] += f"=={version}"
        elif mode == "git":
            vprint(lang["update"]["downloading_git"] % branch)
            command = ["install", "--upgrade", f"git+{GIT_REPO}@{branch}"]
        pip.main(command)
        os._exit(0)
    else:
        raise NotImplementedError(lang["update"]["except"]["unsupported_native"])


def language_install(language_list: list):
    """Install specified language files"""
    LANGUAGE_URL = "https://raw.githubusercontent.com/aveeryy/Polarity/main/lang/%s.toml"

    failed = 0

    from polarity.config import paths

    for lang in language_list:

        response = request_webpage(url=LANGUAGE_URL % lang)
        if response.status_code == 404:
            vprint(f'Language "{lang}" not found in server', 4, "update", "warning")
            failed += 1
            continue
        vprint(f"Installing language {lang}", "debug", "update")
        with open(paths["lang"] + f"{lang}.toml", "wb") as f:
            f.write(response.content)
        vprint(f"Language {lang} written to file", "debug", "update")
    if failed:
        vprint("Language installer finished with warnings", "warning" "update")
    else:
        vprint("All languages installed successfully", module_name="update")
    # After install reload the language strings
    from polarity.config import change_language, lang_code

    if lang_code not in ("internal", ""):
        change_language(lang_code)


def windows_setup() -> None:
    "Perform installation of dependencies on Windows systems"

    LATEST = "https://www.gyan.dev/ffmpeg/builds/release-version"
    FFMPEG = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    from polarity.config import paths

    if sys.platform != "win32":
        vprint(
            "Not running on Windows, exiting...",
            module_name="update",
            level="error",
        )
        os._exit(1)

    vprint("Downloading FFmpeg", module_name="update")
    download = get(FFMPEG, stream=True)
    total = int(download.headers["Content-Length"])
    downloaded = 0
    with open("ffmpeg.zip", "wb") as output:
        for chunk in download.iter_content(chunk_size=1024):
            output.write(chunk)
            downloaded += len(chunk)
            vprint(
                f"{downloaded} / {total} bytes downloaded   ",
                end="\r",
                module_name="update",
            )
    vprint("Extracting FFmpeg", module_name="update")
    ZipFile("ffmpeg.zip", "r").extractall(paths["tmp"])
    os.remove("ffmpeg.zip")
    # Get latest FFmpeg version string
    version = get(LATEST).text
    version_str = f"ffmpeg-{version}-essentials_build"
    # Move binaries to their respective folder
    os.rename(f'{paths["tmp"]}{version_str}/bin/ffmpeg.exe', f'{paths["bin"]}ffmpeg.exe')
    os.rename(
        f'{paths["tmp"]}{version_str}/bin/ffprobe.exe', f'{paths["bin"]}ffprobe.exe'
    )
    vprint("Cleaning up", module_name="update")
    shutil.rmtree(f'{paths["tmp"]}{version_str}')
    vprint("Setup complete", module_name="update")
    vprint("Exiting setup in 2 seconds", module_name="update")
    sleep(2)
    os._exit(0)
