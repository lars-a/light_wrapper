# Light Wrapper – Hinweise für Claude

Home-Assistant-Custom-Integration (Domain `light_wrapper`), installiert über HACS als benutzerdefiniertes Repository aus `github.com/lars-a/light_wrapper`. Sie fasst mehrere Lichter zu einer Lichtentität zusammen. Dazu kommen optionale Standardwerte für Helligkeit und Farbtemperatur, die beim Einschalten ohne Parameter gelten, und Standard-Übergangszeiten für Ein- und Ausschalten (pro Gruppe oder global). Das Verhalten im Detail steht im README (`README.md` englisch, `README.de.md` deutsch).

Sprache:

- Commit-Messages, Release-Notes, Code-Kommentare und Docstrings (auch in den Tests) sind auf **Englisch**.
- README gibt es zweimal: `README.md` (Englisch, wird von GitHub und HACS/Marketplace angezeigt) und `README.de.md` (Deutsch). Bei jeder Änderung **beide** pflegen; oben verlinken sie einander.
- Mit dem Nutzer wird Deutsch gesprochen.

## Aufbau

- `custom_components/light_wrapper/`
  - Es gibt genau **einen** Config Entry („Light Wrapper“, `single_config_entry` im Manifest). `entry.options` sind die globalen Einstellungen (nur Übergangszeiten). Jede Lichtgruppe ist ein **Untereintrag** (`subentry_type` `light_group`), ihre Einstellungen stehen in `subentry.data`. Entitäten einer Gruppe werden mit `config_subentry_id` angelegt; unique_ids und Geräte-Identifier beruhen auf der `subentry_id`, die globalen auf der `entry_id`.
  - `__init__.py`: Setup und Laufzeitdaten (`LightWrapperRuntime` mit `global_settings` und `groups`, je ein `LightWrapperData`). Der Update-Listener lädt nur neu, wenn sich die Struktur ändert (Gruppe angelegt/gelöscht/umbenannt, Lichter geändert, Standardwert an- bzw. abgeschaltet). Reine Wertänderungen (z. B. über die Number-Entitäten) gehen ohne Reload durch.
  - `config_flow.py`: Config-Flow legt den Eintrag ohne Formular an. Options-Flow (`init`) = globale Einstellungen. `LightGroupSubentryFlow` mit `user` (anlegen) und `reconfigure` (bearbeiten, inkl. Name). Die Standardwerte sind Slider; ob sie verwendet werden, steuern die Schalter `use_default_*`. Diese Schalter werden **nicht** gespeichert: Ein Standardwert steht nur in den Daten, wenn er aktiv ist.
  - `light.py`: die Gruppen-Lichtentität. `number.py`: Number-Entitäten für die Standardwerte. `switch.py`: Schalter „Standardwerte auch wenn an“ (`apply_defaults_when_on`; standardmäßig an, steht nur als `False` in `subentry.data`, wenn abgeschaltet, und wird ohne Reload übernommen). `entity.py`: `device_info()` und `LightWrapperSettingEntity` (Basis für Number/Switch, speichert in `subentry.data` bzw. `entry.options`).
  - `translations/de.json` und `en.json`: bei jedem neuen Feld **beide** pflegen.
  - `brand/icon.png` (256 px) und `icon@2x.png` (512 px): Icon, das Home Assistant ab 2026.3 anzeigt. Quelle ist `assets/icon.svg`; nach Änderungen beide PNGs neu rendern (z. B. mit `cairosvg`).
- `tests/`: pytest mit `pytest-homeassistant-custom-component`.
- `hacs.json`: HACS installiert die ZIP-Datei aus dem Release (`zip_release`). Mindestversion Home Assistant 2025.3.0 (Untereinträge mit Entitäten und Bearbeiten-Dialog).

## manifest.json

- `integration_type` muss `device` bleiben, damit die Integration unter „Integrationen“ erscheint und nicht unter „Helfer“.
- Die Schlüsselreihenfolge ist `domain`, `name`, danach alphabetisch. Hassfest prüft das.

## Tests

- Unter Windows läuft Home Assistant nicht nativ. Lokal also nur unter WSL2/Linux:
  `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements_test.txt && pytest`
- Die Lichter in den Tests sind simulierte Zustände; Aufrufe an die Mitglieder werden abgefangen (`member_calls` in `tests/conftest.py`).
- GitHub Actions (`.github/workflows/validate.yml`) führt bei jedem Push HACS-Prüfung, Hassfest und `pytest -v --timeout=60` aus. Das ist der maßgebliche Test.
- Größere Änderungen zuerst auf einen eigenen Branch pushen und erst bei grünen Tests nach `main` übernehmen.

## Release (damit HACS ein Update anbietet)

Ein Release wird **nur auf ausdrückliche Anweisung** des Nutzers erstellt, nicht von sich aus nach einem Feature oder Fix. Auch die Version im Manifest wird erst im Rahmen eines beauftragten Releases erhöht.

1. `version` in `custom_components/light_wrapper/manifest.json` erhöhen (SemVer).
2. Commit auf `main`, pushen und warten, bis „Validate“ grün ist.
3. `gh release create vX.Y.Z --title "vX.Y.Z" --notes "<changes in English>"`
4. `.github/workflows/release.yml` setzt die Version aus dem Tag ins Manifest und hängt `light_wrapper.zip` an. Prüfen mit `gh release view vX.Y.Z --json assets`.

Ohne Release sieht HACS keine neue Version. Reine Doku-Änderungen brauchen kein Release. Nach einer Änderung, die HACS-Nutzer betrifft, darf ein Release vorgeschlagen, aber nicht ungefragt erstellt werden.
