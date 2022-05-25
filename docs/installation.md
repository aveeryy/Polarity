# Windows <img src=https://aveeryy.github.io/icons/small/Windows.png height=40>

## Python install

### Installing Python
* **Windows 7**

Download **Python 3.8.10**: [32 bits](https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe) or [64 bits](https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe) or [the latest Python 3.8 release](https://www.python.org/downloads/windows/)

* **Windows 8 and later**

Download the **latest version** of Python: https://www.python.org/downloads/windows/

### Downloading and installing Polarity

#### Using pip (Recommended)
- Open a `cmd` or `powershell` window and type `pip install --user --upgrade Polarity`
- Install ffmpeg using `python -m polarity --windows-setup`

#### Using GitHub

* Download the latest Python release [here](github.com/aveeryy/polarity/releases/latest) or the latest git commit [here](https://github.com/Aveeryy/Polarity/archive/refs/heads/main.zip)

> This step is simplified for inexperienced users

* Unzip it and execute `setup-windows.cmd` inside the `scripts` directory to install ffmpeg and required dependencies

# Linux <img src=https://aveeryy.github.io/icons/small/Linux.png height=40>

* Using your distribution package manager install Python 3.7 or higher and ffmpeg

### Debian and Debian-based (APT)
    sudo apt update && apt upgrade
    sudo apt install python3 python3-pip ffmpeg

### Arch and Arch-based (pacman/yay)
    sudo pacman -Syu python ffmpeg
    yay -Syu python ffmpeg

#### Installing Polarity with pip

    pip install --upgrade Polarity

    
# Android <img src=https://aveeryy.github.io/icons/small/Android.png height=40>

- Download, install and open **[Termux](https://f-droid.org/en/packages/com.termux/)** and **[Termux:API](https://f-droid.org/en/packages/com.termux.api/)**
- Continue with your preferred method

## Automatic install
- Download the latest installation script:
  - **Release:** **`curl install-android.sh -o inst.sh`**
  - **Git:** **`curl install-android-git.sh -o inst.sh`**
- Make the script executable **`chmod +x inst.sh`** and run it **`./inst.sh`**

## Manual (legacy) install [Release]
- First, setup external storage using **`termux-setup-storage`**
- Update the repos using **`apt update`**
- Install the dependencies **`apt install ffmpeg python termux-api`**
- Install Polarity using **`pip install Polarity`**
- Launch Polarity using **`polarity`**

## Manual (legacy) install [Git]
- First, setup external storage using **`termux-setup-storage`**
- Update the repos using **`apt update`**
- Install the dependencies **`apt install git ffmpeg python termux-api`**
- Clone the repository using **`git clone https://github.com/aveeryy/Polarity.git`**
- Change to the Polarity directory **`cd Polarity`**
- Install Polarity using **`pip install .`**
- Launch Polarity using **`polarity`**