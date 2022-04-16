# Polarity installation script for Android
# Installs the latest release version from pip
# Requires Termux to be installed

VERSION='2022.4.16 (release)'

echo '[-] Polarity Installer for Android' $VERSION

# Allow Termux to use internal storage
if [ ! -d ~/storage ]
then
    echo '[-] Setting up external storage'
    echo '[-] Allow Termux to access files otherwise Polarity won''t work'
    termux-setup-storage
fi
# Update repos and install dependencies
echo '[-] Updating repositories'
apt update
echo '[-] Installing/Updating dependencies'
apt install -y python ffmpeg termux-api
# Install Polarity using pip
echo '[-] Installing the latest release'
pip install --no-input Polarity
echo '[-] Installation complete'
echo '[-] Use Polarity with ''polarity <urls> [OPTIONS]'''
