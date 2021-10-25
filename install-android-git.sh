# Polarity installation script for Android
# Installs the latest commit from the stable (main) branch
# Requires Termux to be installed

VERSION='2021.10.25 (git)'
REPO='https://github.com/Aveeryy/Polarity.git'

echo '[-] Polarity Installer for Android' $VERSION

# Allow Termux to use internal storage
if [ ! -d ~/storage ]
then
    echo '[-] Setting up external storage'
    echo '[-] Allow Termux to access files otherwise Polarity won''t work'
    termux-setup-storage
fi
# Remove old Polarity installation
if [ -d ~/Polarity ]
then
    echo '[-] Updating Polarity installation'
    rm -rf ~/Polarity/
fi
# Update repos and install dependencies
echo '[-] Updating repositories'
apt -qqqq update
echo '[-] Installing/Updating dependencies'
apt -qqqq install -y git python ffmpeg termux-api
# Clone the repository
echo '[-] Downloading latest git release'
cd ~
git clone --quiet $REPO
cd ~/Polarity/
# Install python dependencies
echo '[-] Installing Python dependencies'
pip install --no-input -q -q -q -r requirements.txt
# Install Polarity
echo '[-] Installing Polarity'
pip install --no-input -q -q -q -e .
# Add alias to ~/.bashrc
echo "alias polarity='python -m polarity'" >> ~/.bashrc
echo '[-] Installation complete'
echo '[-] Use Polarity with ''polarity <urls> [OPTIONS]'''
# Create a new shell so settings apply
cd $OLDPWD
bash
