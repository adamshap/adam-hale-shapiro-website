"""Render the static website from content/site.json. Standard library only."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import json
import posixpath
import re
import hashlib
from citations import bibtex, load_citations, normalized_title, write_citations
from paper_data import load_site, load_papers, research_assets

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'source', 'wbr'}
CV = 'https://www.frbsf.org/wp-content/uploads/CV-Shapiro.pdf'
GOATCOUNTER = 'https://adam-hale-shapiro.goatcounter.com/count'
SITE_URL = 'https://adam-hale-shapiro.com'
CITATIONS = load_citations()
CITATIONS_BY_TITLE = {normalized_title(e['match_title']): e for e in CITATIONS}
CITATIONS_BY_PATH = {e['paper_path']: e for e in CITATIONS if e['paper_path']}

def citation_link(title, destination, paper_path=None):
    entry = CITATIONS_BY_PATH.get(paper_path) or CITATIONS_BY_TITLE.get(normalized_title(title))
    if not entry:
        return ''
    filename = entry['id'] + '.bib'
    href = relative('/citations/' + filename, destination)
    label = escape(entry['match_title'], quote=True)
    download = '<a class="resource-link" href="' + escape(href, quote=True) + '" download="' + filename + '" aria-label="Download .bib for ' + label + '">Download .bib</a>'
    return ('<details class="paper-citation"><summary>BibTeX<span class="sr-only"> for ' + escape(entry['match_title']) + '</span></summary>'
            '<div class="citation-panel"><textarea readonly rows="8" spellcheck="false" aria-label="BibTeX citation for ' + escape(entry['match_title'], quote=True) + '">' + escape(bibtex(entry)) + '</textarea>'
            '<div class="citation-actions"><button type="button" data-copy-citation aria-label="Copy BibTeX for ' + label + '" hidden>Copy</button>' + download + '<span class="citation-status" role="status" aria-live="polite"></span></div></div></details>')

def sharing_metadata(slug, title, description):
    url = SITE_URL + ('/' if slug == '/' else '/' + slug.strip('/') + '/')
    image = SITE_URL + '/assets/social-preview.jpg?v=' + hashlib.sha256(
        (DOCS / 'assets/social-preview.jpg').read_bytes()).hexdigest()[:10]
    tags = [('og:type', 'website'), ('og:site_name', 'Adam Hale Shapiro'),
            ('og:title', title), ('og:description', description), ('og:url', url),
            ('og:image', image), ('og:image:secure_url', image),
            ('og:image:type', 'image/jpeg'), ('og:image:width', '1200'),
            ('og:image:height', '630'),
            ('og:image:alt', 'Adam Hale Shapiro — Research, Economic Letters, Code & Data; snow-covered trees')]
    result = '<link rel="canonical" href="' + escape(url, quote=True) + '">'
    result += ''.join('<meta property="' + key + '" content="' + escape(value, quote=True) + '">' for key, value in tags)
    result += ''.join('<meta name="' + key + '" content="' + escape(value, quote=True) + '">' for key, value in
                      [('twitter:card', 'summary_large_image'), ('twitter:title', title),
                       ('twitter:description', description), ('twitter:image', image),
                       ('twitter:image:alt', tags[-1][1])])
    return result

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
    inside = ''.join(serialize(c, source, destination, tidy and node.tag not in ('textarea', 'pre', 'code')) for c in node.children)
    if node.tag == 'root':
        return inside
    if node.tag == 'a' and not text(node).strip('"“” ') and not node.find('img'):
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
            css = 'resource-link primary-resource' if 'pdf' in text(a).lower() else 'resource-link'
            label = text(a)
            labels = {
                'Interactive Dashboard': 'Dashboard', 'Data Series (.xlxs)': 'Data',
                'Daily News Sentiment Index (.xlxs)': 'Data', 'ISMI Series': 'Data',
                'Economic Letter': 'Letter', 'Data and Code': 'Code & data',
                'Cyclical Inflation Code': 'Cyclical code', 'Covid-Sensitive Inflation Code': 'COVID code',
            }
            links.append(anchor(local_path(a.attrs['href'], source), labels.get(label, label), destination, css))
    return '<div class="resource-links">' + ''.join(links) + '</div>' if links else ''

def bibliography(chunks):
    journals = (
        'Journal of Money', 'International Journal of Central Banking', 'Journal of Monetary Economics',
        'The Quarterly Journal of Economics', 'Quarterly Journal of Economics', 'Review of Economic Studies',
        'Journal of Econometrics', 'Journal of International Economics', 'Review of Economic Dynamics',
        'American Economic Association', 'American Journal of Health Economics', 'Health Affairs',
        'Health Services Research', 'Review of Economics and Statistics', 'Health Economics',
        'Journal of Health Economics', 'Journal of Law', 'International Journal of Industrial Organization',
        'Journal of Industrial Economics', 'Journal of Political Economy',
    )
    pattern = re.compile('|'.join(re.escape(journal) for journal in journals))
    result = []
    standalone_dates = []
    for chunk in chunks:
        if not text(Tree(chunk).root).strip(' .'):
            continue
        chunk = re.sub(r'^with\s*(?=<a\b)', 'with ', chunk)
        chunk = chunk.replace(',,', ',')
        if re.fullmatch(r'[A-Z][a-z]+ 20\d\d\.?', text(Tree(chunk).root)):
            standalone_dates.append(text(Tree(chunk).root).rstrip('.'))
            continue
        chunk = re.sub(r'FRBSF Working Paper\. (20\d\d)\.?', r'FRBSF Working Paper &middot; \1', chunk)
        chunk = re.sub(r'FRBSF Working Paper[. ]*([A-Z][a-z]+),? (20\d\d)', r'FRBSF Working Paper &middot; \1 \2', chunk)
        is_author = text(Tree(chunk).root).startswith('with ')
        if is_author:
            chunk = re.sub(r'\.(\s*(?:</a>)?\s*)$', r'\1', chunk)
        venue = pattern.search(chunk) if is_author else None
        if venue:
            authors = chunk[:venue.start()].rstrip(' .')
            if authors:
                result.append('<p class="paper-authors">' + authors + '</p>')
            result.append('<p class="paper-venue">' + chunk[venue.start():] + '</p>')
        else:
            kind = 'paper-authors' if is_author else 'paper-note' if text(Tree(chunk).root).startswith('Coverage in') else 'paper-venue'
            result.append('<p class="' + kind + '">' + chunk + '</p>')
    if standalone_dates:
        for index in range(len(result) - 1, -1, -1):
            if 'class="paper-venue"' in result[index]:
                result[index] = result[index].removesuffix('</p>').rstrip(' .') + ' &middot; ' + ' &middot; '.join(standalone_dates) + '</p>'
                break
    return ''.join(result)

def media_coverage(nodes, title, source, destination):
    outlets = {
        'ft.com': 'Financial Times', 'wsj.com': 'Wall Street Journal',
        'bloomberg.com': 'Bloomberg', 'reuters.com': 'Reuters',
        'economist.com': 'The Economist', 'latimes.com': 'Los Angeles Times',
        'nytimes.com': 'The New York Times', 'washingtonpost.com': 'The Washington Post',
    }
    groups = {}
    for node in nodes:
        for link in node.walk():
            if link.tag != 'a':
                continue
            host = urlsplit(link.attrs['href']).hostname or ''
            outlet = next((name for domain, name in outlets.items() if host == domain or host.endswith('.' + domain)), text(link))
            groups.setdefault(outlet, []).append(link)
    rows = []
    for outlet, links in groups.items():
        if len(links) == 1:
            links_html = serialize(links[0], source, destination, True)
            # Keep the outlet visible while retaining the article's descriptive label.
            if text(links[0]).lower().removeprefix('the ') != outlet.lower().removeprefix('the '):
                links_html = '<span class="media-outlet">' + escape(outlet) + '</span>' + links_html
        else:
            items = []
            for link in links:
                label = text(link)
                if label.lower().removeprefix('the ') == outlet.lower().removeprefix('the '):
                    year = re.search(r'(?:19|20)\d{2}', link.attrs['href'])
                    label = year.group() if year else 'Article'
                items.append('<li>' + anchor(link.attrs['href'], label, destination) + '</li>')
            links_html = '<span class="media-outlet">' + escape(outlet) + '</span><ul class="media-links">' + ''.join(items) + '</ul>'
        rows.append('<li>' + links_html + '</li>')
    if not rows:
        return ''
    return '<details class="paper-media"><summary>Media coverage<span class="sr-only"> for ' + escape(title) + '</span></summary><ul class="media-outlets">' + ''.join(rows) + '</ul></details>'

def paper(block, slug='/research', destination=None, pages=None):
    destination = destination or slug
    paras = [n for n in block.children if isinstance(n, Node) and n.tag == 'p']
    if not paras:
        return ''
    first, *rest = paras
    resource_nodes = [n for n in rest if 'resource' in n.attrs.get('class', '').split()]
    detail_nodes = [n for n in rest if n not in resource_nodes]
    statuses = [n for n in detail_nodes if text(n).startswith('Conditionally accepted')]
    media_nodes = [n for n in detail_nodes if text(n).startswith('Coverage in')]
    detail_nodes = [n for n in detail_nodes if n not in statuses and n not in media_nodes]
    first_link = next((n for n in first.walk() if n.tag == 'a' and text(n).strip('"“” ')), None)
    title = text(first_link or first).strip('"“” ')
    title_html = anchor(local_path(first_link.attrs['href'], slug), title, destination) if first_link else escape(title)
    tail = ''.join(serialize(c, slug, destination, True) for c in first.children if c is not first_link).strip(' \xa0')
    # Paper titles occasionally share a paragraph with their coauthors.
    details = bibliography(([tail] if tail else []) + [inner(n, slug, destination) for n in detail_nodes])
    status_html = ''.join('<p class="paper-status">' + escape(text(n)) + '</p>' for n in statuses)
    abstract = ''
    if pages and first_link:
        target = urlsplit(local_path(first_link.attrs['href'], slug)).path.rstrip('/')
        entry = pages.get(target)
        if entry:
            abstract_parts, in_abstract = [], False
            for value in entry['blocks']:
                part = fragment(value)
                if part.find('h2'):
                    if text(part.find('h2')) == 'Abstract':
                        in_abstract = True
                        continue
                    if in_abstract:
                        break
                if in_abstract:
                    abstract_parts.append(inner(part, target, destination))
            if abstract_parts:
                abstract = '<details class="paper-abstract"><summary>Abstract<span class="sr-only"> for ' + escape(title) + '</span></summary><div class="paper-abstract-content">' + ''.join(abstract_parts) + '</div></details>'
    resource_html = resources(resource_nodes, slug, destination)
    resource_links = Tree(resource_html).root.find('div') if resource_html else None
    links = resource_links.children if resource_links else []
    for link in links:
        if isinstance(link, Node) and link.tag == 'a':
            link.attrs['aria-label'] = text(link) + ' for ' + title
    resource_actions = ''.join(serialize(n, destination, destination, True) for n in links)
    disclosures = resource_actions + citation_link(title, destination) + abstract + media_coverage(media_nodes, title, slug, destination)
    if disclosures:
        disclosures = '<div class="paper-disclosures">' + disclosures + '</div>'
    return '<article class="paper"><h3>' + title_html + '</h3><div class="paper-details">' + details + '</div>' + status_html + disclosures + '</article>'

def navigation(slug):
    items = [('/', 'Home'), ('/research/', 'Research'), ('/blank-1/', 'Letters'), ('/blank-2/', 'Code & Data')]
    active = slug if slug in ('/', '/research', '/blank-1', '/blank-2') else '/research'
    links = ''
    for url, label in items:
        selected = active.rstrip('/') == url.rstrip('/')
        links += '<a' + (' aria-current="page"' if selected and active == slug else ' aria-current="true"' if selected else '') + ' href="' + relative(url, slug) + '">' + label + '</a>'
    return '''<header class="site-header"><div class="header-inner">''' + anchor('/', 'Adam Hale Shapiro', slug, 'brand') + '''<button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav"><span>Menu</span><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M3 6h14M3 10h14M3 14h14"/></svg></button><nav id="site-nav" aria-label="Main navigation">''' + links + anchor(CV, 'CV', slug, 'nav-cv') + '</nav></div></header>'

def footer(slug):
    affiliation = 'Vice President &middot; Federal Reserve Bank of San Francisco'
    return '''<footer class="site-footer"><div class="footer-top"><div>''' + anchor('/', 'Adam Hale Shapiro', slug, 'footer-name') + '''<p>''' + affiliation + '''</p></div><div class="footer-contact"><button class="email-reveal" type="button" data-reveal-email hidden>Show email</button><noscript><a href="https://www.frbsf.org/our-people/economists/adam-shapiro/">Contact via SF Fed profile</a></noscript><p>101 Market Street · San Francisco, CA 94105</p></div></div><p class="disclaimer">The content on this website does not represent the views of the Federal Reserve Bank of San Francisco (FRBSF) or the Federal Reserve System. <a href="https://www.frbsf.org/contact-us/">Contact the FRBSF</a> for all media inquiries.</p><div class="footer-bottom"><span>© 2026 Adam Hale Shapiro</span><a href="#top">Back to top</a></div></footer>'''

def page(slug, title, body, description=None):
    body = body.replace('<main id="content"', '<main id="content" tabindex="-1"', 1)
    description = description or 'Research papers, publications, Economic Letters, interactive inflation dashboards, code and data from economist Adam Hale Shapiro.'
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#6a2036"><title>''' + escape(title) + '''</title><meta name="description" content="''' + escape(description, quote=True) + '''">''' + sharing_metadata(slug, title, description) + '''<link rel="icon" href="''' + asset_href('/assets/favicon.svg', slug) + '''" type="image/svg+xml"><link rel="stylesheet" href="''' + asset_href('/assets/style.css', slug) + '''"><script defer src="''' + asset_href('/assets/site.js', slug) + '''"></script><script data-goatcounter="''' + GOATCOUNTER + '''" async src="https://gc.zgo.at/count.js"></script></head><body id="top"><a class="skip-link" href="#content">Skip to content</a>''' + navigation(slug) + body + footer(slug) + '</body></html>\n'

def section_heading(title, intro=''):
    return '<div class="page-heading"><h1>' + escape(title) + '</h1>' + ('<p class="page-intro">' + escape(intro) + '</p>' if intro else '') + '</div>'

def tool_feature(name, href, description, preview, slug='/'):
    return '<a class="tool-feature" href="' + escape(relative(href, slug), quote=True) + '"><div class="tool-summary"><h3>' + escape(name) + '</h3><p>' + escape(description) + '</p></div><span class="tool-preview"><img src="' + asset_href('/assets/dashboards/' + preview, slug) + '" alt="" width="968" height="574" loading="lazy" decoding="async"></span></a>'

def home(pages):
    slug = '/'
    tree = Tree(pages[slug]['blocks'][0]).root
    paras = [n for n in tree.walk() if n.tag == 'p']
    profile_links = [n.find('a') for n in paras[1:] if n.find('a') and 'media inquiries' not in text(n)]
    profile_icons = {'Google Scholar': 'google-scholar.svg', 'SF Fed Profile': 'sf-fed.png', 'LinkedIn': 'linkedin.svg'}
    social = ''
    for link in profile_links:
        label = text(link)
        if label in ('CV', 'Email'):
            continue
        icon = profile_icons.get(label)
        image = '<img class="profile-icon' + (' profile-icon-bank' if label == 'SF Fed Profile' else '') + '" src="' + asset_href('/assets/icons/' + icon, slug) + '" width="20" height="20" alt="" aria-hidden="true" decoding="async">' if icon else ''
        compact_label = {'SF Fed Profile': 'SF Fed'}.get(label, label)
        social += '<a class="profile-link" aria-label="' + escape(label, quote=True) + '" href="' + escape(link.attrs['href'], quote=True) + '">' + image + '<span class="profile-label">' + escape(label) + '</span><span class="profile-label-compact" aria-hidden="true">' + escape(compact_label) + '</span></a>'
    banner = '<div class="tree-banner"><img src="assets/forest-banner.jpg" alt="Sunlight falling on snow-covered trees" width="1600" height="440" fetchpriority="high"></div>'
    hero = '''<section class="hero"><div class="hero-copy"><p class="home-introduction">''' + escape(text(paras[0])) + '''</p><div class="hero-tools"><div class="profile-links">''' + social + '''</div></div></div></section>'''
    tools = '<section class="home-section"><div class="section-header"><div><h2>Interactive Dashboards</h2></div>' + anchor('/blank-2/', 'All code & data', css='text-link all-data-link') + '</div><div class="tools-grid">' + tool_feature('Inflation Shock Momentum', 'https://adamshap.github.io/ismi-webapp/ism_webapp.html', 'Explore sustained movements in inflation shocks.', 'ismi.jpg') + tool_feature('Supply & Demand Driven Inflation', 'https://adamshap.github.io/supply-demand-webapp/supply_demand_webapp.html', 'Explore the supply and demand components of inflation.', 'supply-demand.jpg') + '</div></section>'
    blocks = [fragment(b) for b in pages['/research']['blocks']]
    featured = {p['href'] for p in load_papers()['papers'] if p.get('featured')}
    selected = [b for b in blocks if b.find('a') and local_path(b.find('a').attrs['href'], '/research') in featured][:2]
    if not selected:
        selected = [b for b in blocks if b.find('p')][:2]
    figures = research_assets('figure')
    research = '<section class="home-section"><div class="section-header"><div><h2>Recent papers</h2></div>' + anchor('/research/', 'All research', css='text-link all-research-link') + '</div><div class="featured-papers">' + ''.join(illustrated_research(b, None, figures, destination='/') for b in selected) + '</div></section>'
    return page(slug, 'Adam Hale Shapiro | Economist', '<main id="content" class="home-shell"><h1 class="sr-only">Adam Hale Shapiro</h1>' + banner + '<div class="home-main">' + hero + research + tools + '</div></main>')

def figure_image(figure, destination, loading='lazy'):
    width, height = figure['width'], figure['height']
    left, top, right, bottom = figure.get('display_bounds', [0, 0, width, height])
    crop_width, crop_height = right - left, bottom - top
    # Balance visible chart area as well as frame size. Wider/taller charts keep
    # their maximum safe scale; fuller plots get a little optical breathing room.
    # The outer frame and row spacing stay fixed, and all chart labels remain.
    frame_height = 4 / 7
    balanced_scale = (.84 * frame_height / (crop_width * crop_height)) ** .5
    scale = min(1 / crop_width, frame_height / crop_height, balanced_scale)
    framing = {
        'width': width * scale * 100,
        'height': height * scale * 175,
        'left': ((1 - crop_width * scale) / 2 - left * scale) * 100,
        'top': ((frame_height - crop_height * scale) / 2 - top * scale) * 175,
    }
    style = ';'.join('--figure-' + key + ':' + format(value, '.4f') + '%' for key, value in framing.items())
    return Node('img', [('src', asset_href(figure['src'], destination)), ('alt', figure['alt']), ('width', str(width)), ('height', str(height)), ('loading', loading), ('decoding', 'async'), ('style', style)])

def illustrated_research(block, pages, figures, destination='/research', topics=None, show_figure=True):
    article = Tree(paper(block, destination=destination, pages=pages)).root.find('article')
    href = article.find('h3').find('a').attrs['href']
    article.attrs['class'] += ' research-item'
    if topics is not None:
        article.attrs['data-topics'] = ' '.join(topics[local_path(href, destination)])
    if destination == '/' and any('paper-status' in n.attrs.get('class', '').split() for n in article.walk()):
        article.attrs['class'] += ' featured-publication'
    copy = Node('div', [('class', 'research-copy')])
    copy.children = article.children
    article.children = [copy]
    if show_figure:
        figure = figures[local_path(href, destination)]
        preview = Node('a', [('class', 'letter-figure research-figure'), ('href', href), ('aria-label', 'Read ' + figure['title'])])
        preview.children = [figure_image(figure, destination)]
        article.children.append(preview)
    return serialize(article, destination, destination, True)

def topic_strip(tabs):
    return '<div class="topic-strip">' + tabs + '<span class="topic-swipe-cue" aria-hidden="true" hidden><svg width="12" height="16" viewBox="0 0 12 16" fill="none"><path d="m4 4 4 4-4 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span><p class="sr-only" role="status" aria-live="polite" data-filter-status></p></div>'

def research(data, pages):
    slug = '/research'
    groups = []
    for value in data['blocks']:
        block = fragment(value)
        if block.find('h2'):
            groups.append([text(block.find('h2')), []])
        elif block.find('p'):
            groups[-1][1].append(block)
    figures = research_assets('figure')
    topics = research_assets('topics')
    assert set(topics) == set(figures), 'Each research paper needs topic assignments'
    labels = [('all', 'All'), ('inflation', 'Inflation & monetary policy'), ('health', 'Health economics'), ('competition', 'Price setting & competition'), ('finance', 'Banking & finance')]
    tabs = topic_strip('<div class="research-topics" role="group" aria-label="Filter papers by topic">' + ''.join('<button type="button" class="topic-tab" data-topic="' + key + '" aria-pressed="' + ('true' if key == 'all' else 'false') + '" aria-controls="research-results">' + escape(label) + '</button>' for key, label in labels) + '</div>')
    content = ''
    for index, (title, blocks) in enumerate(groups):
        section_id = ['working-papers', 'publications', 'book-chapters', 'older-working-papers'][index]
        content += '<section class="research-group" id="' + section_id + '"><div class="group-heading"><h2>' + escape(title) + '</h2></div>' + ''.join(illustrated_research(block, pages, figures, topics=topics, show_figure=False) for block in blocks) + '</section>'
    return page(slug, 'Research | Adam Hale Shapiro', '<main id="content" class="page-main research-main">' + section_heading('Papers & publications') + tabs + '<div id="research-results" class="research-results">' + content + '</div></main>')

def letters(data):
    slug = '/blank-1'
    tree = Tree(''.join(data['blocks'])).root
    groups = []
    for p in [n for n in tree.walk() if n.tag == 'p']:
        if p.find('a') and not text(p).startswith('Coverage in'):
            groups.append([p])
        elif groups:
            groups[-1].append(p)
    figures = json.loads((ROOT / 'content/letter-figures.json').read_text(encoding='utf-8'))
    topics = json.loads((ROOT / 'content/letter-topics.json').read_text(encoding='utf-8'))
    assert set(topics) == set(figures), 'Each Economic Letter needs topic assignments'
    labels = [('all', 'All'), ('inflation', 'Inflation & monetary policy'), ('housing', 'Housing & wealth'), ('health', 'Health economics'), ('finance', 'Banking & finance'), ('news', 'News & sentiment')]
    tabs = topic_strip('<div class="research-topics" role="group" aria-label="Filter Economic Letters by topic">' + ''.join('<button type="button" class="topic-tab" data-topic="' + key + '" aria-pressed="' + ('true' if key == 'all' else 'false') + '" aria-controls="letter-results">' + escape(label) + '</button>' for key, label in labels) + '</div>')

    articles = ''
    for index, nodes in enumerate(groups):
        block = Node('root')
        block.children = nodes
        article = Tree(paper(block, slug)).root.find('article')
        href = nodes[0].find('a').attrs['href']
        article.attrs['data-topics'] = ' '.join(topics[href])
        figure = figures.get(href)
        if figure:
            article.attrs['class'] += ' letter-item'
            copy = Node('div', [('class', 'letter-copy')])
            disclosures = [n for n in article.children if isinstance(n, Node) and 'paper-disclosures' in n.attrs.get('class', '').split()]
            copy.children = [n for n in article.children if n not in disclosures]
            preview = Node('a', [('class', 'letter-figure'), ('href', href), ('aria-label', 'Read ' + figure['title'])])
            preview.children = [figure_image(figure, slug, 'eager' if index < 2 else 'lazy')]
            article.children = [copy, preview, *disclosures]
        articles += serialize(article, slug, slug, True)
    return page(slug, 'Economic Letters | Adam Hale Shapiro', '<main id="content" class="page-main letters-main">' + section_heading('Economic Letters') + tabs + '<h2 class="sr-only">Letters by publication date</h2><div id="letter-results" class="letter-list">' + articles + '</div><p class="letter-figure-credit">Figures: Federal Reserve Bank of San Francisco.</p></main>')

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
        actions = [anchor(local_path(a.attrs['href'], slug), 'Open dashboard' if i < 2 else 'Download data', slug, 'data-action primary-action')]
        documentation, notes = [], []
        for n in nodes[1:]:
            if text(n).lower().startswith('documentation:'):
                documentation.append('<p>' + inner(n, slug, slug).replace('documentation:', '').strip() + '</p>')
                continue
            seen = set()
            for link_node in n.walk():
                if link_node.tag == 'a' and text(link_node) and link_node.attrs.get('href') not in seen:
                    seen.add(link_node.attrs['href'])
                    label = text(link_node).replace('excel file (.xlsx)', 'Excel data').replace('Stata Code', 'Stata code')
                    actions.append(anchor(local_path(link_node.attrs['href'], slug), label, slug, 'data-action'))
            if i >= 2 and '(last updated' in text(n):
                notes.append(re.search(r'\(last updated[^)]+\)', text(n)).group(0).strip('()').replace('last updated', 'Updated'))
            if 'requires Haver' in text(n):
                notes.append('Stata code requires Haver.')
        detail = '<div class="data-actions">' + ''.join(actions) + '</div>'
        if i < 2:
            data_source = ['https://adamshap.github.io/ismi-webapp/ism_data.csv', 'https://adamshap.github.io/supply-demand-webapp/supply_demand_baseline.csv'][i]
            detail += '<p class="data-note dashboard-update" data-dashboard-updated="' + data_source + '" hidden></p><noscript><p class="data-note">See dashboard for the latest data.</p></noscript>'
        detail += ''.join('<p class="data-note">' + escape(note) + '</p>' for note in notes)
        if documentation:
            detail += '<details class="data-documentation"><summary>Documentation</summary><div>' + ''.join(documentation) + '</div></details>'
        items += '<article class="data-item' + (' dashboard-item' if i < 2 else '') + '"><div class="data-item-heading"><p class="eyebrow">' + ('Interactive dashboard' if i < 2 else 'Data & replication') + '</p><h2>' + escape(title) + '</h2></div><div class="data-details">' + detail + '</div></article>'
    return page(slug, 'Code & Data | Adam Hale Shapiro', '<main id="content" class="page-main data-main">' + section_heading('Code & data') + '<div class="data-list">' + items + '</div></main>')

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
    statuses = [n for n in meta_paras if text(n).startswith('Conditionally accepted')]
    meta_paras = [n for n in meta_paras if n not in statuses]
    status_html = ''.join('<p class="paper-status">' + escape(text(n)) + '</p>' for n in statuses)
    resource_html = resources(links, slug, slug)
    bib_link = citation_link(title, slug, slug)
    if bib_link:
        resource_html = resource_html.removesuffix('</div>') + bib_link + '</div>' if resource_html else '<div class="resource-links">' + bib_link + '</div>'
    header = '<div class="paper-header"><p class="eyebrow">Research</p><h1>' + escape(title.strip('" ')) + '</h1><div class="paper-byline">' + ''.join(serialize(n, slug, slug, True) for n in meta_paras) + '</div>' + status_html + resource_html + '</div>'
    body = ''.join('<section class="prose">' + inner(b, slug, slug) + '</section>' for b in blocks[abstract_at:])
    return page(slug, title + ' | Adam Hale Shapiro', '<main id="content" class="page-main paper-main"><div class="breadcrumb">' + anchor('/research/', 'All research', slug) + '</div>' + header + '<div class="abstract-body">' + body + '</div><div class="paper-return">' + anchor('/research/', 'Browse all research', slug, 'button button-secondary') + '</div></main>')

def build():
    write_citations(DOCS / 'citations')
    pages = load_site()
    for slug, data in pages.items():
        if slug == '/':
            output = home(pages)
        elif slug == '/research':
            output = research(data, pages)
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
