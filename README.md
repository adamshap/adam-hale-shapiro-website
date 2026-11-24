# Adam Hale Shapiro's website

Independent static copy of the public Wix website, prepared for GitHub Pages.
The publishable website is in `docs/`. No paid hosting or build tools are required.

## Edit the website

- Home: `docs/index.html`
- Research: `docs/research/index.html`
- Economic Letters: `docs/blank-1/index.html`
- Code & Data: `docs/blank-2/index.html`
- Individual paper pages retain their existing paths in `docs/`.
- Shared appearance: `docs/assets/style.css`

Edit the HTML in GitHub and commit the change. GitHub Pages publishes from the
`main` branch's `/docs` folder.

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
