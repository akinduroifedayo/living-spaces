# Weather Window · a Space without the kit look

Copy `space.json`, `index.html`, `styles.css`, `app.js` into a Space. It needs no kit CSS, framework, library or font. The host can still provide persistence; this particular public forecast has no records to save. City selection is explicitly volatile. No geolocation or account is used.

This is a **dashboard** composition: current temperature and conditions at the left, twelve actual hourly forecasts at the right, exact values behind a native disclosure. SVG geometry comes from a linear scale over response values; it is not a decorative trend. Both daylight and dark palettes are authored.

It calls the public Open-Meteo forecast API over HTTPS with CORS. Attribution links to Open-Meteo; forecasts are estimates, not observations. Provider availability, terms and embedding/network policy need to be checked when shipping a derivative. It requests no secrets.

The app loads live data when available, retains the last forecast on a later failure, rejects incomplete responses, supports retry, cancels superseded requests and has a twelve-second timeout. **Explore sample** is a user-chosen, clearly labelled synthetic dataset, never a silent fallback passed off as live weather. The exact Internet Off message is used only if the host actually supplies `space.meta.network === 'off'`; generic load failure never pretends to know the permission state.

Render directly with the design static server for design review. A static HTTP success proves neither opaque-origin CORS nor the production internet isolation boundary. Forge owns network qualification; in an offline sandbox the sample still works. Screenshots and executed states are recorded under `docs/design/space-kit/`.
