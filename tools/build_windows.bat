@echo off
:: Windows Build Script für Wirtschaftssimulation
:: Dieses Skript erstellt eine virtuelle Umgebung und installiert alle Abhängigkeiten

echo Wirtschaftssimulation Build-Tool
echo ===============================

:: Überprüfen, ob Python installiert ist
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Fehler: Python ist nicht installiert.
    echo Bitte installieren Sie Python 3.11 oder höher von https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Überprüfen, ob pip installiert ist
where pip >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Fehler: pip ist nicht verfügbar.
    echo Bitte stellen Sie sicher, dass Python korrekt installiert ist.
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

:: Virtuelle Umgebung erstellen
echo Erstelle virtuelle Umgebung...
python -m venv venv

:: Überprüfen, ob die virtuelle Umgebung erstellt wurde
if not exist "venv\" (
    echo Fehler: Virtuelle Umgebung konnte nicht erstellt werden.
    pause
    exit /b 1
)

:: Virtuelle Umgebung aktivieren
echo Aktiviere virtuelle Umgebung...
call venv\Scripts\activate

:: Abhängigkeiten installieren
echo Installiere Abhängigkeiten...
pip install --upgrade pip
pip install -r requirements.txt

:: Überprüfen, ob die Installation erfolgreich war
if %ERRORLEVEL% neq 0 (
    echo Fehler: Abhängigkeiten konnten nicht installiert werden.
    pause
    exit /b 1
)

echo.
echo Build abgeschlossen!
echo Sie können die Simulation jetzt mit 'venv\Scripts\python main.py' starten.
echo Oder erstellen Sie eine Verknüpfung mit dem folgenden Ziel:
echo   %CURRENT_DIR%\venv\Scripts\python.exe %CURRENT_DIR%\main.py
pause