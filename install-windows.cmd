@echo off
:: Install python dependencies
echo [-] Installing dependencies
pip install --no-input -q -q -q -r requirements.txt
:: Re-do because of tqdm cannot delete shit bug
pip install --no-input -q -q -q -r requirements.txt
:: Execute the python installer
python -m polarity --install-windows
echo [-] Done, press any key to exit.
pause > nul