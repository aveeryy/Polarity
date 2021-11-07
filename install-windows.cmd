@echo off
:: Install python dependencies
echo [update] Installing dependencies
pip install --no-input -q -q -q -r requirements.txt
:: Re-do because of "tqdm cannot delete" bug
pip install --no-input -q -q -q -r requirements.txt
:: Execute the python installer
python -m polarity --install-windows
echo [update] Done, press any key to exit.
pause > nul