# Notizen / Annahmen (Implementierungs-Log)

## Milestone 1 — Wachstums- und Sterbe-Verhalten

- **Haushalts-Geburten** werden als *neue Haushaltsgründung* modelliert (nicht als Baby im selben Haushalt): eine probabilistische Entscheidung pro Tag, abhängig von Alter (triangular um `fertility_peak_age`), Einkommen (Elasticity) und Vermögen (Elasticity). Finanzierung ausschließlich via Transfer aus Sichtgeld/Local-Savings/Sparkasse-Einlagen (kein Geldschöpfen).
- **Haushalts-Tod**: vor Entfernen wird der Nachlass abgewickelt: Sparkassen-Kredit wird aus der Erbmasse bedient (Sichtgeld → Local-Savings → Einlagen), Restvermögen wird an einen (bevorzugt jüngeren) Erben im selben Gebiet übertragen (Fallback: Staat). Einlagen werden per Ledger-Umbuchung übertragen.
- **Altersverteilung**: Initiale Haushalte erhalten eine deterministische (seeded) Triangular-Verteilung (`initial_age_*`). Replacement-Haushalte bei Todesfällen werden mit arbeitsfähigem Alter gesampelt.
- **Unternehmens-Gründung**: pro Region probabilistisch, getrieben durch Inventar-Knappheit der Retailer und Kapitalverfügbarkeit eines (reichsten) Haushalts-Funders (Transfer-finanziert).
- **Fusion/Merger**: vereinfacht als Absorption eines distress-Unternehmens durch ein liquides Unternehmen (Transfer von Employees/Assets), 1 Ereignis/Tag max.
