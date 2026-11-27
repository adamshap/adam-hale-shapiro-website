import sys
import unittest
from pathlib import Path
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_site
from citations import bibtex, load_citations


class CitationChecks(unittest.TestCase):
    def setUp(self):
        self.entries = load_citations()
        self.root = build_site.ROOT

    def test_every_research_entry_has_one_working_download_before_disclosures(self):
        tree = build_site.Tree((self.root / 'docs/research/index.html').read_text(encoding='utf-8'))
        papers = [n for n in tree.root.walk() if n.tag == 'article' and 'paper' in n.attrs.get('class', '').split()]
        self.assertEqual(len(papers), len(self.entries))
        found = set()
        for paper in papers:
            with self.subTest(title=paper.find('h3').text()):
                links = [n for n in paper.walk() if n.tag == 'a' and n.text() == 'Download .bib']
                self.assertEqual(len(links), 1)
                link = links[0]
                path = urlsplit(urljoin('https://local.test/research/', link.attrs['href'])).path
                filename = self.root / 'docs' / path.lstrip('/')
                self.assertTrue(filename.is_file())
                self.assertEqual(link.attrs['download'], filename.name)
                found.add(filename.name)
                panel = next(n for n in paper.walk() if n.tag == 'details' and 'paper-citation' in n.attrs.get('class', ''))
                self.assertIn('readonly', panel.find('textarea').attrs)
                self.assertEqual(panel.find('textarea').text(), filename.read_text(encoding='utf-8'))
                self.assertEqual(len([n for n in panel.walk() if n.tag == 'button' and 'data-copy-citation' in n.attrs]), 1)
                actions = list(panel.parent.children)
                for disclosure in (n for n in actions if isinstance(n, build_site.Node) and n.tag == 'details'):
                    if disclosure is not panel:
                        self.assertLess(actions.index(panel), actions.index(disclosure))
        self.assertEqual(found, {e['id'] + '.bib' for e in self.entries})

    def test_home_and_detail_pages_use_the_same_citations(self):
        for entry in self.entries:
            if entry['paper_path']:
                tree = build_site.Tree((self.root / 'docs' / entry['paper_path'].strip('/') / 'index.html').read_text(encoding='utf-8'))
                links = [n for n in tree.root.walk() if n.tag == 'a' and n.text() == 'Download .bib']
                self.assertEqual(len(links), 1, entry['id'])
                self.assertTrue(links[0].attrs['href'].endswith('/' + entry['id'] + '.bib'))
        tree = build_site.Tree((self.root / 'docs/index.html').read_text(encoding='utf-8'))
        papers = [n for n in tree.root.walk() if n.tag == 'article' and 'paper' in n.attrs.get('class', '').split()]
        self.assertTrue(papers)
        for paper in papers:
            self.assertEqual(len([n for n in paper.walk() if n.tag == 'a' and n.text() == 'Download .bib']), 1)

    def test_published_citations_are_final_articles_or_chapters(self):
        by_title = {e['match_title']: e for e in self.entries}
        example = by_title['Decomposing Supply and Demand Driven Inflation']
        self.assertEqual(example['entry_type'], 'article')
        self.assertEqual({k: example['fields'][k] for k in ('doi', 'year', 'volume', 'number', 'pages')},
                         dict(doi='10.1111/jmcb.13209', year='2026', volume='58', number='2', pages='365--388'))
        self.assertEqual(by_title['Measuring News Sentiment']['fields']['year'], '2022')
        self.assertEqual(by_title['Decomposing Medical-Care Expenditure Growth']['entry_type'], 'incollection')
        for entry in self.entries:
            fields = entry['fields']
            if entry['entry_type'] == 'article':
                self.assertNotIn('Working Paper', fields['journal'])
            if fields.get('note', '').startswith('Conditionally accepted'):
                self.assertEqual(entry['entry_type'], 'techreport')
                self.assertNotIn('journal', fields)

    def test_accented_names_and_coauthors_are_preserved(self):
        sample = next(e for e in self.entries if e['match_title'] == 'Phillips meets Beveridge')
        self.assertIn("R{\\'{e}}gis", bibtex(sample))
        self.assertIn('Barnichon', sample['fields']['author'])


if __name__ == '__main__':
    unittest.main()
