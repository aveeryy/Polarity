@echo off
:: Install python dependencies
echo [update] Installing dependencies
pip install --no-input -r requirements.txt
:: Execute the python installer
python -m polarity --windows-setup
echo [update] Done, press any key to exit.
pause > nul