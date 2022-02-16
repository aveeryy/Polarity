# Polarity development scripts

A collection of scripts to help with development or help inexperienced users install Polarity

## Script list

* **`bump-version.py`**: update Polarity and/or Penguin version number to today's date
* **`install-android-git.sh`** install Polarity on Android via termux (latest git commit)
* **`install-android.sh`** install Polarity on Android via termux (latest release)
* **`setup-windows.cmd`** download ffmpeg and install Polarity (requires Python)

## Differences between setup and install scripts

**`setup-*`** scripts

* Requires the source code to be downloaded
* Requires Python to be installed (does not install system dependencies)
* Installs Polarity and ffmpeg

**`install-*`** scripts

* Can be downloaded and run independently
* Installs system dependencies (like python), Polarity and ffmpeg
