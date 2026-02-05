@echo off
:: Windows Update Script für Wirtschaftssimulation
:: Dieses Skript aktualisiert das Projekt von einem Git-Repository

:: Konfigurationsvariablen
set REPO_URL=https://github.com/stockh0lm/economy-mas.git
set BRANCH=main

echo Wirtschaftssimulation Update-Tool
echo ===============================

:: Überprüfen, ob Git installiert ist
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Fehler: Git ist nicht installiert.
    echo Bitte installieren Sie Git von https://git-scm.com/downloads
    pause
    exit /b 1
)

:: Aktuelles Verzeichnis speichern
set CURRENT_DIR=%cd%

:: In das Projektverzeichnis wechseln (falls nicht bereits dort)
if not exist "main.py" (
    echo Fehler: Dieses Skript muss im Projektverzeichnis ausgeführt werden.
    pause
    exit /b 1
)

:: Aktuellen Stand sichern
echo Sichere aktuellen Stand...
git stash push -m "Automatische Sicherung vor Update"

:: Updates vom Repository abrufen
echo Rufe Updates ab...
git fetch origin %BRANCH%

:: Aktuellen Branch ermitteln
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD') do set CURRENT_BRANCH=%%i

:: Auf den Ziel-Branch wechseln oder aktuellen Branch aktualisieren
if "%CURRENT_BRANCH%"=="%BRANCH%" (
    echo Aktualisiere aktuellen Branch...
    git pull origin %BRANCH%
) else (
    echo Wechsle zu Branch %BRANCH%...
    git checkout %BRANCH%
    git pull origin %BRANCH%
)

:: Abhängigkeiten aktualisieren
echo Aktualisiere Python-Abhängigkeiten...
if exist "venv\" (
    echo Virtuelle Umgebung gefunden - aktualisiere Pakete...
    call venv\Scripts\activate
    pip install --upgrade -r requirements.txt
) else (
    echo Keine virtuelle Umgebung gefunden.
    echo Bitte erstellen Sie eine mit: python -m venv venv
    echo Und installieren Sie die Abhängigkeiten mit: pip install -r requirements.txt
)

:: Sicherung wiederherstellen (falls gewünscht)
echo.
echo Möchten Sie die vorherige Sicherung wiederherstellen? (J/N)
set /p RESTORE=
if /i "%RESTORE%"=="J" (
    git stash pop
    echo Sicherung wurde wiederhergestellt.
) else (
    echo Sicherung bleibt gespeichert. Sie können sie später mit 'git stash pop' wiederherstellen.
)

echo.
echo Update abgeschlossen!
echo Sie können die Simulation jetzt mit 'python main.py' starten.
pause