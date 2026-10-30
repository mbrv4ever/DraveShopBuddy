@echo off
title DraveShopBuddy - EXE bouwen
rem Copyright (C) 2026 Dravenlock (Roger & Claudio). GNU GPL v3.0.
cd /d "%~dp0"
set "APPN=DraveShopBuddy"
set "DATA=dist\%APPN%\%APPN%-data"
set "RESERVE=D:\Caches\%APPN%_data_reserve"

rem --- 1. data veiligstellen (wordt anders gewist door PyInstaller) ---
set "VOOR=0"
if exist "%DATA%" (
  for /f %%N in ('dir /s /b /a-d "%DATA%" 2^>nul ^| find /c /v ""') do set "VOOR=%%N"
  if exist "%RESERVE%" rmdir /s /q "%RESERVE%"
  robocopy "%DATA%" "%RESERVE%" /e /njh /njs /nfl /ndl >nul
  if errorlevel 8 ( echo Data veiligstellen MISLUKT - ik stop. & goto mislukt )
)
echo Data voor de bouw: %VOOR% bestanden

rem --- 2. bouwen ---
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo Nieuwe .venv maken met Python 3.13...
  py -3.13 -m venv .venv || goto mislukt
)
"%VPY%" -m pip install -q --upgrade pip
"%VPY%" -m pip install -q -r requirements.txt pyinstaller pillow || goto mislukt
"%VPY%" make_icon.py || goto mislukt
"%VPY%" -m PyInstaller --noconfirm --clean --windowed --onedir --name %APPN% --icon assets\icon.ico ^
  --add-data "assets;assets" --add-data "%APPN%-Snelgids.pdf;." ^
  --hidden-import shop_engine --hidden-import drave_doneer --hidden-import drave_update ^
  --exclude-module tkinter --exclude-module matplotlib --exclude-module PIL --exclude-module numpy ^
  draveshopbuddy.py
if errorlevel 1 goto mislukt
if not exist "dist\%APPN%\%APPN%.exe" goto mislukt
xcopy /e /i /y assets "dist\%APPN%\assets" >nul
copy /y %APPN%-Snelgids.pdf "dist\%APPN%\" >nul

rem --- 3. data terugzetten en natellen ---
if exist "%RESERVE%" (
  robocopy "%RESERVE%" "%DATA%" /e /njh /njs /nfl /ndl >nul
)
set "NA=0"
if exist "%DATA%" for /f %%N in ('dir /s /b /a-d "%DATA%" 2^>nul ^| find /c /v ""') do set "NA=%%N"
echo Data na de bouw: %NA% bestanden
if %NA% LSS %VOOR% ( echo LET OP: er missen bestanden! Reserve staat in %RESERVE% & goto mislukt )
echo.
echo KLAAR: dist\%APPN%\%APPN%.exe
exit /b 0
:mislukt
echo MISLUKT - kijk hierboven voor de fout.
exit /b 1
