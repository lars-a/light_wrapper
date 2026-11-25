# Light Wrapper für Home Assistant

Fasst mehrere physische Lichter zu **einer** Lichtentität zusammen, die sich wie ein normales Licht verhält (Ein/Aus, Helligkeit, Farbtemperatur, Farben, Effekte, Übergänge). Dazu kommen optionale **Standardwerte** für Helligkeit und Farbtemperatur, die beim Einschalten ohne Parameter verwendet werden.

## Installation

### Über HACS

1. In Home Assistant **HACS** öffnen → Menü (⋮) → **Benutzerdefinierte Repositories**.
2. Repository `https://github.com/lars-a/light_wrapper` mit Typ **Integration** hinzufügen.
3. **Light Wrapper** in HACS suchen und herunterladen.
4. Home Assistant neu starten.
5. **Einstellungen → Geräte & Dienste → Helfer → Helfer erstellen → Light Wrapper**.
6. Namen, Lichter und (optional) Standardwerte eingeben.

### Manuell

Den Ordner `custom_components/light_wrapper` nach `<config>/custom_components/light_wrapper` kopieren, Home Assistant neu starten und weiter mit Schritt 5.

Benötigt Home Assistant 2025.2 oder neuer.

## Was angelegt wird

Pro Wrapper entsteht ein Gerät mit:

| Entität | Zweck |
|---|---|
| `light.<name>` | Die Lichtgruppe |
| `number.<name>_standardhelligkeit` | Standardhelligkeit in % (nur wenn aktiviert) |
| `number.<name>_standard_farbtemperatur` | Standard-Farbtemperatur in K (nur wenn aktiviert; nicht verfügbar, wenn keines der Lichter Farbtemperatur kann) |

Über die Number-Entitäten kannst du die Werte im Dashboard oder per Automation ändern, zum Beispiel tagsüber kühl und hell, abends warm und gedimmt. Aktivieren oder deaktivieren lassen sich die Standardwerte unter **Konfigurieren** (Feld leeren = deaktiviert).

## Verhalten beim Einschalten

* Standardwerte greifen nur, wenn die Gruppe **vorher aus** war. Ein `turn_on` auf ein schon eingeschaltetes Licht ändert nichts an der Helligkeit.
* Die **Standardhelligkeit** wird verwendet, wenn keine Helligkeit angegeben ist (`brightness`, `brightness_pct`, `brightness_step`, `white`).
* Die **Standard-Farbtemperatur** wird verwendet, wenn keine Farbe angegeben ist (`color_temp_kelvin`, `hs_color`, `rgb_color`, `xy_color`, `white`, `effect` …). Sie geht nur an Mitglieder, die Farbtemperatur unterstützen, und wird auf deren Bereich begrenzt.
* Beide Werte werden unabhängig voneinander geprüft: `light.turn_on` mit nur `brightness_pct: 30` setzt trotzdem die Standard-Farbtemperatur.
* `transition` und `flash` werden immer durchgereicht.

## Tests

Home Assistant läuft nicht nativ unter Windows, deshalb die Tests unter **WSL2 (Ubuntu)** ausführen:

```bash
cd /mnt/d/Claude/light_wrapper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Die Lichter in den Tests sind simulierte Zustände; Aufrufe an die Mitglieder werden abgefangen und geprüft.

## Zustand der Gruppe

* **An**, sobald mindestens ein Mitglied an ist; **nicht verfügbar**, wenn alle Mitglieder nicht verfügbar sind.
* Helligkeit, Farbtemperatur und Farben sind der Mittelwert der eingeschalteten Mitglieder.
* Unterstützte Farbmodi und Features sind die Vereinigung aller Mitglieder. Als aktueller Farbmodus gilt der häufigste unter den eingeschalteten Mitgliedern.
* Das Attribut `entity_id` listet die Mitglieder, wie bei normalen Gruppen.
