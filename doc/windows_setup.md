# Windows Setup-Anleitung für Wirtschaftssimulation

Diese Anleitung erklärt, wie Sie das Wirtschaftssimulation-Projekt auf einem Windows-Rechner einrichten und Updates durchführen.

## Voraussetzungen

Bevor Sie beginnen, stellen Sie sicher, dass folgende Software installiert ist:

1. **Python 3.11 oder höher**
   - Download: https://www.python.org/downloads/
   - Wichtig: Wählen Sie während der Installation die Option "Add Python to PATH"

2. **Git** (für Updates)
   - Download: https://git-scm.com/downloads
   - Wählen Sie während der Installation alle Standardoptionen

## Erstinstallation

### Methode 1: Mit dem Build-Skript (empfohlen)

1. Laden Sie das Projekt von GitHub herunter oder kopieren Sie es auf Ihren Rechner
2. Navigieren Sie im Datei-Explorer zum Projektverzeichnis
3. Doppelklicken Sie auf `tools\build_windows.bat`
4. Folgen Sie den Anweisungen auf dem Bildschirm

### Methode 2: Manuelle Installation

1. Öffnen Sie die Eingabeaufforderung (cmd) oder PowerShell
2. Navigieren Sie zum Projektverzeichnis:
   ```cmd
   cd Pfad\zum\Projekt
   ```
3. Erstellen Sie eine virtuelle Umgebung:
   ```cmd
   python -m venv venv
   ```
4. Aktivieren Sie die virtuelle Umgebung:
   ```cmd
   venv\Scripts\activate
   ```
5. Installieren Sie die Abhängigkeiten:
   ```cmd
   pip install -r requirements.txt
   ```

## Projekt starten

Nach der Installation können Sie die Simulation starten:

```cmd
venv\Scripts\python main.py
```

### Alternative: Desktop-Verknüpfung erstellen

1. Klicken Sie mit der rechten Maustaste auf den Desktop
2. Wählen Sie "Neu" > "Verknüpfung"
3. Geben Sie als Ziel ein:
   ```
   Pfad\zum\Projekt\venv\Scripts\python.exe Pfad\zum\Projekt\main.py
   ```
4. Geben Sie einen Namen für die Verknüpfung ein (z. B. "Wirtschaftssimulation")

## Updates durchführen

### Methode 1: Mit dem Update-Skript (empfohlen)

1. Doppelklicken Sie auf `tools\update_windows.bat`
2. Folgen Sie den Anweisungen auf dem Bildschirm
3. Das Skript:
   - Sichert Ihre lokalen Änderungen
   - Lädt die neuesten Änderungen vom Git-Repository
   - Aktualisiert die Python-Abhängigkeiten
   - Frag Sie, ob Sie die Sicherung wiederherstellen möchten

### Methode 2: Manuelles Update

1. Öffnen Sie die Eingabeaufforderung im Projektverzeichnis
2. Führen Sie folgende Befehle aus:
   ```cmd
   git stash
   git pull origin main
   venv\Scripts\activate
   pip install --upgrade -r requirements.txt
   ```

## Konfiguration

Das Projekt verwendet Konfigurationsdateien, die plattformunabhängig sind:

- `config.yaml` - Hauptkonfiguration (kann bearbeitet werden)
- `config.py` - Python-Konfiguration (nicht bearbeiten)

Sie können die Simulation mit einer benutzerdefinierten Konfiguration starten:

```cmd
venv\Scripts\python main.py --config meine_config.yaml
```

## Problembehandlung

### Häufige Probleme und Lösungen

**Problem:** Python wird nicht gefunden
- **Lösung:** Stellen Sie sicher, dass Python im PATH ist oder geben Sie den vollen Pfad an

**Problem:** Git wird nicht gefunden
- **Lösung:** Installieren Sie Git und stellen Sie sicher, dass es im PATH ist

**Problem:** Abhängigkeiten können nicht installiert werden
- **Lösung:** Versuchen Sie `pip install --upgrade pip` vor der Installation

**Problem:** Virtuelle Umgebung kann nicht erstellt werden
- **Lösung:** Stellen Sie sicher, dass Sie ausreichend Berechtigungen haben und genug Speicherplatz verfügbar ist

## Projektübertragung auf einen anderen Windows-Rechner

1. Kopieren Sie das gesamte Projektverzeichnis auf den neuen Rechner
2. Führen Sie `tools\build_windows.bat` aus, um die virtuelle Umgebung neu zu erstellen
3. Starten Sie die Simulation wie oben beschrieben

## Wichtige Hinweise

- Die virtuelle Umgebung (`venv\`) ist plattformspezifisch und sollte nicht zwischen Rechnern kopiert werden
- Konfigurationsdateien und Simulationsdaten können zwischen Rechnern kopiert werden
- Verwenden Sie Git für die Versionskontrolle und Updates

## Support

Bei weiteren Fragen oder Problemen konsultieren Sie bitte die Hauptdokumentation in `doc/specs.md` oder öffnen Sie ein Issue im GitHub-Repository.