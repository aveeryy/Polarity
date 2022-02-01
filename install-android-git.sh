# Polarity installation script for Android
# Installs from the latest commit of the branch specified
# Defaults to main branch
# Requires Termux to be installed

VERSION='2021.12.31 (git)'
REPO='https://github.com/aveeryy/Polarity.git'

echo '[-] Polarity Installer for Android' $VERSION

if [ $# -ne 1 ]; then
    # Use default branch if no branch has been specified
    BRANCH='main'
else
    BRANCH=$1
fi

echo 'Installing from branch:' $BRANCH

# Allow Termux to use internal storage
if [ ! -d ~/storage ]
then
    echo '[-] Setting up external storage'
    echo '[-] Allow Termux to access files otherwise Polarity won''t work'
    termux-setup-storage
fi
echo '[-] Updating repositories'
apt update
echo '[-] Installing/Updating dependencies'
apt install -y git python ffmpeg termux-api
# Install Polarity
echo '[-] Installing Polarity'
pip install --no-input 'git+'$REPO'@'$BRANCH
# Add alias to ~/.bashrc
# TODO: add check to avoid adding multiple aliases on update
echo "alias polarity='python -m polarity'" >> ~/.bashrc
echo '[-] Installation complete'
echo '[-] Use Polarity with ''polarity <urls> [OPTIONS]'''
# Create a new shell so alias settings apply
bash
