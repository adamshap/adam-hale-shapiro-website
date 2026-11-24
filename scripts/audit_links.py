"""Check the site's local references and public HTTP(S) links without credentials."""
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import json
import argparse
from build_site import Tree, text

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://adam-hale-shapiro.com/'

def check_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; WebsiteLinkCheck/1.0)'}
    result = {'url': url}
    for method in ('HEAD', 'GET'):
        try:
            request = Request(url, headers=headers, method=method)
            with urlopen(request, timeout=22) as response:
                result.update(status=response.status, final_url=response.url,
                              content_type=response.headers.get('Content-Type', ''))
                if method == 'GET':
                    sample = response.read(1024)
                    if urlsplit(url).path.lower().endswith('.pdf') and not sample.startswith(b'%PDF'):
                        result['note'] = 'PDF link returns a non-PDF response'
                result['result'] = 'ok'
                return result
        except HTTPError as error:
            result.update(status=error.code, final_url=error.url)
            if method == 'HEAD':
                continue
            result['result'] = 'blocked' if error.code in (401, 403, 429, 999) else 'broken'
            return result
        except (URLError, TimeoutError, OSError) as error:
            result['error'] = str(error)
            if method == 'HEAD':
                continue
            result['result'] = 'unverified'
            return result
    return result

def audit(output):
    site = ROOT / 'docs'
    local_errors, remote, references = [], {}, 0
    for path in site.rglob('*.html'):
        route = path.relative_to(site).as_posix().removesuffix('index.html')
        tree = Tree(path.read_text(encoding='utf-8')).root
        for node in tree.walk():
            for attribute in ('href', 'src'):
                raw = node.attrs.get(attribute)
                if not raw:
                    continue
                parsed = urlsplit(raw)
                if parsed.scheme in ('mailto', 'tel', 'data'):
                    continue
                references += 1
                if parsed.scheme in ('http', 'https') or parsed.netloc:
                    url = urljoin(BASE + route, raw).split('#')[0]
                    remote.setdefault(url, []).append({'page': route or '/', 'label': text(node)[:120]})
                else:
                    target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
                    if target.is_dir():
                        target /= 'index.html'
                    if not target.is_file():
                        local_errors.append({'page': route, 'reference': raw, 'error': 'missing file'})
                    elif parsed.fragment and target.suffix == '.html':
                        target_tree = tree if target == path else Tree(target.read_text(encoding='utf-8')).root
                        ids = {n.attrs.get('id') for n in target_tree.walk()}
                        if unquote(parsed.fragment) not in ids:
                            local_errors.append({'page': route, 'reference': raw, 'error': 'missing anchor'})
    print('Checking', len(remote), 'unique remote URLs and', references, 'total references', flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(check_url, url): url for url in remote}
        for future in as_completed(futures):
            result = future.result()
            result['used_by'] = remote[result['url']]
            results.append(result)
            if result['result'] != 'ok' or result.get('note'):
                print(json.dumps({k:v for k,v in result.items() if k != 'used_by'}), flush=True)
    report = {'references': references, 'unique_remote_urls': len(remote),
              'local_errors': local_errors, 'summary': dict(Counter(r['result'] for r in results)),
              'results': sorted(results, key=lambda r: r['url'])}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'local_errors': local_errors, 'summary': report['summary']}), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    audit(parser.parse_args().output)
