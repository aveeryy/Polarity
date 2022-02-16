@echo off
:: Change to parent directory
cd /d "%~dp0\.."
:: Install Polarity
echo [update] Installing Polarity
pip install --no-input --upgrade --user .
:: Execute the python installer
python -m polarity --windows-setup
echo [update] Done, press any key to exit.
pause > nul
