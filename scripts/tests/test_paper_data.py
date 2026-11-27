from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_site
import paper_data


class SharedPaperDataChecks(unittest.TestCase):
    def test_one_edit_reaches_both_web_views_and_citation(self):
        data = deepcopy(paper_data.load_papers())
        entry = next(p for p in data['papers'] if p['paper_path'] == '/papers')
        entry['match_title'] = 'Updated paper title'
        entry['fields']['author'] = 'Example, Newauthor and Shapiro, Adam Hale'
        entry['date'] = {'kind': 'revision', 'value': '2027-02'}
        entry['abstract_html'] = '<p>Updated abstract from the revised paper.</p>'
        entry['resources'][0]['href'] = 'https://example.org/revised-paper.pdf'
        with patch.object(paper_data, 'load_papers', return_value=data):
            pages = paper_data.load_site()
            research = ''.join(pages['/research']['blocks'])
            detail = ''.join(pages['/papers']['blocks'])
            for content in (research, detail):
                self.assertIn('Updated paper title', content)
                self.assertIn('Newauthor Example', content)
                self.assertIn('Revised February 2027', content)
                self.assertIn('https://example.org/revised-paper.pdf', content)
            self.assertIn(entry['abstract_html'], detail)
            citation = next(c for c in paper_data.citation_records() if c['paper_path'] == '/papers')
            self.assertEqual(citation['fields']['author'], entry['fields']['author'])
            self.assertEqual(citation['fields']['year'], '2027')
            self.assertIn('Revised February 2027', citation['fields']['note'])

    def test_generated_titles_and_abstracts_match_shared_records(self):
        for entry in paper_data.load_papers()['papers']:
            if not entry['paper_path']:
                continue
            filename = build_site.DOCS / entry['paper_path'].strip('/') / 'index.html'
            tree = build_site.Tree(filename.read_text(encoding='utf-8')).root
            self.assertEqual(build_site.text(tree.find('h1')), entry['match_title'])
            abstract = next(n for n in tree.walk() if n.attrs.get('class') == 'abstract-body')
            self.assertEqual(build_site.text(abstract).removeprefix('Abstract').strip(),
                             build_site.text(build_site.Tree(entry['abstract_html']).root))

    def test_legacy_report_citation_can_keep_its_original_year(self):
        record = next(c for c in paper_data.citation_records() if c['id'].startswith('subprime-outcomes'))
        self.assertEqual(record['fields']['year'], '2007')
        self.assertIn('Revised May 2008', record['fields']['note'])

    def test_old_duplicate_paper_storage_is_gone(self):
        static = json.loads((build_site.ROOT / 'content/site.json').read_text(encoding='utf-8'))
        self.assertNotIn('/research', static)
        for entry in paper_data.load_papers()['papers']:
            if entry['paper_path']:
                self.assertNotIn(entry['paper_path'], static)
        for filename in ('citations.json', 'research-figures.json', 'research-topics.json'):
            self.assertFalse((build_site.ROOT / 'content' / filename).exists())


class AccessibilityMarkupChecks(unittest.TestCase):
    def test_landmarks_heading_order_and_control_references(self):
        for path in build_site.DOCS.rglob('index.html'):
            with self.subTest(page=path):
                tree = build_site.Tree(path.read_text(encoding='utf-8')).root
                nodes = list(tree.walk())
                mains = [n for n in nodes if n.tag == 'main']
                self.assertEqual(len(mains), 1)
                self.assertEqual(mains[0].attrs.get('tabindex'), '-1')
                self.assertEqual(len([n for n in nodes if n.tag == 'h1']), 1)
                previous = 0
                for n in nodes:
                    if n.tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                        level = int(n.tag[1])
                        self.assertLessEqual(level, previous + 1)
                        previous = level
                ids = [n.attrs['id'] for n in nodes if 'id' in n.attrs]
                self.assertEqual(len(ids), len(set(ids)))
                for n in nodes:
                    for target in n.attrs.get('aria-controls', '').split():
                        self.assertIn(target, ids)
                    if n.tag == 'img':
                        self.assertIn('alt', n.attrs)
                    if n.tag == 'button' and 'data-copy-citation' in n.attrs:
                        self.assertTrue(n.attrs.get('aria-label', '').startswith('Copy BibTeX for '))


if __name__ == '__main__':
    unittest.main()
