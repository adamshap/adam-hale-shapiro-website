"""Render the static website from content/site.json. Standard library only."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import json
import posixpath
import re
import hashlib

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'source', 'wbr'}
CV = 'https://www.frbsf.org/wp-content/uploads/CV-Shapiro.pdf'
EMAIL = 'mailto:adam.shapiro@sf.frb.org'

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
    def find(self, tag):
        return next((n for n in self.walk() if n.tag == tag), None)

class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node('root')
        self.feed(source)
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
    def handle_data(self, value):
        self.current.children.append(value)

def text(value):
    value = value.text() if isinstance(value, Node) else value
    return re.sub(r'\s+', ' ', value.replace('\u200b', '')).strip()

def local_path(href, source):
    if urlsplit(href).scheme or href.startswith('//'):
        return href
    return urljoin('https://local.test' + source.rstrip('/') + '/', href).replace('https://local.test', '')

def relative(href, destination):
    if not href.startswith('/') or href.startswith('//'):
        return href
    parts = urlsplit(href)
    value = posixpath.relpath(parts.path or '/', destination.rstrip('/') or '/')
    if parts.path.endswith('/'):
        value += '/' if not value.endswith('/') else ''
    return value + ('?' + parts.query if parts.query else '') + ('#' + parts.fragment if parts.fragment else '')

def serialize(node, source='/', destination='/', tidy=False):
    if isinstance(node, str):
        return escape(re.sub(r'\s+', ' ', node) if tidy else node)
    inside = ''.join(serialize(c, source, destination, tidy) for c in node.children)
    if node.tag == 'root':
        return inside
    if node.tag == 'a' and not text(node).strip('"“” '):
        return ''
    attrs = ''
    for key, value in node.attrs.items():
        if key in ('href', 'src'):
            value = relative(local_path(value, source), destination)
        attrs += ' ' + key + '="' + escape(value or '', quote=True) + '"'
    return '<' + node.tag + attrs + '>' + ('' if node.tag in VOID else inside + '</' + node.tag + '>')

def inner(node, source='/', destination='/'):
    return ''.join(serialize(c, source, destination, True) for c in node.children).strip()

def fragment(source):
    root = Tree(source).root
    children = [n for n in root.children if isinstance(n, Node)]
    return children[0] if len(children) == 1 and children[0].tag == 'section' else root

def anchor(href, label, slug='/', css=''):
    return '<a' + (' class="' + css + '"' if css else '') + ' href="' + escape(relative(href, slug), quote=True) + '">' + escape(label) + '</a>'

def asset_href(path, slug):
    version = hashlib.sha256((DOCS / path.lstrip('/')).read_bytes()).hexdigest()[:10]
    return relative(path, slug) + '?v=' + version

def resources(nodes, source, destination):
    links = []
    for n in nodes:
        a = n.find('a')
        if a and text(a):
            links.append(anchor(local_path(a.attrs['href'], source), text(a), destination, 'resource-link'))
    return '<div class="resource-links">' + ''.join(links) + '</div>' if links else ''

def paper(block, slug='/research', destination=None):
    destination = destination or slug
    paras = [n for n in block.children if isinstance(n, Node) and n.tag == 'p']
    if not paras:
        return ''
    first, *rest = paras
    resource_nodes = [n for n in rest if 'resource' in n.attrs.get('class', '').split()]
    detail_nodes = [n for n in rest if n not in resource_nodes]
    first_link = next((n for n in first.walk() if n.tag == 'a' and text(n).strip('"“” ')), None)
    title = text(first_link or first).strip('"“” ')
    title_html = anchor(local_path(first_link.attrs['href'], slug), title, destination) if first_link else escape(title)
    tail = ''.join(serialize(c, slug, destination, True) for c in first.children if c is not first_link).strip(' \xa0')
    # Paper titles occasionally share a paragraph with their coauthors.
    details = ('<p>' + tail + '</p>' if tail else '') + ''.join('<p>' + inner(n, slug, destination) + '</p>' for n in detail_nodes)
    search = escape(text(block), quote=True)
    return '<article class="paper" data-search-item data-search="' + search + '"><h3>' + title_html + '</h3><div class="paper-details">' + details + '</div>' + resources(resource_nodes, slug, destination) + '</article>'

def navigation(slug):
    items = [('/', 'Home'), ('/research/', 'Research'), ('/blank-1/', 'Economic Letters'), ('/blank-2/', 'Code & Data')]
    active = slug if slug in ('/', '/research', '/blank-1', '/blank-2') else '/research'
    links = ''
    for url, label in items:
        selected = active.rstrip('/') == url.rstrip('/')
        links += '<a' + (' aria-current="page"' if selected and active == slug else ' aria-current="true"' if selected else '') + ' href="' + relative(url, slug) + '">' + label + '</a>'
    return '''<header class="site-header"><div class="header-inner">''' + anchor('/', 'Adam Hale Shapiro', slug, 'brand') + '''<button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav"><span>Menu</span><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M3 6h14M3 10h14M3 14h14"/></svg></button><nav id="site-nav" aria-label="Main navigation">''' + links + anchor(CV, 'CV', slug, 'nav-cv') + '</nav></div></header>'

def footer(slug):
    return '''<footer class="site-footer"><div class="footer-top"><div>''' + anchor('/', 'Adam Hale Shapiro', slug, 'footer-name') + '''<p>Federal Reserve Bank of San Francisco</p></div><div class="footer-contact">''' + anchor(EMAIL, 'adam.shapiro@sf.frb.org', slug) + '''<p>101 Market Street · San Francisco, CA 94105</p></div></div><p class="disclaimer">The content on this website does not represent the views of the Federal Reserve Bank of San Francisco (FRBSF) or the Federal Reserve System. <a href="https://www.frbsf.org/contact-us/">Contact the FRBSF</a> for all media inquiries.</p><div class="footer-bottom"><span>© 2026 Adam Hale Shapiro</span><a href="#top">Back to top</a></div></footer>'''

def page(slug, title, body, description=None):
    description = description or 'Research, publications, economic letters, code and data from economist Adam Hale Shapiro.'
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#6a2036"><title>''' + escape(title) + '''</title><meta name="description" content="''' + escape(description, quote=True) + '''"><link rel="icon" href="''' + asset_href('/assets/favicon.svg', slug) + '''" type="image/svg+xml"><link rel="stylesheet" href="''' + asset_href('/assets/style.css', slug) + '''"><script defer src="''' + asset_href('/assets/site.js', slug) + '''"></script></head><body id="top"><a class="skip-link" href="#content">Skip to content</a>''' + navigation(slug) + body + footer(slug) + '</body></html>\n'

def section_heading(eyebrow, title, intro=''):
    return '<div class="page-heading"><p class="eyebrow">' + escape(eyebrow) + '</p><h1>' + escape(title) + '</h1>' + ('<p class="page-intro">' + escape(intro) + '</p>' if intro else '') + '</div>'

def tool_feature(name, href, description, slug='/'):
    return '<article class="tool-feature"><p class="eyebrow">Interactive dashboard</p><h3>' + anchor(href, name, slug) + '</h3><p>' + escape(description) + '</p>' + anchor(href, 'Open dashboard', slug, 'text-link') + '</article>'

def home(pages):
    slug = '/'
    tree = Tree(pages[slug]['blocks'][0]).root
    paras = [n for n in tree.walk() if n.tag == 'p']
    bio = inner(paras[0])
    # Keep the original biography wording; break it into readable paragraphs.
    bio = bio.replace('. I study', '.</p><p>I study')
    profile_links = [n.find('a') for n in paras[1:] if n.find('a') and 'media inquiries' not in text(n)]
    social = ''.join(anchor(a.attrs['href'], text(a), css='profile-link') for a in profile_links if text(a) not in ('CV', 'Email'))
    hero = '''<section class="hero"><div class="hero-copy"><p class="eyebrow">Economist</p><h1>Adam Hale<br>Shapiro<span class="accent-period">.</span></h1><div class="bio"><p>''' + bio + '''</p></div><div class="hero-actions">''' + anchor('/research/', 'Explore research', css='button button-primary') + anchor(CV, 'Curriculum vitae', css='button button-secondary') + '''</div><div class="profile-links">''' + social + '''</div></div><figure class="hero-visual"><img src="assets/forest.jpg" alt="Sunlight falling on snow-covered trees" width="900" height="1100" fetchpriority="high"><figcaption>Applied micro · Macroeconomics · Health economics</figcaption></figure></section>'''
    tools = '<section class="home-section"><div class="section-header"><div><p class="eyebrow">Code & Data</p><h2>Explore the data.</h2></div>' + anchor('/blank-2/', 'All code & data', css='text-link') + '</div><div class="tools-grid">' + tool_feature('Inflation Shock Momentum', 'https://adamshap.github.io/ismi-webapp/ism_webapp.html', 'Explore sustained movements in inflation shocks.') + tool_feature('Supply & Demand Driven Inflation', 'https://adamshap.github.io/supply-demand-webapp/supply_demand_webapp.html', 'Explore the supply and demand components of inflation.') + '</div></section>'
    blocks = [fragment(b) for b in pages['/research']['blocks']]
    selected = [b for b in blocks if b.find('p')][:2]
    research = '<section class="home-section"><div class="section-header"><div><p class="eyebrow">Working papers</p><h2>Recent research.</h2></div>' + anchor('/research/', 'All research', css='text-link') + '</div><div class="featured-papers">' + ''.join(paper(b, destination='/') for b in selected) + '</div></section>'
    return page(slug, 'Adam Hale Shapiro | Economist', '<main id="content" class="home-main">' + hero + tools + research + '</main>')

def search_field(label, count):
    return '<div class="search-toolbar"><label class="search-box"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><span class="sr-only">' + escape(label) + '</span><input type="search" data-search-input placeholder="' + escape(label) + '" autocomplete="off"></label><p class="search-status" data-search-status aria-live="polite">' + str(count) + ' results</p></div><div class="empty-results" data-empty-results hidden><h3>No matching results</h3><p>Try a title, coauthor, journal, or year.</p><button type="button" class="button button-secondary" data-clear-search>Clear search</button></div>'

def research(data):
    slug = '/research'
    groups = []
    for value in data['blocks']:
        block = fragment(value)
        if block.find('h2'):
            groups.append([text(block.find('h2')), []])
        elif block.find('p'):
            groups[-1][1].append(block)
    sidebar = '<aside class="section-sidebar"><p class="eyebrow">On this page</p><a href="#working-papers">Working papers</a><a href="#publications">Publications</a>' + anchor(CV, 'Curriculum vitae') + '</aside>'
    count = sum(len(items) for _, items in groups)
    content = search_field('Search research', count)
    for index, (title, blocks) in enumerate(groups):
        section_id = 'working-papers' if index == 0 else 'publications'
        content += '<section class="research-group" id="' + section_id + '" data-search-group><div class="group-heading"><h2>' + escape(title) + '</h2><span>' + str(len(blocks)) + '</span></div>' + ''.join(paper(block) for block in blocks) + '</section>'
    return page(slug, 'Research | Adam Hale Shapiro', '<main id="content" class="page-main">' + section_heading('Research', 'Papers & publications', 'Research on inflation, price setting dynamics, and the U.S. healthcare sector.') + '<div class="research-layout">' + sidebar + '<div>' + content + '</div></div></main>')

def letters(data):
    slug = '/blank-1'
    tree = Tree(''.join(data['blocks'])).root
    groups = []
    for p in [n for n in tree.walk() if n.tag == 'p']:
        if p.find('a'):
            groups.append([p])
        elif groups:
            groups[-1].append(p)
    articles = ''
    for nodes in groups:
        block = Node('root')
        block.children = nodes
        articles += paper(block, slug)
    return page(slug, 'Economic Letters | Adam Hale Shapiro', '<main id="content" class="page-main letters-main">' + section_heading('San Francisco Fed', 'Economic Letters', 'Economic analysis and research for a broader audience.') + search_field('Search economic letters', len(groups)) + '<div class="letter-list">' + articles + '</div></main>')

def code_data(data):
    slug = '/blank-2'
    tree = Tree(''.join(data['blocks'])).root
    groups = []
    for p in [n for n in tree.walk() if n.tag == 'p']:
        a = next((n for n in p.walk() if n.tag == 'a' and text(n)), None)
        start = a and ('Dashboard' in text(a) or any(x in text(a) for x in ('Cyclical and Acyclical', 'Covid Sensitive', 'Daily News Sentiment')))
        if start:
            groups.append([])
        if groups:
            groups[-1].append(p)
    items = ''
    for i, nodes in enumerate(groups):
        first = nodes[0]
        a = next(n for n in first.walk() if n.tag == 'a' and text(n))
        title = text(a).replace('Dashboard', '').replace('(.xlsx)', '').strip()
        link = anchor(local_path(a.attrs['href'], slug), 'Open dashboard' if i < 2 else 'Download data', slug, 'button button-primary' if i < 2 else 'resource-link')
        details = ''.join('<p>' + inner(n, slug, slug).strip() + '</p>' for n in nodes[1:])
        details = details.replace('documentation:', 'Documentation:').replace('excel file (.xlsx)', 'Excel data (.xlsx)')
        items += '<article class="data-item' + (' dashboard-item' if i < 2 else '') + '"><div><p class="eyebrow">' + ('Interactive dashboard' if i < 2 else 'Data & replication') + '</p><h2>' + escape(title) + '</h2></div><div class="data-details">' + details + '<div class="data-primary">' + link + '</div></div></article>'
    return page(slug, 'Code & Data | Adam Hale Shapiro', '<main id="content" class="page-main">' + section_heading('Open research', 'Code & data', 'Interactive dashboards, data series, and replication code.') + '<div class="data-list">' + items + '</div></main>')

def detail(slug, data):
    blocks = [fragment(b) for b in data['blocks']]
    title = data['title']
    if blocks and blocks[0].find('h2') and text(blocks[0].find('h2')) != 'Abstract':
        title = text(blocks.pop(0).find('h2'))
    abstract_at = next((i for i, b in enumerate(blocks) if b.find('h2') and text(b.find('h2')) == 'Abstract'), len(blocks))
    meta = ''.join(inner(b, slug, slug) for b in blocks[:abstract_at])
    # Keep downloads together, separate from bibliographic information.
    meta_tree = Tree(meta).root
    links = [n for n in meta_tree.walk() if n.tag == 'p' and 'resource' in n.attrs.get('class', '')]
    meta_paras = [n for n in meta_tree.children if isinstance(n, Node) and n not in links]
    header = '<div class="paper-header"><p class="eyebrow">Research</p><h1>' + escape(title.strip('" ')) + '</h1><div class="paper-byline">' + ''.join(serialize(n, slug, slug, True) for n in meta_paras) + '</div>' + resources(links, slug, slug) + '</div>'
    body = ''.join('<section class="prose">' + inner(b, slug, slug) + '</section>' for b in blocks[abstract_at:])
    return page(slug, title + ' | Adam Hale Shapiro', '<main id="content" class="page-main paper-main"><div class="breadcrumb">' + anchor('/research/', 'All research', slug) + '</div>' + header + '<div class="abstract-body">' + body + '</div><div class="paper-return">' + anchor('/research/', 'Browse all research', slug, 'button button-secondary') + '</div></main>')

def build():
    pages = json.loads((ROOT / 'content/site.json').read_text(encoding='utf-8'))
    for slug, data in pages.items():
        if slug == '/':
            output = home(pages)
        elif slug == '/research':
            output = research(data)
        elif slug == '/blank-1':
            output = letters(data)
        elif slug == '/blank-2':
            output = code_data(data)
        else:
            output = detail(slug, data)
        path = DOCS / (slug.strip('/') + '/index.html' if slug != '/' else 'index.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding='utf-8', newline='\n')
    print('Built', len(pages), 'pages')

if __name__ == '__main__':
    build()
