"""Check the site's local references and public HTTP(S) links without credentials."""
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import json
import argparse
import time
from build_site import Tree, text

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://adam-hale-shapiro.com/'

def check_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; WebsiteLinkCheck/1.0)'}
    result = {'url': url}
    # Confirm a missing URL with GET, twice. HEAD failures and paywalls alone
    # are not evidence that a reader-facing link is broken.
    missing = 0
    for method in ('HEAD', 'GET', 'GET'):
        try:
            request = Request(url, headers=headers, method=method)
            with urlopen(request, timeout=15) as response:
                result.update(status=response.status, final_url=response.url,
                              content_type=response.headers.get('Content-Type', ''))
                if method == 'GET':
                    sample = response.read(1024)
                    if urlsplit(url).path.lower().endswith('.pdf') and not sample.startswith(b'%PDF'):
                        result['note'] = 'PDF link returns a non-PDF response'
                final = urlsplit(response.url)
                result['result'] = 'unverified' if final.hostname == 'accounts.google.com' else 'ok'
                if result['result'] == 'unverified':
                    result['note'] = 'Redirected to Google sign-in; file access needs manual review'
                return result
        except HTTPError as error:
            result.update(status=error.code, final_url=error.url)
            if method == 'HEAD':
                continue
            if error.code in (401, 403, 429, 999):
                result['result'] = 'blocked'
                return result
            if error.code in (404, 410):
                missing += 1
                if missing == 2:
                    result['result'] = 'broken'
                    return result
            else:
                result['result'] = 'unverified'
            time.sleep(1)
        except (URLError, TimeoutError, OSError) as error:
            result['error'] = str(error)
            if method == 'HEAD':
                continue
            result['result'] = 'unverified'
            time.sleep(1)
    result['result'] = 'unverified'
    return result

def collect_references(site):
    site = site.resolve()
    local_errors, remote, references = [], {}, 0
    for path in site.rglob('*.html'):
        route = path.relative_to(site).as_posix().removesuffix('index.html')
        tree = Tree(path.read_text(encoding='utf-8')).root
        for node in tree.walk():
            attributes = ['href', 'src']
            if node.tag == 'meta' and (node.attrs.get('property') in ('og:image', 'og:image:secure_url') or node.attrs.get('name') == 'twitter:image'):
                attributes.append('content')
            for attribute in attributes:
                raw = node.attrs.get(attribute)
                if not raw:
                    continue
                parsed = urlsplit(raw)
                if parsed.scheme in ('mailto', 'tel', 'data'):
                    continue
                references += 1
                url = urljoin(BASE + route, raw).split('#')[0]
                resolved = urlsplit(url)
                if parsed.scheme and parsed.scheme not in ('http', 'https'):
                    continue
                if resolved.hostname != urlsplit(BASE).hostname:
                    remote.setdefault(url, []).append({'page': route or '/', 'label': text(node)[:120]})
                else:
                    target = (site / unquote(resolved.path).lstrip('/')).resolve()
                    if not target.is_relative_to(site):
                        local_errors.append({'page': route, 'reference': raw, 'error': 'path outside published site'})
                        continue
                    if target.is_dir():
                        target /= 'index.html'
                    if not target.is_file():
                        local_errors.append({'page': route, 'reference': raw, 'error': 'missing file'})
                    elif parsed.fragment and target.suffix == '.html':
                        target_tree = tree if target == path else Tree(target.read_text(encoding='utf-8')).root
                        ids = {n.attrs.get('id') for n in target_tree.walk()}
                        if unquote(parsed.fragment) not in ids:
                            local_errors.append({'page': route, 'reference': raw, 'error': 'missing anchor'})
    return local_errors, remote, references

def markdown_report(report):
    lines = ['# Website link check', '',
             f"Checked {report['references']} references and {report['unique_remote_urls']} unique external URLs.", '']
    failures = report['local_errors'] + [r for r in report['results'] if r['result'] == 'broken']
    lines += ['## Confirmed broken links', '']
    for item in failures:
        if 'url' in item:
            pages = ', '.join(sorted({r['page'] for r in item['used_by']}))
            lines.append(f"- HTTP {item['status']}: {item['url']} (used on {pages})")
        else:
            lines.append(f"- {item['page'] or '/'}: `{item['reference']}` — {item['error']}")
    if not failures:
        lines.append('None found.')
    manual = [r for r in report['results'] if r['result'] in ('blocked', 'unverified') or r.get('note')]
    lines += ['', '## Automated verification limits', '',
              f'{len(manual)} URLs need manual verification (paywalls, bot protection, temporary errors, or unexpected responses).',
              'These are listed in the JSON artifact and are not reported as confirmed broken links.', '']
    return '\n'.join(lines)

def audit(output, local_only=False):
    local_errors, remote, references = collect_references(ROOT / 'docs')
    print('Checking', 0 if local_only else len(remote), 'unique remote URLs and', references, 'total references', flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(check_url, url): url for url in remote} if not local_only else {}
        for future in as_completed(futures):
            result = future.result()
            result['used_by'] = remote[result['url']]
            results.append(result)
            if result['result'] != 'ok' or result.get('note'):
                print(json.dumps({k:v for k,v in result.items() if k != 'used_by'}), flush=True)
    report = {'references': references, 'unique_remote_urls': len(remote), 'local_only': local_only,
              'local_errors': local_errors, 'summary': dict(Counter(r['result'] for r in results)),
              'results': sorted(results, key=lambda r: r['url'])}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    output.with_suffix('.md').write_text(markdown_report(report), encoding='utf-8')
    print(json.dumps({'local_errors': local_errors, 'summary': report['summary']}), flush=True)
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--fail-on-broken', action='store_true')
    args = parser.parse_args()
    report = audit(args.output, args.local_only)
    if args.fail_on_broken and (report['local_errors'] or report['summary'].get('broken')):
        raise SystemExit(1)
