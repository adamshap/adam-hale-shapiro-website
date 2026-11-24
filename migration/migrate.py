"""Archive the public Wix content and create an independent GitHub Pages site.

Run before handoff only. After handoff, edit the static HTML directly.
Uses Python's standard library; nothing from Wix runs on the new website.
"""
from html.parser import HTMLParser
from html import escape
from urllib.parse import urlsplit, urljoin, unquote
from urllib.request import urlopen, Request
from pathlib import Path
import hashlib
import json
import re
import posixpath

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'migration/source'
DIST = ROOT / 'docs'
DOMAIN = 'https://www.adam-hale-shapiro.com'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()
    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node('root')
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent
    def handle_data(self, data):
        self.current.children.append(data)

def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=45) as response:
        return response.read()

def route(url):
    parts = urlsplit(urljoin(DOMAIN, url))
    if parts.hostname not in ('www.adam-hale-shapiro.com', 'adam-hale-shapiro.com'):
        return None
    return unquote(parts.path).rstrip('/') or '/'

def path_for(slug):
    return DIST / (slug.lstrip('/') + '/index.html' if slug != '/' else 'index.html')

SOURCE.mkdir(parents=True, exist_ok=True)
DIST.mkdir(parents=True, exist_ok=True)
pages, failures = {}, []
pending = ['/', '/research', '/blank-1', '/blank-2']
aliases = {'/': 'home', '/research': 'research', '/blank-1': 'letters', '/blank-2': 'data'}
while pending:
    slug = pending.pop(0)
    if slug in pages:
        continue
    source_path = SOURCE / (aliases.get(slug, slug.strip('/').replace('/', '--')) + '.html')
    try:
        raw = source_path.read_bytes() if source_path.exists() else fetch(DOMAIN + slug)
        source_path.write_bytes(raw)
        tree = Tree(raw.decode('utf-8')).root
        main = next((n for n in tree.walk() if n.tag == 'main'), None)
        if main is None:
            raise ValueError('No main element')
        pages[slug] = {'tree': tree, 'main': main, 'raw': raw}
        for node in main.walk():
            if node.tag == 'a' and node.attrs.get('data-anchor') != 'SCROLL_TO_TOP':
                target = route(node.attrs.get('href', ''))
                if target and target not in pages and target not in pending and '.' not in target.split('/')[-1]:
                    pending.append(target)
        print('Captured', slug, flush=True)
    except Exception as error:
        failures.append({'path': slug, 'error': str(error)})

assets = {}
def asset(url):
    if url in assets:
        return assets[url]
    host = urlsplit(url).hostname or ''
    owned_file = host in ('www.adam-hale-shapiro.com', 'adam-hale-shapiro.com') and urlsplit(url).path.startswith('/_files/')
    if host not in ('static.wixstatic.com', 'static.wix.com') and not owned_file:
        return url
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in ('.pdf', '.zip', '.xlsx', '.xls', '.docx', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.ico'):
        suffix = '.bin'
    filename = hashlib.sha256(url.encode()).hexdigest()[:18] + suffix
    local_url = urlsplit(url).path if owned_file else '/assets/' + filename
    destination = DIST / local_url.lstrip('/')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not destination.exists():
            destination.write_bytes(fetch(url))
        assets[url] = local_url
        return assets[url]
    except Exception as error:
        failures.append({'asset': url, 'error': str(error)})
        return url

def clean(node):
    if isinstance(node, str):
        return escape(node.replace('\u200b', '').replace('\ufeff', ''))
    inside = ''.join(clean(child) for child in node.children)
    if node.tag == 'a':
        href = node.attrs.get('href', '')
        target = route(href)
        if node.attrs.get('data-anchor') == 'SCROLL_TO_TOP':
            href = '#top'
        elif target in pages:
            href = target + ('/' if target != '/' else '') + (('#' + urlsplit(href).fragment) if urlsplit(href).fragment else '')
        else:
            href = asset(href)
        return '<a href="' + escape(href, quote=True) + '">' + inside + '</a>'
    if node.tag == 'br':
        return '<br>'
    if node.tag in ('p', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'em', 'strong', 'sup', 'sub'):
        if not node.text().strip(' \n\t\xa0\u200b'):
            return ''
        return '<' + node.tag + '>' + inside + '</' + node.tag + '>'
    return inside

home = pages['/']['tree']
cv = next((n.attrs['href'] for n in home.walk() if n.tag == 'a' and n.text().strip() == 'CV'), '#')
banner = next((n.attrs.get('src') for n in home.walk() if n.tag == 'img' and n.attrs.get('alt') == 'Snowy Trees'), None)
banner_path = asset(banner.split('/v1/')[0]) if banner else None
titles = {'/': 'Home', '/research': 'Research', '/blank-1': 'Economic Letters', '/blank-2': 'Code & Data'}
navigation = [('/', 'Home'), ('/research', 'Research'), ('/blank-1', 'Economic Letters'), ('/blank-2', 'Code & Data')]
manifest = []
for slug, page in pages.items():
    def in_rich_text(node):
        parent = node.parent
        while parent:
            if parent.attrs.get('data-testid') == 'richTextElement':
                return True
            parent = parent.parent
        return False
    blocks = [n for n in page['main'].walk() if n.attrs.get('data-testid') == 'richTextElement' or (n.tag == 'a' and n.attrs.get('href') and not in_rich_text(n))]
    title_node = next((n for n in page['tree'].walk() if n.tag == 'title'), None)
    title = titles.get(slug, title_node.text().split('|')[0].strip() if title_node else 'Research')
    nav = ''.join('<a ' + ('aria-current="page" ' if slug == url else '') + 'href="' + (url + '/' if url != '/' else '/') + '">' + label + '</a>' for url, label in navigation)
    sections = []
    for block in blocks:
        if not block.text().strip(' \n\t\xa0\u200b'):
            continue
        if block.tag == 'a':
            link = '<p class="resource">' + clean(block) + '</p>'
            if sections:
                sections[-1] += link
            else:
                sections.append(link)
        else:
            sections.append(''.join(clean(c) for c in block.children))
    if slug not in titles and sections and re.sub('<[^>]+>', '', sections[0]).strip() == title:
        sections.pop(0)
    content = ''.join('<section class="content-block">' + section + '</section>' for section in sections)
    image = '<img class="banner" src="' + banner_path + '" alt="Snowy trees" width="1600" height="400">' if banner_path else ''
    heading = '<p class="eyebrow">Economist</p><h1>Adam Hale Shapiro</h1>' if slug == '/' else '<h1>' + escape(title) + '</h1>'
    html = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(('Adam Hale Shapiro | Economist' if slug == '/' else title + ' | Adam Hale Shapiro')) + '</title><meta name="description" content="Research, publications, economic letters, code and data from economist Adam Hale Shapiro."><link rel="stylesheet" href="/assets/style.css"></head><body id="top"><a class="skip" href="#content">Skip to content</a><header><a class="brand" href="/">Adam Hale Shapiro</a><nav aria-label="Main navigation">' + nav + '<a href="' + escape(cv, quote=True) + '">CV</a></nav></header>' + (image if slug == '/' else '') + '<main id="content" class="' + ('home' if slug == '/' else 'listing') + '">' + heading + content + '</main><footer><p>The content on this website does not represent the views of the Federal Reserve Bank of San Francisco (FRBSF) or the Federal Reserve System. <a href="https://www.frbsf.org/news-and-media/">Contact the FRBSF</a> for all media inquiries.</p><div><span>© 2026 Adam Hale Shapiro</span><a href="#top">Back to top</a></div></footer></body></html>\n'
    output = path_for(slug)
    # Relative links work both at a github.io project URL and at the custom domain.
    directory = slug.lstrip('/') or '.'
    def relative_link(match):
        attribute, url = match.group(1), match.group(2)
        path, mark, fragment = url.partition('#')
        relative = posixpath.relpath(path or '/', '/' + directory)
        if path.endswith('/') and not relative.endswith('/'):
            relative += '/'
        return attribute + '="' + relative + (mark + fragment if mark else '') + '"'
    html = re.sub(r'(href|src)="(/[^\"]*)"', relative_link, html)
    if slug == '/':
        html = re.sub(r'(<footer>)<p>.*?</p>', r'\1', html)
    html = html.replace('https://www.frbsf.org/news-and-media/', 'https://www.frbsf.org/contact-us/')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8', newline='\n')
    links = [n.attrs.get('href') for n in page['main'].walk() if n.tag == 'a']
    manifest.append({'path': slug, 'title': title, 'blocks': len(blocks), 'links': len(links), 'source_sha256': hashlib.sha256(page['raw']).hexdigest()})

(ROOT / 'migration/inventory.json').write_text(json.dumps({'pages': manifest, 'downloaded_assets': assets, 'failures': failures}, indent=2), encoding='utf-8')
print(json.dumps({'pages': len(pages), 'assets': len(assets), 'failures': failures}, indent=2))
