# Adam Hale Shapiro's website

Academic website hosted on GitHub Pages at adam-hale-shapiro.com.
The publishable website is in `docs/`. No paid hosting or production dependencies
are required. The site includes responsive navigation, research and Economic
Letters search, paper abstracts, dashboards, and downloadable research assets.

## Sharing previews and link monitoring

Every generated page includes its own canonical URL and Open Graph title,
description, and image, plus equivalent Twitter card tags. The shared
1200 × 630 JPEG is `docs/assets/social-preview.jpg`, using the existing trees
and Source Sans 3. These tags do not change the rendered website. Rebuild
after replacing the image so its cache version updates. LinkedIn may cache
older cards; its Post Inspector can refresh a URL without publishing a post:
https://www.linkedin.com/post-inspector/

The image's HTML source is `content/social-preview.html`. Serve the repository
root and render that page at 1200 × 630 to replace the JPEG. It uses the website's
banner opacity and fade, with an edge-to-edge image and the existing typography.

`Check website links` runs weekly on Mondays at 15:23 UTC, after relevant
pushes, and on demand under GitHub Actions. Pull requests check local references
only. It validates published files, page anchors, sharing-image references,
and public external links without credentials. Confirmed HTTP 404/410 links
are checked twice with GET; paywalls, bot protection, and temporary network
failures are reported separately as verification limits.

Each run saves JSON and Markdown reports for 30 days and adds a job summary.
Confirmed broken links fail the check and open or update one issue in this
repository; unchanged findings do not create duplicate issues. The issue closes
when those failures are resolved. Repository notification preferences determine
GitHub's email notifications. The workflow never rewrites site links or edits
Google Drive files. GitHub may disable schedules on a public repository after
60 days without repository activity; re-enable the workflow in Actions if needed.

Run manually:

```powershell
py -m unittest discover -s scripts/tests -v
py scripts/audit_links.py --output link-report.json --fail-on-broken
```

Use `--local-only` to skip external network checks. Keep local report output
outside the published `docs/` directory.

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

## Dashboard update dates

The Code & Data page reads the public CSV used by each dashboard on page load,
with cache revalidation. "Updated" comes from the CSV's Last-Modified header
(the GitHub Pages publication time); "Data through" is the latest populated
month in that CSV. Both ISO dates and Stata monthly dates are supported.
Publishing new dashboard data updates these labels without rebuilding this site.
If the source is unavailable, visitors are directed to the dashboard for the
latest data rather than seeing an old hard-coded date.

## Paper citations

`content/citations.json` holds verified bibliographic metadata and source URLs
for every Research entry. Published papers use final journal records, including
print year, volume, issue and pages; chapters cite the published book. Working
papers retain their report number and any revision or conditional acceptance note.
When a paper is published, update its citation here as well as its visible entry.
Do not use temporary Google Scholar export URLs.

`python scripts/build_site.py` generates stable `docs/citations/*.bib` downloads
and matching expandable citations on Research, the homepage and paper detail pages.
Each citation provides selectable text, a Copy button and a Download .bib link;
the text and download remain available without JavaScript. The build
needs no external API. `python -m unittest discover -s scripts/tests` checks
coverage, download targets, final-version examples and link ordering.
