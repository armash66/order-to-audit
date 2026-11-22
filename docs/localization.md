# Localization

[Documentation](README.md)

## Behavior

The active React interface supports English (`en`), Tamil (`ta`), Hindi (`hi`) and Marathi (`mr`). One selector covers sign-in, account controls, setup, orders, production, inventory, reports, visits and offline capture. The browser stores the preference as `ota-language`; the document language follows it.

The catalogue is bundled with the application so offline capture does not need a translation API request. [translations.json](../frontend/src/translations.json) is the single source. The authenticated compatibility endpoint reads that same file.

## Translation boundaries

Translate headings, actions, help, statuses, form labels, confirmations, table labels and known validation messages. Preserve numbers, item codes, GST identifiers and user-entered records. Known seed names have catalogue entries. Invoice PDFs and report exports retain their recorded English content.

Unrecognized server errors currently use a localized retry message. That avoids an English fragment but may provide less detail than English mode. Native-speaker review of all three languages remains necessary before claiming linguistic certification.

## Adding or changing copy

1. Keep a stable English phrase as the catalogue key.
2. Add a complete translation to `ta`, `hi` and `mr` together.
3. Use the shared language hooks; do not add a second dictionary or fetch translations per page.
4. Keep dynamic numbers and business values outside translated phrases.
5. Translate browser confirmations and accessibility labels too.
6. Check the phrase in its actual form, table or message at phone and desktop widths.

The shared renderer translates known text nodes and accessibility labels; each component must apply it to its own returned tree. Explicit translation calls handle dynamic labels. Error messages are translated at render time so switching language updates a visible error.

## Verification

From the repository root, after installing frontend dependencies:

```sh
node scripts/check_i18n.cjs
python scripts/react_language_check.py --width 360
python scripts/react_language_check.py --width 1280
```

The source check detects missing static labels and unequal catalogue key sets. Browser checks cover language switching, login errors, four roles, all workspace tabs, setup and direct offline access. These checks establish coverage and behavior; they cannot certify idiomatic wording.
