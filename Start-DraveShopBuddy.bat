@echo off
rem === Start-DraveShopBuddy.bat - start DraveShopBuddy vanaf de broncode ===
cd /d "%~dp0"
set "PY="
for %%V in (3.13 3.12 3.11) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( echo Geen Python gevonden. Installeer Python 3.11 - 3.13. & pause & exit /b 1 )
%PY% -c "import PyQt6.QtWebEngineWidgets" >nul 2>&1
if errorlevel 1 (
  echo PyQt6 + WebEngine installeren ^(eenmalig^)...
  %PY% -m pip install PyQt6 PyQt6-WebEngine
)
start "" %PY% "%~dp0draveshopbuddy.py"
