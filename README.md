# Adam Hale Shapiro's website

Academic website hosted on GitHub Pages at adam-hale-shapiro.com.
The publishable website is in `docs/`. No paid hosting or production dependencies
are required. The site includes responsive navigation, research and Economic
Letters search, paper abstracts, dashboards, and downloadable research assets.

## Edit the website

- Home: `docs/index.html`
- Research: `docs/research/index.html`
- Economic Letters: `docs/blank-1/index.html`
- Code & Data: `docs/blank-2/index.html`
- Individual paper pages retain their existing paths in `docs/`.
- Shared appearance: `docs/assets/style.css`

Page content is maintained in `content/site.json`. The shared HTML layouts are
in `scripts/build_site.py`. Edit the content or layout and regenerate the pages:

```powershell
py scripts/build_site.py
node --check docs/assets/site.js
py -m http.server 8766 --bind 127.0.0.1 --directory docs
```

The renderer uses Python's standard library. Preview the result, then commit the
content, renderer, and generated `docs/` changes together. GitHub Pages publishes
from the `main` branch's `/docs` folder. Direct HTML edits in `docs/` must also be
carried into the source content or layout before rebuilding.

The site uses system fonts, local assets, and a small progressive-enhancement
script. All pages, abstracts, and downloads remain accessible without JavaScript;
JavaScript adds the mobile menu and instant search.

## Domain migration

First verify `adam-hale-shapiro.com` under the GitHub account's Pages settings.
Then set this repository's Pages custom domain to `adam-hale-shapiro.com` and
update the website DNS records at Wix. Preserve all email-related DNS records.
Follow current GitHub Pages DNS documentation rather than assuming saved IP
addresses remain current. Enable Enforce HTTPS when the certificate is ready.

Wix can remain the domain registrar. Domain registration must be renewed before
its 2029 expiration, or transferred to a different registrar before expiration.
GitHub Pages provides hosting, not free registration of the custom domain.

## Migration records

`migration/inventory.json` records the captured pages, original source hashes,
downloaded Wix assets and any capture failures. Original HTML snapshots are in
the local ignored `migration/source/` directory. They are not published.

The one-time `migration/migrate.py` importer captures the old public Wix site.
Do not rerun it after editing the new site: edit `docs/` directly instead.

## Analytics

All 26 pages use the asynchronous GoatCounter script in `scripts/build_site.py`.
The endpoint is `https://adam-hale-shapiro.goatcounter.com/count`.
View the private dashboard at https://adam-hale-shapiro.goatcounter.com/ using the
existing GoatCounter login. This website has separate statistics from ISMI and
Supply & Demand. Do not replace its endpoint with either dashboard's endpoint.

GoatCounter skips localhost and other local previews by default. Keep that
behavior so development visits do not pollute the website's statistics.
Documentation: https://www.goatcounter.com/help/start
