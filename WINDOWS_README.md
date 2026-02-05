# Wirtschaftssimulation - Windows Setup

Willkommen bei der Windows-Version der Wirtschaftssimulation! Diese Datei enthält alle Informationen, die Sie benötigen, um das Projekt auf einem Windows-Rechner einzurichten und zu nutzen.

## 🚀 Schnellstart

1. **Installieren Sie die Voraussetzungen:**
   - [Python 3.11+](https://www.python.org/downloads/) (wählen Sie "Add Python to PATH")
   - [Git](https://git-scm.com/downloads) (für Updates)

2. **Führen Sie das Build-Skript aus:**
   - Doppelklicken Sie auf `tools\build_windows.bat`
   - Folgen Sie den Anweisungen

3. **Starten Sie die Simulation:**
   - Doppelklicken Sie auf `start_simulation.bat` (wird nach dem Build erstellt)
   - Oder führen Sie manuell aus: `venv\Scripts\python main.py`

## 📦 Was wurde für Windows vorbereitet

### Neue Tools für Windows

- **`tools\build_windows.bat`** - Erstellt die virtuelle Umgebung und installiert Abhängigkeiten
- **`tools\update_windows.bat`** - Aktualisiert das Projekt mit den neuesten Änderungen
- **`doc\windows_setup.md`** - Detaillierte Setup-Anleitung für Windows

### Plattformunabhängige Features

✅ **Konfiguration:**
- `config.yaml` und `config.py` verwenden plattformunabhängige Pfade (pathlib)
- Keine harten Unix-Pfade im Code

✅ **Abhängigkeiten:**
- Alle Python-Pakete in `requirements.txt` sind Windows-kompatibel
- Keine plattformspezifischen Python-Bibliotheken

✅ **Build-System:**
- `pyproject.toml` ist plattformunabhängig konfiguriert
- Standard-Python-Tools (setuptools, wheel) werden verwendet

## 🔄 Updates durchführen

Führen Sie einfach `tools\update_windows.bat` aus:

1. Das Skript sichert Ihre lokalen Änderungen
2. Lädt die neuesten Änderungen vom Repository
3. Aktualisiert alle Python-Abhängigkeiten
4. Fragt Sie, ob Sie Ihre Änderungen wiederherstellen möchten

## 📁 Projektstruktur

```
Wirtschaftssimulation/
├── main.py                  # Haupteinstiegspunkt
├── config.yaml              # Konfiguration (kann bearbeitet werden)
├── requirements.txt         # Python-Abhängigkeiten
├── tools/
│   ├── build_windows.bat    # Windows Build-Skript
│   ├── update_windows.bat   # Windows Update-Skript
│   └── ...                  # Andere Tools
├── doc/
│   ├── windows_setup.md     # Detaillierte Windows-Anleitung
│   └── specs.md             # Technische Spezifikationen
└── venv/                    # Virtuelle Umgebung (wird erstellt)
```

## 🎯 Nächste Schritte

1. **Erste Schritte:** Lesen Sie `doc\windows_setup.md` für detaillierte Anweisungen
2. **Konfiguration anpassen:** Bearbeiten Sie `config.yaml` für Ihre Simulationsparameter
3. **Simulation starten:** Führen Sie `venv\Scripts\python main.py` aus
4. **Updates erhalten:** Führen Sie regelmäßig `tools\update_windows.bat` aus

## 💡 Tipps für Windows-Nutzer

- **Virtuelle Umgebung:** Die `venv\`-Ordner ist plattformspezifisch - kopieren Sie ihn nicht zwischen Rechnern
- **Pfade:** Verwenden Sie immer relative Pfade oder `pathlib` in Ihrem Code
- **Git:** Installieren Sie Git mit allen Standardoptionen für beste Kompatibilität
- **Performance:** Die Simulation läuft auf Windows genauso gut wie auf Linux

## 🆘 Hilfe und Support

- **Dokumentation:** `doc\specs.md` enthält technische Details
- **Probleme:** Öffnen Sie ein Issue im GitHub-Repository
- **Fragen:** Konsultieren Sie die Hauptdokumentation oder die Community

---

**Viel Spaß mit der Wirtschaftssimulation auf Windows!** 🚀