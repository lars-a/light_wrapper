# Light Wrapper for Home Assistant

**English** | [Deutsch](README.de.md)

Combines several physical lights into **one** light entity that behaves like a regular light (on/off, brightness, color temperature, colors, effects, transitions). On top of that, there are optional **defaults** for brightness and color temperature that are used when the light is turned on without parameters, and **default transitions** for turning on and off, either global or per group.

## Installation

### Via the Marketplace or HACS

Starting with Home Assistant **2026.11**, HACS is built in as the **Marketplace** (**Settings → Marketplace**); a separate HACS installation is then neither needed nor possible. Older versions require [HACS](https://hacs.xyz) to be installed.

The buttons below open the matching page directly in your Home Assistant (via [My Home Assistant](https://my.home-assistant.io); on first use, the page asks for the address of your instance).

**Add the repository and install**

[![Open the repository in the Marketplace or HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lars-a&repository=light_wrapper&category=integration)

1. Click the button. From 2026.11 on, it opens the Marketplace; on older versions, HACS. When asked whether to add the repository `lars-a/light_wrapper`, confirm with **Add**.
2. Open **Light Wrapper**, click **Download** and select the latest version.
3. Restart Home Assistant.

Without the button, add the repository `https://github.com/lars-a/light_wrapper` (type **Integration**) like this:

* from 2026.11: **Settings → Marketplace → Add via link**
* before 2026.11: **HACS** → menu (⋮) → **Custom repositories**

Existing HACS installations are moved to the Marketplace automatically when updating to 2026.11, including custom repositories like this one.

**Set up the integration**

[![Set up the integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=light_wrapper)

4. Click the button (or **Settings → Devices & services → Integrations → Add integration → Light Wrapper**).
   Two entries are created right away, without further questions: **Global settings** and **Light groups**.

**Add light groups**

[![Open the integration](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=light_wrapper)

5. On the integration page (**Devices & services → Light Wrapper**), use **Add light group** on the **Light groups** entry and enter a name, the lights and (optionally) defaults.

The integration page is organized like this:

* **Global settings**: use **Configure** (gear icon) to change the default transitions for all groups.
* **Light groups**: lists the light groups below it. Each has its own device and can be edited there (name, lights, defaults) or deleted. Deleting a group also removes its device and entities.

Each entry exists only once. The entry names follow the system language at the time they are created and can be renamed. If you delete one of them, **Add entry** on the integration page creates it again.

**Updates**

New versions appear under **Settings → Updates** and in the Marketplace (before 2026.11: in HACS). Restart Home Assistant after updating.

### Manual

Copy the folder `custom_components/light_wrapper` to `<config>/custom_components/light_wrapper`, restart Home Assistant and continue with step 4 ("Set up the integration").

Requires Home Assistant 2025.3 or newer. Home Assistant shows the integration icon (`custom_components/light_wrapper/brand/`) from version 2026.3 on; older versions show a placeholder instead.

## What gets created

Each light group gets a device with:

| Entity | Purpose |
|---|---|
| `light.<name>` | The light group |
| `number.<name>_default_brightness` | Default brightness in % (only if enabled) |
| `number.<name>_default_color_temperature` | Default color temperature in K (only if enabled; unavailable if none of the lights supports color temperature) |
| `number.<name>_transition_on` | Own transition when turning on, in s (only if enabled) |
| `number.<name>_transition_off` | Own transition when turning off, in s (only if enabled) |
| `switch.<name>_apply_defaults_when_on` | Apply defaults even if the group is already on (on by default, see below) |

Entity IDs depend on the system language of Home Assistant; shown here for English.

With the number entities you can change the values from a dashboard or an automation, for example cool and bright during the day, warm and dimmed in the evening. The defaults are enabled or disabled in the group's edit dialog with the "Use …" toggles; the value itself is set there with a slider.

The range of the default color temperature is the **common range** of all lights with color temperature. With one lamp at 2200–6500 K and another at 2700–5000 K, it goes from 2700 to 5000 K, so every value works for all lamps. Further rules:

* Lights without color temperature are not counted.
* If the lights are not known yet, 2000–6500 K applies. This also affects the form when adding a group, because no lights are selected there yet.
* If the ranges do not overlap at all, the combined range applies.
* If an entered value is outside the range of the selected lights, it is set to the nearest valid value when saving.

## Global settings

Open the global settings with **Configure** on the **Global settings** entry. They define default transitions for **all** light groups, separately for turning on and off (0–10 s each, in 0.1 s steps). Each enabled transition gets a number entity on the **Light Wrapper global settings** device (`number.light_wrapper_global_settings_transition_on` or `…_transition_off`).

Each group can set its own value in its edit dialog with "Use own transition …". The group's own value takes precedence; without one, the global value applies, and without either, no transition is sent.

A transition of 0 s is sent explicitly as `transition: 0`. This is not the same as no transition: lamps with their own built-in transition then switch instantly.

## Behavior when turning on and off

* The **"Apply defaults when on"** switch (in the group's edit dialog or as a switch entity) is **on** by default. A `turn_on` **without parameters** then applies the defaults even if the group is already on. Only `transition` may be given in addition. If a brightness or color is included, the normal behavior applies: with the group already on, only the given value changes. So a brightness slider in a dashboard does not reset the color temperature along the way.
* If the switch is **off**, defaults only apply if the group was **off before**. A `turn_on` on a light that is already on then does not change brightness or color.
* The **default brightness** is used if no brightness is given (`brightness`, `brightness_pct`, `brightness_step`, `white`).
* The **default color temperature** is used if no color is given (`color_temp_kelvin`, `hs_color`, `rgb_color`, `xy_color`, `white`, `effect` …). It is only sent to members that support color temperature and is limited to their range.
* If the group was off, both values are checked independently: `light.turn_on` with only `brightness_pct: 30` still applies the default color temperature.
* `transition` and `flash` are always passed through.
* The **default transition** is used for every `turn_on` or `turn_off` without `transition` and without `flash`, even if the group is already on (for example when changing the brightness). It is only sent to members that support transitions.

## Group state

* **On** as soon as at least one member is on; **unavailable** if all members are unavailable.
* With **"On only when all lights are on"** (in the group's edit dialog, off by default), the group is only on when all members are on. Members that are unavailable or unknown are not counted. While only some members are on, the group counts as off, so a `turn_on` applies the defaults as when switching on.
* Brightness, color temperature and colors are the average of the members that are on.
* Supported color modes and features are the union of all members. The current color mode is the most common one among the members that are on.
* The `entity_id` attribute lists the members, as with regular groups.
* With **"Hide members"** (in the group's edit dialog, off by default), the group's lights are hidden in the UI, like with group helpers. They are shown again when the setting is turned off, when a light is removed from the group, or when the group or the **Light groups** entry is deleted. Lights you hid yourself stay hidden.
* The group's active defaults are also shown as attributes of the light entity (`default_brightness_pct`, `default_color_temp_kelvin`, `default_transition_on`, `default_transition_off`). Global transitions do not appear there.

## License

[MIT](LICENSE)
