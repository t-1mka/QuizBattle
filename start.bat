@echo off
chcp 65001 > nul
title BrainStorm
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LANG=C.UTF-8
set LC_ALL=C.UTF-8

echo.
echo  +----------------------------------+
echo  ^|   BrainStorm  -  Zapusk          ^|
echo  +----------------------------------+
echo.

if not exist "venv\Scripts\activate.bat" (
    echo  Sozdayu virtualnoe okruzhenie...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo.
        echo  [OSHIBKA] Python 3.10+ ne najden!
        echo  Skachajte: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat
python run.py

if %errorlevel% neq 0 (
    echo.
    echo  [OSHIBKA] Smotri oshibku vyshe.
    pause
)
