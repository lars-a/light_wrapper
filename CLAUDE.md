# Light Wrapper – Hinweise für Claude

Home-Assistant-Custom-Integration (Domain `light_wrapper`), installiert über HACS als benutzerdefiniertes Repository aus `github.com/lars-a/light_wrapper`. Sie fasst mehrere Lichter zu einer Lichtentität zusammen. Dazu kommen optionale Standardwerte für Helligkeit und Farbtemperatur, die beim Einschalten ohne Parameter gelten. Das Verhalten im Detail steht im README.

Sprache: Code-Kommentare, Docstrings, Commit-Messages und README sind auf Deutsch. Mit dem Nutzer wird Deutsch gesprochen.

## Aufbau

- `custom_components/light_wrapper/`
  - `__init__.py`: Setup und Laufzeitdaten (`LightWrapperData`). Der Update-Listener lädt nur neu, wenn sich die Lichter ändern oder ein Standardwert an- bzw. abgeschaltet wird. Reine Wertänderungen (z. B. über die Number-Entitäten) gehen ohne Reload durch.
  - `config_flow.py`: Config-Flow (anlegen) und Options-Flow (bearbeiten). Die Standardwerte sind Slider; ob sie verwendet werden, steuern die Schalter `use_default_*`. Diese Schalter werden **nicht** gespeichert: In `entry.options` steht ein Standardwert nur, wenn er aktiv ist.
  - `light.py`: die Gruppen-Lichtentität. `number.py`: Number-Entitäten für die Standardwerte. `switch.py`: Schalter „Standardwerte auch wenn an“ (`apply_defaults_when_on`; standardmäßig an, steht nur als `False` in `entry.options`, wenn abgeschaltet, und wird ohne Reload übernommen). `entity.py`: gemeinsame Basis.
  - `translations/de.json` und `en.json`: bei jedem neuen Feld **beide** pflegen.
  - `brand/icon.png` (256 px) und `icon@2x.png` (512 px): Icon, das Home Assistant ab 2026.3 anzeigt. Quelle ist `assets/icon.svg`; nach Änderungen beide PNGs neu rendern (z. B. mit `cairosvg`).
- `tests/`: pytest mit `pytest-homeassistant-custom-component`.
- `hacs.json`: HACS installiert die ZIP-Datei aus dem Release (`zip_release`).

## manifest.json

- `integration_type` muss `device` bleiben, damit die Integration unter „Integrationen“ erscheint und nicht unter „Helfer“.
- Die Schlüsselreihenfolge ist `domain`, `name`, danach alphabetisch. Hassfest prüft das.

## Tests

- Unter Windows läuft Home Assistant nicht nativ. Lokal also nur unter WSL2/Linux (siehe README).
- GitHub Actions (`.github/workflows/validate.yml`) führt bei jedem Push HACS-Prüfung, Hassfest und `pytest -v --timeout=60` aus. Das ist der maßgebliche Test.
- Größere Änderungen zuerst auf einen eigenen Branch pushen und erst bei grünen Tests nach `main` übernehmen.

## Release (damit HACS ein Update anbietet)

Ein Release wird **nur auf ausdrückliche Anweisung** des Nutzers erstellt, nicht von sich aus nach einem Feature oder Fix. Auch die Version im Manifest wird erst im Rahmen eines beauftragten Releases erhöht.

1. `version` in `custom_components/light_wrapper/manifest.json` erhöhen (SemVer).
2. Commit auf `main`, pushen und warten, bis „Validate“ grün ist.
3. `gh release create vX.Y.Z --title "vX.Y.Z" --notes "<Änderungen auf Deutsch>"`
4. `.github/workflows/release.yml` setzt die Version aus dem Tag ins Manifest und hängt `light_wrapper.zip` an. Prüfen mit `gh release view vX.Y.Z --json assets`.

Ohne Release sieht HACS keine neue Version. Reine Doku-Änderungen brauchen kein Release. Nach einer Änderung, die HACS-Nutzer betrifft, darf ein Release vorgeschlagen, aber nicht ungefragt erstellt werden.
