#!/bin/bash

# Filtere die relevanten Zeilen aus der ruff-Ausgabe
# und formatiere sie für PyCharm-Inspections
grep -E '^([A-Z]{1,}[0-9]+) .* --> .*$' | \
awk -F ' --> ' '
{
    # Extrahiere Fehlermeldung, Datei und Zeile/Spalte
    msg = $1;
    rest = $2;
    split(rest, parts, ":");
    file = parts[1];
    line = parts[2];
    col = parts[3];

    # Entferne Leerzeichen und Annotationspfeile
    gsub(/^[ \t]+/, "", msg);
    gsub(/[ \t]+$/, "", msg);
    gsub(/[ \t]+\^+/, "", msg);

    # Gib im PyCharm-Format aus: FILE:LINE:COLUMN: MESSAGE
    print file ":" line ":" col ": " msg;
}'
