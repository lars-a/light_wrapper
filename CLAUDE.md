# Light Wrapper – Hinweise für Claude

Home-Assistant-Custom-Integration (Domain `light_wrapper`), installiert über HACS als benutzerdefiniertes Repository aus `github.com/lars-a/light_wrapper`. Sie fasst mehrere Lichter zu einer Lichtentität zusammen. Dazu kommen optionale Standardwerte für Helligkeit und Farbtemperatur, die beim Einschalten ohne Parameter gelten, und Standard-Übergangszeiten für Ein- und Ausschalten (pro Gruppe oder global). Das Verhalten im Detail steht im README (`README.md` englisch, `README.de.md` deutsch).

Sprache:

- Commit-Messages, Release-Notes, Code-Kommentare und Docstrings (auch in den Tests) sind auf **Englisch**.
- README gibt es zweimal: `README.md` (Englisch, wird von GitHub und HACS/Marketplace angezeigt) und `README.de.md` (Deutsch). Bei jeder Änderung **beide** pflegen; oben verlinken sie einander.
- Mit dem Nutzer wird Deutsch gesprochen.

## Aufbau

- `custom_components/light_wrapper/`
  - Es gibt genau **zwei** Config Entries, beide mit `entry.data["entry_type"]`, das zugleich die `unique_id` ist: `global` („Globale Einstellungen“, `entry.options` = Übergangszeiten, nur Number-Plattform, einziger Eintrag mit Options-Flow) und `groups` („Lichtgruppen“, jede Lichtgruppe ist ein **Untereintrag** mit `subentry_type` `light_group`, Einstellungen in `subentry.data`). Unterscheiden mit `is_global()`. Die Lichtentität liest die globalen Übergangszeiten beim Aufruf über `global_defaults()`. Entitäten einer Gruppe werden mit `config_subentry_id` angelegt; unique_ids und Geräte-Identifier beruhen auf der `subentry_id`, die globalen auf der `entry_id`.
  - `__init__.py`: Setup und Laufzeitdaten (`LightWrapperRuntime` mit `global_settings` und `groups`, je ein `LightWrapperData`). Der Update-Listener lädt nur neu, wenn sich die Struktur ändert (Gruppe angelegt/gelöscht/umbenannt, Lichter geändert, Standardwert an- bzw. abgeschaltet). Reine Wertänderungen (z. B. über die Number-Entitäten) gehen ohne Reload durch.
  - `config_flow.py`: Der Config-Flow (`user`) legt den ersten fehlenden Eintrag ohne Formular an und startet für den anderen einen Flow mit `SOURCE_IMPORT` (`async_step_import`). **Nicht** `SOURCE_SYSTEM` verwenden: Für System-Einträge blendet die Oberfläche Löschen, Deaktivieren und Neu laden aus. `async_setup` ersetzt einen alten System-Eintrag (bis 0.7.1) einmalig durch einen Import-Eintrag mit gleichem Titel und gleichen Optionen. Die Titel kommen aus `ENTRY_TITLES` nach Systemsprache. Options-Flow (`init`) = globale Einstellungen (`async_supports_options_flow` nur für `global`), Untereintrags-Typ nur für `groups`. `LightGroupSubentryFlow` mit `user` (anlegen, inkl. Bereich) und `reconfigure` (bearbeiten, inkl. Name, ohne Bereich). Der Bereich steht als `area_id` in `subentry.data`; `_async_create_group_devices()` in `__init__.py` legt damit beim Setup das Gerät an, bevor die Plattformen die Entitäten anlegen, damit Home Assistant die Entity-IDs gleich mit dem Bereich bildet. Bestehende Geräte bleiben unberührt (Bereich pflegt dann der Nutzer am Gerät). Die Standardwerte sind Slider; ob sie verwendet werden, steuern die Schalter `use_default_*`. Diese Schalter werden **nicht** gespeichert: Ein Standardwert steht nur in den Daten, wenn er aktiv ist.
  - `capabilities.py`: merkt sich die Fähigkeiten der Mitglieder (Farbmodi, Farbtemperaturbereich, Features, Effekte), die sie im eingeschalteten Zustand melden (`Store` `light_wrapper.capabilities`, geladen in `async_setup`). Für Lichter, die sie im ausgeschalteten Zustand oder direkt nach dem Einschalten nicht melden: Gemerktes und Gemeldetes werden immer kombiniert (Modi, Features und Effekte vereinigt), Lichter außerhalb aller Gruppen werden beim Setup vergessen (`async_keep_capabilities`). Fähigkeiten von Mitgliedern **immer** über `member_capabilities()` lesen, nicht direkt aus dem Zustand.
  - `light.py`: die Gruppen-Lichtentität, inkl. der Aktion `light_wrapper.set_defaults` (Entity-Service, registriert über `platform.async_register_entity_service`, weil `async_register_platform_entity_service` erst nach 2025.3 existiert; Felder in `services.yaml`, Texte unter `services` in den Übersetzungen). `number.py`: Number-Entitäten für die Standardwerte. `switch.py`: Schalter „Standardwerte auch wenn an“ (`apply_defaults_when_on`; standardmäßig an, steht nur als `False` in `subentry.data`, wenn abgeschaltet, und wird ohne Reload übernommen). Die Einstellung „Erst an, wenn alle Lichter an sind“ (`on_when_all_on`) gibt es bewusst **nur im Bearbeiten-Dialog**, nicht als Entität; standardmäßig aus, steht nur als `True` in `subentry.data` und wirkt ohne Reload. Ebenso „Farbtemperatur nach dem Einschalten erneut senden“ (`resend_color_temp`, nur `True` gespeichert, von `light.py` beim Aufruf direkt aus `subentry.data` gelesen; zweites `turn_on` nur an Mitglieder, die vorher aus waren, nach `RESEND_COLOR_TEMP_DELAY`) und „Mitglieder ausblenden“ (`hide_members`): `_async_update_hidden_members()` in `__init__.py` setzt `hidden_by=integration` im Entity-Register beim Setup und in jedem Update-Listener-Aufruf und blendet beim Entfernen von Lichtern/Gruppen/Eintrag (`async_remove_entry`) wieder ein; vom Nutzer ausgeblendete Lichter bleiben unberührt. `entity.py`: `device_info()` und `LightWrapperSettingEntity` (Basis für Number/Switch, speichert in `subentry.data` bzw. `entry.options`).
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
