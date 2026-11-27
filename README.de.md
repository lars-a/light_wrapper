# Light Wrapper für Home Assistant

[English](README.md) | **Deutsch**

Fasst mehrere physische Lichter zu **einer** Lichtentität zusammen, die sich wie ein normales Licht verhält (Ein/Aus, Helligkeit, Farbtemperatur, Farben, Effekte, Übergänge). Dazu kommen optionale **Standardwerte** für Helligkeit und Farbtemperatur, die beim Einschalten ohne Parameter verwendet werden, sowie **Standard-Übergangszeiten** für Ein- und Ausschalten, global oder pro Gruppe.

## Installation

### Über den Marketplace bzw. HACS

Ab Home Assistant **2026.11** ist HACS als **Marketplace** fest eingebaut (**Einstellungen → Marketplace**); eine eigene HACS-Installation ist dann weder nötig noch möglich. Bei älteren Versionen muss [HACS](https://hacs.xyz) installiert sein.

Die Schaltflächen unten öffnen die passende Seite direkt in deinem Home Assistant (über [My Home Assistant](https://my.home-assistant.io); beim ersten Aufruf fragt die Seite nach der Adresse deiner Instanz).

**Repository hinzufügen und installieren**

[![Repository im Marketplace bzw. in HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lars-a&repository=light_wrapper&category=integration)

1. Auf die Schaltfläche klicken. Ab 2026.11 öffnet sie den Marketplace, bei älteren Versionen HACS. Die Frage, ob das Repository `lars-a/light_wrapper` hinzugefügt werden soll, mit **Hinzufügen** bestätigen.
2. **Light Wrapper** öffnen, auf **Herunterladen** klicken und die neueste Version wählen.
3. Home Assistant neu starten.

Ohne Schaltfläche fügst du das Repository `https://github.com/lars-a/light_wrapper` (Typ **Integration**) so hinzu:

* ab 2026.11: **Einstellungen → Marketplace → Per Link hinzufügen**
* vor 2026.11: **HACS** → Menü (⋮) → **Benutzerdefinierte Repositories**

Bestehende HACS-Installationen werden beim Update auf 2026.11 automatisch in den Marketplace übernommen, einschließlich benutzerdefinierter Repositories wie diesem.

**Integration einrichten**

[![Integration einrichten](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=light_wrapper)

4. Auf die Schaltfläche klicken (oder **Einstellungen → Geräte & Dienste → Integrationen → Integration hinzufügen → Light Wrapper**).
   Es werden sofort zwei Einträge angelegt, ohne weitere Fragen: **Globale Einstellungen** und **Lichtgruppen**.

**Lichtgruppen anlegen**

[![Integration öffnen](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=light_wrapper)

5. Auf der Seite der Integration (**Geräte & Dienste → Light Wrapper**) am Eintrag **Lichtgruppen** über **Lichtgruppe hinzufügen** Namen, Lichter und (optional) Bereich und Standardwerte eingeben.
   Der Bereich wird dem Gerät der Gruppe beim Anlegen zugewiesen. So entstehen die Entity-IDs gleich mit dem Bereich (z. B. `light.kuche_deckenlicht`). Später änderst du den Bereich direkt am Gerät.

Die Seite der Integration ist so aufgebaut:

* **Globale Einstellungen**: Über **Konfigurieren** (Zahnrad) stellst du die Standard-Übergangszeiten für alle Gruppen ein.
* **Lichtgruppen**: Darunter stehen die Lichtgruppen. Jede hat ein eigenes Gerät und lässt sich dort bearbeiten (Name, Lichter, Standardwerte) oder löschen. Beim Löschen verschwinden auch ihr Gerät und ihre Entitäten.

Beide Einträge gibt es nur einmal. Ihre Namen richten sich beim Anlegen nach der Systemsprache und lassen sich umbenennen. Löschst du einen davon, legt **Eintrag hinzufügen** auf der Seite der Integration ihn neu an.

**Updates**

Neue Versionen erscheinen unter **Einstellungen → Updates** bzw. im Marketplace (vor 2026.11: in HACS). Nach dem Update Home Assistant neu starten.

### Manuell

Den Ordner `custom_components/light_wrapper` nach `<config>/custom_components/light_wrapper` kopieren, Home Assistant neu starten und weiter mit Schritt 4 („Integration einrichten“).

Benötigt Home Assistant 2025.3 oder neuer. Das Icon der Integration (`custom_components/light_wrapper/brand/`) zeigt Home Assistant ab Version 2026.3 an; ältere Versionen zeigen stattdessen einen Platzhalter.

## Was angelegt wird

Pro Lichtgruppe entsteht ein Gerät mit:

| Entität | Zweck |
|---|---|
| `light.<name>` | Die Lichtgruppe |
| `number.<name>_standard_helligkeit` | Standard-Helligkeit in % (nur wenn aktiviert) |
| `number.<name>_standard_farbtemperatur` | Standard-Farbtemperatur in K (nur wenn aktiviert; nicht verfügbar, wenn keines der Lichter Farbtemperatur kann) |
| `number.<name>_standard_ubergangszeit_einschalten` | Eigene Übergangszeit beim Einschalten in s (nur wenn aktiviert) |
| `number.<name>_standard_ubergangszeit_ausschalten` | Eigene Übergangszeit beim Ausschalten in s (nur wenn aktiviert) |
| `switch.<name>_standardwerte_auch_wenn_an` | Standardwerte auch bei schon eingeschalteter Gruppe anwenden (standardmäßig an, siehe unten) |

Die Entity-IDs hängen von der Systemsprache von Home Assistant ab; hier für Deutsch.

Über die Number-Entitäten kannst du die Werte im Dashboard oder per Automation ändern, zum Beispiel tagsüber kühl und hell, abends warm und gedimmt. Aktivieren oder deaktivieren lassen sich die Standardwerte im Bearbeiten-Dialog der Gruppe über die Schalter „… verwenden“; den Wert selbst stellst du dort per Slider ein.

Der Bereich der Standard-Farbtemperatur ist der **gemeinsame Bereich** aller Lichter mit Farbtemperatur. Bei einer Lampe mit 2200–6500 K und einer mit 2700–5000 K geht er also von 2700 bis 5000 K, und jeder Wert passt für alle Lampen. Weitere Regeln:

* Lichter ohne Farbtemperatur zählen nicht mit.
* Sind die Lichter noch nicht bekannt, gilt 2000–6500 K. Das betrifft auch das Formular beim Anlegen, weil dort noch keine Lichter gewählt sind.
* Überschneiden sich die Bereiche gar nicht, gilt der Gesamtbereich.
* Liegt ein eingegebener Wert außerhalb des Bereichs der gewählten Lichter, wird er beim Speichern auf den nächsten passenden Wert gesetzt.

## Aktion `light_wrapper.set_defaults`

Ändert die Standardwerte einer oder mehrerer Lichtgruppen direkt an ihren Lichtentitäten, zum Beispiel in einer Automation:

```yaml
action: light_wrapper.set_defaults
target:
  entity_id:
    - light.wohnzimmer
    - light.flur
data:
  default_brightness_pct: 40
  default_color_temp_kelvin: 2700
  default_transition_on: 1.5
  default_transition_off: 3
```

* Die Parameter heißen wie die Attribute der Lichtentität. Alle sind optional, aber mindestens einer muss angegeben sein.
* Ein Wert setzt den Standardwert und schaltet ihn bei Bedarf ein (die Number-Entität der Gruppe entsteht dann). `null` schaltet den Standardwert ab.
* Die Farbtemperatur wird auf den gemeinsamen Bereich der Lichter der Gruppe begrenzt; Übergangszeiten werden auf 0,1 s gerundet.
* Geändert werden nur die eigenen Übergangszeiten der Gruppe, nicht die globalen.

## Globale Einstellungen

Die globalen Einstellungen öffnest du über **Konfigurieren** am Eintrag **Globale Einstellungen**. Sie legen Standard-Übergangszeiten für **alle** Lichtgruppen fest, getrennt für Ein- und Ausschalten (je 0–10 s in 0,1-s-Schritten). Für jede aktivierte Übergangszeit gibt es eine Number-Entität am Gerät **Light Wrapper Globale Einstellungen** (`number.light_wrapper_globale_einstellungen_standard_ubergangszeit_einschalten` bzw. `…_ausschalten`).

Jede Gruppe kann in ihrem Bearbeiten-Dialog mit „Eigene Übergangszeit … verwenden“ einen eigenen Wert festlegen. Der eigene Wert geht vor; ohne eigenen Wert gilt der globale, und ohne beides wird keine Übergangszeit gesendet.

Eine Übergangszeit von 0 s wird ausdrücklich als `transition: 0` gesendet. Das ist nicht dasselbe wie keine Übergangszeit: Lampen mit eigenem, eingebautem Übergang schalten dann sofort.

## Verhalten beim Ein- und Ausschalten

* Der Schalter **„Standardwerte auch wenn an“** (im Bearbeiten-Dialog der Gruppe oder als Switch-Entität) ist standardmäßig **an**. Dann setzt ein `turn_on` **ohne Parameter** die Standardwerte auch bei schon eingeschalteter Gruppe. Nur `transition` darf zusätzlich angegeben sein. Kommt eine Helligkeit oder Farbe mit, gilt das normale Verhalten: Bei eingeschalteter Gruppe wird nur der angegebene Wert geändert. Ein Helligkeits-Slider im Dashboard setzt also nicht nebenbei die Farbtemperatur zurück.
* Ist der Schalter **aus**, greifen Standardwerte nur, wenn die Gruppe **vorher aus** war. Ein `turn_on` auf ein schon eingeschaltetes Licht ändert dann nichts an Helligkeit oder Farbe.
* Die **Standard-Helligkeit** wird verwendet, wenn keine Helligkeit angegeben ist (`brightness`, `brightness_pct`, `brightness_step`, `white`).
* Die **Standard-Farbtemperatur** wird verwendet, wenn keine Farbe angegeben ist (`color_temp_kelvin`, `hs_color`, `rgb_color`, `xy_color`, `white`, `effect` …). Sie geht nur an Mitglieder, die Farbtemperatur unterstützen, und wird auf deren Bereich begrenzt.
* War die Gruppe aus, werden beide Werte unabhängig voneinander geprüft: `light.turn_on` mit nur `brightness_pct: 30` setzt dann trotzdem die Standard-Farbtemperatur.
* `transition` und `flash` werden immer durchgereicht.
* Die **Standard-Übergangszeit** wird bei jedem `turn_on` bzw. `turn_off` ohne `transition` und ohne `flash` verwendet, auch wenn die Gruppe schon an ist (z. B. beim Ändern der Helligkeit). Sie geht nur an Mitglieder, die Übergänge unterstützen.
* Manche Lichter melden ihre Fähigkeiten (Farbtemperatur und deren Bereich, Übergänge, Effekte) nur, solange sie an sind, oft auch nicht gleich nach dem Einschalten. Light Wrapper merkt sich, was jedes Mitglied im eingeschalteten Zustand meldet, auch über Neustarts hinweg, und kombiniert es immer mit dem, was das Licht gerade meldet. Wird ein Licht aus allen Gruppen entfernt, wird das Gemerkte verworfen. Ein solches Licht bekommt die Standard-Farbtemperatur und Übergangszeit, sobald es einmal bei geladenem Light Wrapper an war.
* Solche Lichter ignorieren oft auch die Farbtemperatur im Befehl, mit dem sie eingeschaltet werden. Light Wrapper wartet deshalb, bis ein Licht, das aus war, seine Farbtemperatur-Unterstützung wieder meldet (höchstens 10 s). Zeigt es dann nicht die gewünschte Farbtemperatur, bekommt es ein zweites `turn_on` nur mit der Farbtemperatur. Das läuft im Hintergrund; ein späterer Befehl mit Farbe oder das Ausschalten der Gruppe bricht es ab. Lichter, die ihre Fähigkeiten auch im ausgeschalteten Zustand melden, sind nicht betroffen.

## Zustand der Gruppe

* **An**, sobald mindestens ein Mitglied an ist; **nicht verfügbar**, wenn alle Mitglieder nicht verfügbar sind.
* Mit **„Erst an, wenn alle Lichter an sind“** (im Bearbeiten-Dialog der Gruppe, standardmäßig aus) ist die Gruppe erst an, wenn alle Mitglieder an sind. Nicht verfügbare oder unbekannte Mitglieder zählen nicht mit. Solange nur einige Mitglieder an sind, gilt die Gruppe als aus; ein `turn_on` setzt dann die Standardwerte wie beim Einschalten.
* Helligkeit, Farbtemperatur und Farben sind der Mittelwert der eingeschalteten Mitglieder.
* Unterstützte Farbmodi und Features sind die Vereinigung aller Mitglieder. Als aktueller Farbmodus gilt der häufigste unter den eingeschalteten Mitgliedern.
* Das Attribut `entity_id` listet die Mitglieder, wie bei normalen Gruppen.
* Mit **„Mitglieder ausblenden“** (im Bearbeiten-Dialog der Gruppe, standardmäßig aus) werden die Lichter der Gruppe in der Oberfläche ausgeblendet, wie bei Gruppen-Helfern. Sie werden wieder eingeblendet, wenn die Einstellung abgeschaltet, ein Licht aus der Gruppe entfernt oder die Gruppe bzw. der Eintrag **Lichtgruppen** gelöscht wird. Selbst ausgeblendete Lichter bleiben ausgeblendet.
* **„Icon wenn an“** und **„Icon wenn aus“** (im Bearbeiten-Dialog der Gruppe, optional) legen das Icon der Gruppen-Lichtentität je Zustand fest; das Icon für aus gilt auch, solange der Zustand unbekannt ist. Ist eins nicht gesetzt, gilt das Standard-Icon `mdi:lightbulb-group`. Ein direkt an der Entität eingestelltes Icon hat Vorrang.
* Aktive Standardwerte der Gruppe stehen zusätzlich als Attribute an der Lichtentität (`default_brightness_pct`, `default_color_temp_kelvin`, `default_transition_on`, `default_transition_off`). Globale Übergangszeiten erscheinen dort nicht.

## Lizenz

[MIT](LICENSE)
