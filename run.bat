@echo off
call .venv\Scripts\activate
python -m analyzer --config config.yaml %*
pause
