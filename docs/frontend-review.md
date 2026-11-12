# Frontend review — 2026-11-12

The existing Django templates, local Persian fonts, RTL layout and literary visual identity are retained. All user-facing pages inherit the shared responsive corrections. Django admin retains its native interface.

## Appearance

Settings now provides four palettes: paper/pomegranate (default), ocean, forest and plum. Each palette supplies matching surfaces, text, accents, control borders and feature colors for light and dark modes. Automatic mode follows the device using CSS media queries, including changes while the page is open.

`User.palette` persists independently of `User.theme`; migration `accounts.0008_user_palette` assigns the original palette to existing accounts. The header toggle updates only the display mode. Settings previews are temporary until submitted, have a reset control, and remain usable without JavaScript through the native form. Invalid palette values are rejected server-side.

Deploy using the existing build workflow, which runs collectstatic and migrations before serving the new application. For manual deployments, run `python manage.py migrate` and `python manage.py collectstatic --noinput` with the deployment environment configured.

## Corrections

- Responsive poet grids fit narrow screens; filters scroll within their own region without widening the page.
- Shared headings, breadcrumbs, card metadata and action areas wrap long content. Laptop grids account for the sidebar width.
- Small-screen reading controls stack, verse controls retain their own space, and settings palette choices remain accessible native radios.
- Linked chips, alphabet filters and pagination have larger touch targets. Native select arrows follow the current color scheme.
- Mobile navigation closes with Escape/outside clicks and resets across desktop/mobile breakpoints. Escape returns focus to its trigger.
- Favorite updates retain the SVG icon and update the accessible action label and pressed state.
- Removing an editor row moves focus to an adjacent row or the add button.
- Photo forms no longer validate on GET or unrelated settings submissions; this also prevents erroneous autofocus to the file control.
- Current settings/new-poem navigation is indicated. Error pages provide specific explanations for 403, 404 and 500.
- Reduced-motion preferences are respected by notification scrolling. Field errors receive visible invalid borders and focus.
- The live design reference no longer shows hardcoded default hex values after a palette change.

## Validation

- Django suite: 70 tests passed, including all 12 saved appearance combinations, invalid palette rejection, header palette preservation, anonymous access protection and unbound photo forms.
- Migration consistency check: no missing migrations.
- Headless local Chrome against an isolated SQLite fixture database: dashboard, settings, library, archive empty state, poem detail/edit/new, topics, poets, favorites, memorization, review, discovery, treasury index/book/work, design reference and 404.
- Widths: 320, 375, 480, 768, 1024, 1280 and 1440 CSS px. No page-level horizontal overflow or JavaScript exceptions. Horizontal overflow inside the intentional filter rails is excluded.
- All four palettes × three modes × two device color preferences: foreground, secondary text, primary button/hover, selected text and feature text pairs measured at least 4.5:1.
- Browser interactions: preview/reset, save/reload, header toggle preserving palette, favorite SVG/state, Escape/focus, editor deletion focus and review rating enablement.
- Guest login, signup, invalid browser confirmation and 404 checked at 320px.
- Screenshots inspected for desktop settings and mobile treasury/settings. Local artifacts are in `artifacts/ui-review/` (gitignored).

Chrome emulation does not replace testing on physical iOS/Android devices or Safari/Firefox. The review did not change or test production account data; fixtures and browser profiles were isolated under `/tmp`.
