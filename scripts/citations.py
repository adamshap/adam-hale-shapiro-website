"""Build stable BibTeX downloads from publisher-verified, local metadata."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalized_title(value):
    return ''.join(c for c in value.casefold() if c.isalnum())


def load_citations():
    entries = json.loads((ROOT / 'content/citations.json').read_text(encoding='utf-8'))
    for field in ('id', 'key', 'match_title'):
        values = [e[field] for e in entries]
        if len(values) != len(set(values)):
            raise ValueError('Duplicate citation ' + field)
    for entry in entries:
        if not re.fullmatch(r'[a-z0-9-]+', entry['id']):
            raise ValueError('Unsafe citation filename')
        required = {'title', 'author', 'year', 'url'}
        required |= {'article': {'journal', 'volume'},
                     'incollection': {'booktitle', 'editor', 'publisher', 'pages'},
                     'techreport': {'institution', 'number'}}[entry['entry_type']]
        if any(not entry['fields'].get(k) for k in required):
            raise ValueError('Incomplete citation: ' + entry['id'])
    return entries


def latex_text(value):
    # Keep traditional BibTeX users compatible with accented author names.
    accents = {'\u0301': "'", '\u0300': '`', '\u0302': '^', '\u0308': '"',
               '\u0303': '~', '\u0327': 'c', '\u030a': 'r'}
    result = ''
    for char in value:
        decomposed = unicodedata.normalize('NFD', char)
        if len(decomposed) == 2 and decomposed[1] in accents:
            result += '{\\' + accents[decomposed[1]] + '{' + decomposed[0] + '}}'
        elif char in '&%_#$':
            result += '\\' + char
        else:
            result += char
    return result


def bibtex(entry):
    lines = ['@' + entry['entry_type'] + '{' + entry['key'] + ',']
    for key, value in entry['fields'].items():
        # URLs and DOIs must retain their literal machine-readable spelling.
        rendered = value if key in ('url', 'doi') else latex_text(value)
        if key in ('title', 'booktitle'):
            rendered = '{' + rendered + '}'
        lines.append('  ' + key + ' = {' + rendered + '},')
    return '\n'.join(lines) + '\n}\n'


def write_citations(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for entry in load_citations():
        (destination / (entry['id'] + '.bib')).write_text(
            bibtex(entry), encoding='utf-8', newline='\n')
