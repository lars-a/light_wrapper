# Light Wrapper für Home Assistant

Fasst mehrere physische Lichter zu **einer** Lichtentität zusammen, die sich wie ein normales Licht verhält (Ein/Aus, Helligkeit, Farbtemperatur, Farben, Effekte, Übergänge). Dazu kommen optionale **Standardwerte** für Helligkeit und Farbtemperatur, die beim Einschalten ohne Parameter verwendet werden, sowie **Standard-Übergangszeiten** für Ein- und Ausschalten, global oder pro Gruppe.

## Installation

### Über HACS

1. In Home Assistant **HACS** öffnen → Menü (⋮) → **Benutzerdefinierte Repositories**.
2. Repository `https://github.com/lars-a/light_wrapper` mit Typ **Integration** hinzufügen.
3. **Light Wrapper** in HACS suchen und herunterladen.
4. Home Assistant neu starten.
5. **Einstellungen → Geräte & Dienste → Integrationen → Integration hinzufügen → Light Wrapper**.
6. **Lichtgruppe** wählen, dann Namen, Lichter und (optional) Standardwerte eingeben.

Weitere Wrapper und die **Globalen Einstellungen** legst du auf der Seite der Integration (**Geräte & Dienste → Light Wrapper**) über **Gerät hinzufügen** an. Die Auswahl zwischen „Lichtgruppe“ und „Globale Einstellungen“ erscheint nur, solange es die globalen Einstellungen noch nicht gibt. Dort sind alle Wrapper aufgelistet; über **Konfigurieren** (Zahnrad) öffnest du den Dialog, um Lichter und Standardwerte eines Wrappers zu ändern. Umbenennen geht über das ⋮-Menü des Eintrags.

### Manuell

Den Ordner `custom_components/light_wrapper` nach `<config>/custom_components/light_wrapper` kopieren, Home Assistant neu starten und weiter mit Schritt 5.

Benötigt Home Assistant 2025.2 oder neuer. Das Icon der Integration (`custom_components/light_wrapper/brand/`) zeigt Home Assistant ab Version 2026.3 an; ältere Versionen zeigen stattdessen einen Platzhalter.

## Was angelegt wird

Pro Wrapper entsteht ein Gerät mit:

| Entität | Zweck |
|---|---|
| `light.<name>` | Die Lichtgruppe |
| `number.<name>_standardhelligkeit` | Standardhelligkeit in % (nur wenn aktiviert) |
| `number.<name>_standard_farbtemperatur` | Standard-Farbtemperatur in K (nur wenn aktiviert; nicht verfügbar, wenn keines der Lichter Farbtemperatur kann) |
| `number.<name>_ubergangszeit_einschalten` | Eigene Übergangszeit beim Einschalten in s (nur wenn aktiviert) |
| `number.<name>_ubergangszeit_ausschalten` | Eigene Übergangszeit beim Ausschalten in s (nur wenn aktiviert) |
| `switch.<name>_standardwerte_auch_wenn_an` | Standardwerte auch bei schon eingeschalteter Gruppe anwenden (standardmäßig an, siehe unten) |

Über die Number-Entitäten kannst du die Werte im Dashboard oder per Automation ändern, zum Beispiel tagsüber kühl und hell, abends warm und gedimmt. Aktivieren oder deaktivieren lassen sich die Standardwerte unter **Konfigurieren** über die Schalter „… verwenden“; den Wert selbst stellst du dort per Slider ein.

Der Bereich der Standard-Farbtemperatur ist der **gemeinsame Bereich** aller Lichter mit Farbtemperatur. Bei einer Lampe mit 2200–6500 K und einer mit 2700–5000 K geht er also von 2700 bis 5000 K, und jeder Wert passt für alle Lampen. Weitere Regeln:

* Lichter ohne Farbtemperatur zählen nicht mit.
* Sind die Lichter noch nicht bekannt, gilt 2000–6500 K. Das betrifft auch das Formular beim Anlegen, weil dort noch keine Lichter gewählt sind.
* Überschneiden sich die Bereiche gar nicht, gilt der Gesamtbereich.
* Liegt ein eingegebener Wert außerhalb des Bereichs der gewählten Lichter, wird er beim Speichern auf den nächsten passenden Wert gesetzt.

## Globale Einstellungen

Den Eintrag **Globale Einstellungen** gibt es höchstens einmal. Er legt Standard-Übergangszeiten für **alle** Lichtgruppen fest, getrennt für Ein- und Ausschalten (je 0–10 s in 0,1-s-Schritten). Für jede aktivierte Übergangszeit gibt es eine Number-Entität (`number.globale_einstellungen_ubergangszeit_einschalten` bzw. `…_ausschalten`).

Jede Gruppe kann unter **Konfigurieren** mit „Eigene Übergangszeit … verwenden“ einen eigenen Wert festlegen. Der eigene Wert geht vor; ohne eigenen Wert gilt der globale, und ohne beides wird keine Übergangszeit gesendet.

## Verhalten beim Einschalten

* Der Schalter **„Standardwerte auch wenn an“** (im Dialog **Konfigurieren** oder als Switch-Entität) ist standardmäßig **an**. Dann setzt ein `turn_on` **ohne Parameter** die Standardwerte auch bei schon eingeschalteter Gruppe. Nur `transition` darf zusätzlich angegeben sein. Kommt eine Helligkeit oder Farbe mit, gilt das normale Verhalten: Bei eingeschalteter Gruppe wird nur der angegebene Wert geändert. Ein Helligkeits-Slider im Dashboard setzt also nicht nebenbei die Farbtemperatur zurück.
* Ist der Schalter **aus**, greifen Standardwerte nur, wenn die Gruppe **vorher aus** war. Ein `turn_on` auf ein schon eingeschaltetes Licht ändert dann nichts an Helligkeit oder Farbe.
* Die **Standardhelligkeit** wird verwendet, wenn keine Helligkeit angegeben ist (`brightness`, `brightness_pct`, `brightness_step`, `white`).
* Die **Standard-Farbtemperatur** wird verwendet, wenn keine Farbe angegeben ist (`color_temp_kelvin`, `hs_color`, `rgb_color`, `xy_color`, `white`, `effect` …). Sie geht nur an Mitglieder, die Farbtemperatur unterstützen, und wird auf deren Bereich begrenzt.
* Beide Werte werden unabhängig voneinander geprüft: `light.turn_on` mit nur `brightness_pct: 30` setzt trotzdem die Standard-Farbtemperatur.
* `transition` und `flash` werden immer durchgereicht.
* Die **Standard-Übergangszeit** wird bei jedem `turn_on` bzw. `turn_off` ohne `transition` und ohne `flash` verwendet, auch wenn die Gruppe schon an ist (z. B. beim Ändern der Helligkeit). Sie geht nur an Mitglieder, die Übergänge unterstützen.

## Zustand der Gruppe

* **An**, sobald mindestens ein Mitglied an ist; **nicht verfügbar**, wenn alle Mitglieder nicht verfügbar sind.
* Helligkeit, Farbtemperatur und Farben sind der Mittelwert der eingeschalteten Mitglieder.
* Unterstützte Farbmodi und Features sind die Vereinigung aller Mitglieder. Als aktueller Farbmodus gilt der häufigste unter den eingeschalteten Mitgliedern.
* Das Attribut `entity_id` listet die Mitglieder, wie bei normalen Gruppen.

## Lizenz

[MIT](LICENSE)
