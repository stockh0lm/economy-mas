## 1) Ziel, Systemgrenzen, Leitprinzipien (aus dem Text extrahiert)

### 1.1 Kernprinzip: Geldschöpfung nur an einer Stelle
* **Geldschöpfung soll ausschließlich** durch **Kontokorrentkredite an Einzelhandelskaufleute** erfolgen, damit Geldmenge ↔ Warenwertmenge gekoppelt ist.
* Dadurch schwanken **Geldmenge und Warenwertmenge** mit Ein-/Verkauf von Waren.

### 1.2 Geld entsteht & verschwindet im Warenkreislauf
* Geld entsteht „in der Zirkulationssphäre“ durch Warenkredit; es zirkuliert (auch für Dienstleistungen) **bis** es „auf die Kontokorrentkonten zurückströmt und dort verschwindet“.
* Dienstleistungen ändern die **Geldmenge nicht**, nur die Verteilung.

### 1.3 Banken als operative Emittenten + Kontrolle
* Reformierte Banken: Aufgabe ist die **Geldversorgung** durch **zinsfreie Kontokorrentkredite** an den Einzelhandel (Geldschöpfung).
* Banken kontrollieren Einzelhandel (u.a. Inventuren); Banken werden wiederum durch eine **Clearingstelle** kontrolliert, u.a. gegen Bilanzfälschungen.
* Kredite sollen **nicht einseitig kündbar** sein; Änderungen des Kreditrahmens nur abgestimmt.

### 1.4 Sparkassen: separater Kreditkreislauf aus Spargeld (keine Geldschöpfung)
* Sparen senkt Kaufkraft; Spargeld muss über Kreditvergabe wieder in Umlauf, sonst Absatz/Produktion sinken.
* Sparkassen verleihen Spargeld zur Vorfinanzierung → Sichtguthaben wird zu Spargeld und zurück (untergeordneter Kreislauf).

---

## 2) Benötigte Agenten/Institutionen (Mapping auf deine bestehenden Klassen)

Du hast schon viele Bausteine. Grobe Zuordnung:

* **household_agent.py** → Haushalte (Konsum, Arbeit, Sparen, Kontoführung)
* **company_agent.py** → Unternehmen (Produzenten/Dienstleister) *und/oder* Einzelhändler (besser: Einzelhändler als eigener Typ/Flag)
* **bank.py** → Reformbanken (Kontokorrentlinie + Kontogebühren + Inventur-Kontrolle)
* **savings_bank_agent.py** → Sparkassen (Sparannahme, Vorfinanzierungskredite aus Spargeld)
* **clearing_agent.py** → Clearingstelle (Mindestreserve/Risikoreserven, Prüfungen, Wertberichtigungen/Geldvernichtung)
* **financial_market.py** → sollte im Zielsystem stark reduziert/abgeschaltet sein (Börsenschließung wird impliziert: „Nach Schließen der Börsen…“ )
* **state_agent.py** → Staat (im Text gibt es politische/steuerliche Regeln; du wolltest volkswirtschaftliche Faktoren → Staat als Steuer- und Regelsetzer)
* **environmental_agency.py** → optional: Stoffkreislauf/Umweltsteuer wird erwähnt (Abbildung 3).

**Fehlend (empfohlen)**:
* **InventoryLedger / GoodsFlowModule** (Warenwerte, Inventuren, Wertberichtigungslogik).

**Vorhanden**:
* **RetailerAgent** (Einzelhandel) als eigener Agententyp, weil dort Geld entsteht/verschwindet.
* **StateAgent** kauft Waren vom Einzelhandel (Staatsnachfrage).

---

## 3) Zustandsvariablen & Kontenmodell (Simulation-Datenmodell)

### 3.1 Kontotypen (pro Agent)

**Für alle Agenten (Haushalt, Unternehmen):**
* sight_balance (Sichtguthaben / Giro)
* savings_balance (Sparguthaben; nur falls Sparkasse genutzt)
* payment_card_balance (falls Bargeldersatz über Guthabenkarte/Offline-Zahlungen modelliert werden soll; dazu später)

**Für Einzelhändler (zusätzlich):**
* cc_limit (Kontokorrentrahmen)
* cc_balance (typisch negativ = Inanspruchnahme)
* inventory_value (bewerteter Warenbestand)
* inventory_items (optional granular)
* ware_value_adjustment_accounts[] (Warenwertberichtigungskonten, je Artikelgruppe oder je Abschreibungsgrund)

**Für Reformbank:**
* clients[] (Einzelhändlerkonten)
* operating_costs (gedeckt über Kontogebühren statt Zinsen)
* risk_reserve (Risikoprämie in Kontogebühren; plus Rücklagenmechanik)
* clearing_reserve_deposit (Mindestreserve/Risikorücklage bei Clearingstelle)

**Für Sparkasse:**
* savings_pool (Summe Sparguthaben)
* loan_book (Vorfinanzierungskredite aus Spargeld)
* risk_reserve (für Abschreibungen)

**Für Clearingstelle:**
* bank_reserves[bank_id] (verwaltete Mindestreserven/Risikoreserven)
* reserve_bounds (prozentuale Grenzen; zu hoch = Kaufkraftstilllegung, zu niedrig = Wertberichtigung unmöglich)
* audit_schedule, audit_rules
* value_correction_rules (Wertberichtigungen = Geldvernichtung)

---

## 4) Prozesslogik (State-Update-Regeln pro Zeitschritt)

Ich beschreibe das als **deterministische Pipeline** je Simulations-Tick (mit Stochastik nur bei Entscheidungen/Schocks).

### 4.1 Warenkauf durch Einzelhändler (Geldschöpfung – primärer Emissionspunkt)

**Event**: Retailer bestellt Ware vom Produzenten/Großhandel.

**Regel A – Entstehung von Geld im Moment des Handels / der Bezahlung**
* Wenn Retailer die Rechnung bezahlt und dazu Kontokorrent nutzt, wird das „durch Geldschöpfung“ abgewickelt:
  * beim Retailer entsteht Schuld (negativer Saldo),
  * beim Empfänger entsteht Guthaben. (Analog WIR-Beschreibung im Text)
* Der Text fasst das als: „Mit dem Erscheinen der Waren … wird Geld … geschaffen und in Umlauf gebracht.“

**Algorithmisch:**
1. purchase_value = price_to_retailer * quantity
2. Check retailer.cc_balance - purchase_value >= -retailer.cc_limit
3. Wenn nein: Bestellung ablehnen oder Menge reduzieren (**offene Frage**: Priorität/Allokation)
4. Buchung:
   * retailer.cc_balance -= purchase_value (mehr negativ)
   * producer.sight_balance += purchase_value
   * **Money supply** (M1-Proxy) steigt um purchase_value (weil neues Sichtguthaben beim Produzenten entsteht)
5. retailer.inventory_value += purchase_value (oder Einstandswert)

**Kontrollregel B – Inventuren als harte Deckungsprüfung**
* Banken müssen per Inventur prüfen, ob „Warenwerte im Umfang des aktuellen Kreditvolumens … real vorhanden“ sind.
* Algorithmisch: Bank führt Inventur, vergleicht inventory_value mit abs(cc_balance); Abweichung triggert Wertberichtigung/Strafen.

> **Offene Frage (wichtig):** Wie wird Warenwert bewertet? Einstandspreis, Marktpreis, Niederstwertprinzip? Wie schnell wird veraltete Ware abgeschrieben?
>
> **Geklärt**: RetailerAgent existiert bereits im System.

---

### 4.2 Verkauf an Haushalte (Rückstrom Richtung Kontokorrent – Geld verschwindet beim Ausgleich)

**Event**: Haushalt kauft Ware im Einzelhandel.

**Textregel:**
* Geld zirkuliert, „bis das Geld durch Kauf von Waren auf die Kontokorrentkonten zurückströmt und dort verschwindet“.

**Algorithmisch:**
1. sale_value = retail_price * quantity
2. Buchung:
   * household.sight_balance -= sale_value
   * retailer.sight_balance += sale_value
3. Periodisch (oder sofort) **Netting** Retailer:
   * Retailer verwendet Überschuss-Sichtguthaben zur Reduktion des Kontokorrents:
     * repay = min(retailer.sight_balance, abs(retailer.cc_balance))
     * retailer.sight_balance -= repay
     * retailer.cc_balance += repay (weniger negativ)
     * **Money supply sinkt** um repay, weil Tilgung die zuvor geschaffenen Sichtguthaben wieder „einsaugt“ (entspricht „verschwindet“).

> **Offene Frage:** Muss Tilgung zwingend automatisch passieren (täglich), oder entscheidet Retailer? Für Stabilität würde ich „automatisch ab Schwelle“ empfehlen.
>
> **Geklärt**: StateAgent fungiert als Käufer und generiert Staatsnachfrage.

---

### 4.3 Dienstleistungen (sekundäre Kreisläufe, keine Geldmengenänderung)

**Textregel:** Dienstleistungen ändern die Geldmenge nicht, nur Verteilung.

**Algorithmisch:** normale Überweisung:
* buyer.sight_balance -= service_fee
* seller.sight_balance += service_fee
* Money supply konstant.

---

### 4.4 Kontogebühren statt Zinsen (Bankfinanzierung + Anti-Eigenkapital-Bias)

**Textregeln:**
* Banken finanzieren Betriebskosten durch **Kontogebühren**, nicht Zinsen.
* Konten „im Plus“ sollen höhere Gebühren zahlen als Konten „im Minus“, um Eigenkapitalfinanzierung zu „bestrafen“.
* Risikoprämie ist Teil der Kontogebühren und wird gleichmäßig verteilt → Anreiz, alle Kredite solide zu halten.

**Algorithmisch (pro Tick, pro Konto):**
* fee = base_fee + alpha * max(0, sight_balance) + beta * max(0, -sight_balance?) + gamma * risk_pool_share
  * wobei im Text die Richtung klar ist: **Plus teurer als Minus** (alpha > beta).
* Abbuchung: account.sight_balance -= fee; bank.income += fee
* bank zahlt Gehälter/Costs aus bank.income (optional)

**Implementierungsnotiz (API, Stand Milestone 1):**
* Bank-Emission (Geldschöpfung) erfolgt ausschließlich über:
  * `WarengeldBank.finance_goods_purchase(retailer, seller, amount, current_step)`
* Bank-Finanzierung erfolgt ausschließlich über Kontogebühren:
  * `WarengeldBank.charge_account_fees(accounts)`
* Inventurprüfung ist **diagnostisch** (keine unmittelbare Einziehung in der Bank):
  * `WarengeldBank.check_inventories(retailers, current_step=...) -> list[(retailer_id, inventory_value, cc_exposure)]`
* Wertberichtigungen reduzieren Bank-Exposure explizit:
  * `WarengeldBank.write_down_cc(retailer, amount, reason=...)`
* Entfernte Legacy-APIs: `grant_credit`, `calculate_fees`, `fee_rate` (Referenz: doc/issues.md Abschnitt 4).

> **Offene Frage:** Bemessungsgrundlage (täglich, monatlich; linear vs. progressiv). Für Simulation: monatlich und progressiv (damit „große Plus-Bestände“ stärker gedrückt werden).

---

### 4.5 Clearingstelle: Mindestreserve, Wettbewerbssanktion, Prüfungen, Wertberichtigungen

**Textregeln (sehr konkret):**
* Kopplung Geldschöpfung an Warenwerte ist Grundlage der Geldmengensteuerung.
* Banken halten Rücklagen als „Mindestreserve“ bei der Clearingstelle; bei wiederholten Problemen erhöht Clearing die Mindestreserveforderung.
* Zu hohe Rücklagen = Stilllegung von Kaufkraft → partieller Geldmangel/Absatzstockungen; daher prozentuale Grenzen.
* Bei schweren Bilanzfälschungen: Clearing erzwingt Wertberichtigungen (Geldvernichtung), ggf. Bank schließen, seriöse Konten übertragen.

**Algorithmisch (Audit-Zyklus, z.B. monatlich/vierteljährlich):**
1. Für jede Bank:
   * Prüfe Stichproben-Retailer: inventory_value vs abs(cc_balance) + Buchungen.
   * Prüfe Reservequote: bank.clearing_reserve_deposit / bank.total_cc_exposure
2. Wenn problem_score hoch:
   * Erhöhe required_reserve_ratio[bank] (Wettbewerbssanktion: Bank muss Kosten über Gebühren/Gehälter tragen).
3. Wenn Fraud detected:
   * Trigger Wertberichtigung: Geldvernichtung in beteiligten Geschäften.
   * Optional: Bank resolution (Kontoumzug seriöser Kunden)

> **Offene Frage:** Was ist die exakte „Fehlerkorrektur“ bei Bilanzfälschung? Welche Konten werden wie stark wertberichtigt? (Da hängt die Makrodynamik extrem dran.)

---

### 4.6 Wertberichtigungen über Warenwertberichtigungskonten (gezielte Geldvernichtung)

Der Text gibt dafür eine klare Buchungslogik:
* Für „unverkaufbare Waren“ werden **Warenwertberichtigungskonten** geführt; dort werden Rücklagen aus Gewinnen gespeichert.
* Beim Abschreiben unverkaufbarer Ware wird von dort Geld vernichtet: „Geldguthaben wird vom Warenwertberichtigungskonto abgezogen und verschwindet.“
* Gleichzeitig wird der Warenwert im Lager reduziert.

**Algorithmisch (bei Abschreibung / Verderb / Modewechsel):**
1. write_down = f(obsolescence, spoilage, demand_shift)
2. retailer.inventory_value -= write_down
3. retailer.ware_value_adjustment_account -= write_down
4. **Money supply sinkt** um write_down (Geldvernichtung)

> **Offene Frage:** Wie werden Rücklagen *gefüllt*? „Aus Gewinnen“ heißt: aus Überschüssen beim Retailer. Aber Gewinndefinition ist im System (Selbstkostenpreise, Wettbewerb) heikel: Was ist legitimer Gewinn vs. verbotener Profit? (Der Text argumentiert Wettbewerb begrenzt das, liefert aber keine harte Buchungsregel.)

---

### 4.7 Sichtguthaben-Abschmelzung / Schwund nur für Überschuss (Geldflusssicherung)

Im Text wird ein Mechanismus beschrieben, der **nicht generelles Schwundgeld** ist, sondern gezielt „zu große Sichtguthaben“ adressiert:
* Es gibt einen **Sichtfaktor**: Wenn Sichtguthaben über einem **Sichtfreibetrag** liegen, wird der Überschuss **abgeschmolzen** (dokumentiert als Geldvernichtung / Kaufkraftabschmelzung).
* Sichtfreibetrag orientiert sich an „durchschnittlichen monatlichen Ausgaben“, damit auch geringe Einkommen nicht „auf den Markt getrieben“ werden.
* Kernidee: „zu große Sichtguthaben“ wachsen nicht unbegrenzt; es gibt Rückkopplung über den Sichtfaktor.

**Algorithmisch (monatlich, weil Bezug auf Monatsausgaben):**
1. Für jeden Agenten:
   * avg_monthly_spend = rolling_mean(consumption, window=30d)
   * sight_allowance = k * avg_monthly_spend (k aus Politikregel)
2. excess = max(0, sight_balance - sight_allowance)
3. decay = sight_factor * excess
4. sight_balance -= decay
5. **Money supply sinkt** um decay

> **Offene Frage:** Sichtfaktor dynamisch? Wer setzt ihn (Clearingstelle/Staat)? Gibt es Zielgröße (Inflation=0, Lagerumschlag, Vollbeschäftigung)?

---

### 4.8 Spargrenzen & Sparkassenkredite (Sparen an Investitionsbedarf koppeln)

**Textregeln:**
* Sparvolumen muss an Kreditnachfrage für Investitionen/vorgezogenen Konsum angepasst werden.
* Zu geringe Kreditaufnahme → Absatzstockungen.
* Sparkassenkredite sollen einen (niedrigen) Kreditzins haben, um sinnlose Überinvestition zu dämpfen; aber das ist **keine Geldschöpfung**, sondern Verleih von Spargeld.

**Algorithmisch (pro Monat):**
1. Haushalte entscheiden Sparrate (abhängig von Vorsicht, Einkommen, Sichtguthaben-Abschmelzung).
2. Transfer zu Sparkasse:
   * household.sight_balance -= s
   * household.savings_balance += s
   * Kaufkraft sinkt, Geldmenge (gesamt) bleibt, aber M1 sinkt.
3. Sparkasse vergibt Kredite aus savings_pool:
   * loan_amount <= available_savings_pool
   * borrower.sight_balance += loan_amount
   * borrower.loan_balance += loan_amount
4. Tilgung/Raten → Sparkasse, ggf. Abschreibung fauler Kredite aus Risikorücklage (und dadurch ggf. Geldvernichtung, wenn Risikorücklagen „vernichtet“ werden – sinngemäß im Text bei Abschreibungen).

> **Offene Frage:** Konkrete Spargrenzen-Formel fehlt im extrahierten Ausschnitt. (Es ist aber als zentrales Steuerinstrument angekündigt.)

---

## 5) Makro-Messgrößen (für „Validität & Praxistauglichkeit“)

Damit du das System testen kannst, solltest du in jedem Tick mindestens tracken:

* **Money supply (M1-Proxy)**: Summe aller sight_balance (inkl. positiver Salden) minus ggf. negatives? (Definiere sauber.)
* **CC-Exposure**: Summe abs(retailer.cc_balance)
* **Warenwertmenge (Value)**: Summe inventory_value bei Retailern (oder inklusive Produzentenlager, wenn modelliert)
* **Velocity**: Transaktionsvolumen / durchschnittliches Geld
* **Preisniveau** (CPI-Proxy) & **Selbstkosten-Abstand** (wenn du Produktionskosten modellierst)
* **Absatzstockungen**: Lageraufbau + sinkende Umschlagsgeschwindigkeit
* **Insolvenzrate** (Retailer, Produzenten, Sparkassenkreditnehmer)
* **Ungleichheit**: Gini auf Sicht- und Sparguthaben
* **Bankenstabilität**: Reservequote, Audit-Findings, Wertberichtigungen
* **Vollbeschäftigung/Output**: wenn Arbeitsmarkt modelliert ist
