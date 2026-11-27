"""One paper record supplies Research, the homepage, detail pages and BibTeX."""
from copy import deepcopy
from html import escape
from pathlib import Path
import calendar
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def load_papers():
    data = json.loads((ROOT / 'content/papers.json').read_text(encoding='utf-8'))
    papers = data['papers']
    for name in ('id', 'key', 'match_title'):
        values = [p[name] for p in papers]
        if len(values) != len(set(values)):
            raise ValueError('Duplicate paper ' + name)
    for paper in papers:
        if paper['group'] not in data['groups']:
            raise ValueError('Unknown paper group: ' + paper['id'])
        if not re.fullmatch(r'\d{4}(?:-\d{2})?', paper['date']['value']):
            raise ValueError('Invalid paper date: ' + paper['id'])
        if '-' in paper['date']['value'] and not 1 <= int(paper['date']['value'].split('-')[1]) <= 12:
            raise ValueError('Invalid paper month: ' + paper['id'])
        if paper['date']['kind'] not in ('publication', 'revision'):
            raise ValueError('Invalid date kind: ' + paper['id'])
        urls = [link['href'] for link in paper['resources']]
        if len(urls) != len(set(urls)):
            raise ValueError('Duplicate paper resource: ' + paper['id'])
        if not isinstance(paper['topics'], list) or set(paper['topics']) - {'inflation', 'health', 'competition', 'finance'}:
            raise ValueError('Invalid paper topics: ' + paper['id'])
    return data


def research_assets(kind):
    if kind == 'figure':
        return {p['href']: dict(p['figure'], title=p['match_title']) for p in load_papers()['papers']}
    if kind == 'topics':
        return {p['href']: p['topics'] for p in load_papers()['papers']}
    raise ValueError('Unknown research asset: ' + kind)


def date_text(paper, revision_prefix=True):
    date = paper['date']
    parts = date['value'].split('-')
    month = calendar.month_name[int(parts[1])] if len(parts) == 2 else date.get('season', '')
    label = (month + ' ' + parts[0]).strip()
    return ('Revised ' if revision_prefix and date['kind'] == 'revision' else '') + label


def citation_records():
    result = []
    for paper in load_papers()['papers']:
        entry = {k: deepcopy(paper[k]) for k in ('id', 'key', 'match_title', 'paper_path', 'entry_type', 'fields', 'sources', 'verified')}
        entry['fields']['year'] = paper.get('citation_year', paper['date']['value'][:4])
        if paper['date']['kind'] == 'revision':
            note = entry['fields'].get('note', '')
            entry['fields']['note'] = (note + '; ' if note else '') + date_text(paper)
        result.append(entry)
    return result


def authors(paper, compact=False, omit_owner=False):
    result = []
    for value in paper['fields']['author'].split(' and '):
        family, given = (s.strip() for s in value.split(',', 1))
        if omit_owner and family == 'Shapiro' and given in ('Adam', 'Adam Hale'):
            continue
        name = (given.split()[0] if compact else given) + ' ' + family
        url = paper.get('author_links', {}).get(value)
        result.append('<a href="' + escape(url, quote=True) + '">' + escape(name) + '</a>' if compact and url else escape(name))
    if len(result) < 2:
        return ''.join(result)
    return ', '.join(result[:-1]) + (', and ' if len(result) > 2 else ' and ') + result[-1]


def acceptance(paper):
    note = paper['fields'].get('note', '')
    return note.replace('American Economic Journal:', 'AEJ:') if note.startswith('Conditionally accepted') else ''


def venue(paper, detailed=False):
    fields = paper['fields']
    if paper.get('venue_label'):
        label = paper['venue_label']
    elif paper['entry_type'] == 'article':
        label = fields['journal']
        if not detailed:
            label += ' ' + fields.get('volume', '')
            if fields.get('number'):
                label += '(' + fields['number'] + ')'
            if fields.get('pages'):
                label += ', ' + fields['pages'].replace('--', '–')
    elif paper['entry_type'] == 'incollection':
        label = fields['booktitle'] + ', ' + fields['publisher'] + ' / NBER'
    elif fields['institution'] == 'Federal Reserve Bank of San Francisco':
        label = 'FRBSF Working Paper'
        if paper['group'] == 'older-working-papers':
            label += ' ' + fields['number']
    elif fields.get('note', '').startswith('Background paper for the '):
        label = fields['note'].removeprefix('Background paper for the ')
    else:
        label = fields['institution'] + ' ' + fields.get('type', 'Working Paper')
        if fields.get('number'):
            label += ' ' + fields['number']
    label = escape(label.strip())
    if not detailed and paper.get('volume_url'):
        volume = escape(fields['volume'] + ('(' + fields['number'] + ')' if fields.get('number') else ''))
        label = label.replace(volume, '<a href="' + escape(paper['volume_url'], quote=True) + '">' + volume + '</a>', 1)
    return label


def resources(paper, view):
    return ''.join('<p class="resource"><a href="' + escape(link['href'], quote=True) + '">' + escape(link['label']) + '</a></p>'
                   for link in paper['resources'] if view in link['views'])


def research_block(paper):
    title = '<p><a href="' + escape(paper['href'], quote=True) + '">' + escape(paper['match_title']) + '</a></p>'
    byline = authors(paper, compact=True, omit_owner=True)
    status = acceptance(paper)
    return ('<section class="content-block">' + title + ('<p>with ' + byline + '</p>' if byline else '')
            + '<p>' + venue(paper) + ' &middot; ' + escape(date_text(paper)) + '</p>'
            + ('<p>' + escape(status) + '</p>' if status else '')
            + resources(paper, 'research') + paper.get('coverage_html', '') + '</section>')


def detail_page(paper):
    status = acceptance(paper)
    blocks = ['<section class="content-block"><h2>' + escape(paper['match_title']) + '</h2></section>',
              '<section class="content-block"><p>' + authors(paper) + '</p>'
              + ('<p>' + venue(paper, detailed=True) + '</p>' if paper.get('detail_show_venue', True) else '')
              + '<p>' + escape(date_text(paper)) + '</p>' + ('<p>' + escape(status) + '</p>' if status else '')
              + resources(paper, 'detail') + (paper.get('coverage_html', '') if paper.get('detail_coverage') else '') + '</section>']
    if paper.get('abstract_html'):
        blocks += ['<section class="content-block"><h2>Abstract</h2></section>',
                   '<section class="content-block">' + paper['abstract_html'] + '</section>']
    return {'title': paper['match_title'], 'blocks': blocks}


def load_site():
    pages = json.loads((ROOT / 'content/site.json').read_text(encoding='utf-8'))
    data = load_papers()
    research = []
    for group, label in data['groups'].items():
        research.append('<section class="content-block"><h2>' + escape(label) + '</h2></section>')
        research += [research_block(p) for p in data['papers'] if p['group'] == group]
    pages['/research'] = {'title': 'Research', 'blocks': research}
    for paper in data['papers']:
        if paper['paper_path']:
            pages[paper['paper_path']] = detail_page(paper)
    return pages
