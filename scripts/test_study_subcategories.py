"""Regression checks for automatic study subcategory folders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_content as bc
import study_material as sm


class StudySubcategoryTests(unittest.TestCase):
    def test_new_chapters_and_languages_follow_their_period_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / 'content'
            base = content / 'study-material'
            registry = {'hierarchies': {'gk': {'name': 'GK', 'regions': [{
                'id': 'india-gk', 'name': 'India GK', 'categories': [{
                    'id': 'history', 'name': 'History', 'folders': ['history'],
                    'subCategories': [{'id': sid, 'name': name} for sid, name in [
                        ('ancient-history', 'Ancient History'),
                        ('medieval-history', 'Medieval History'),
                        ('modern-history', 'Modern History')]]}]}]}}}
            base.mkdir(parents=True)
            (base / 'metadata.json').write_text(json.dumps(registry))
            records = []
            for sub in ('ancient-history', 'medieval-history', 'modern-history'):
                for lang in ('english', 'punjabi'):
                    for part in ('part-1.md', 'part-2.md'):
                        rel = Path('content/study-material/history') / sub / lang / '01 - A Very Long New Chapter Name About the Expansion of British Power in India' / part
                        full = root / rel
                        full.parent.mkdir(parents=True, exist_ok=True)
                        full.write_text('A new chapter with any file name.')
                        records.append({'path': str(rel), 'file': f'{sub}-{lang}-{part}.html'})
            legacy = Path('content/study-material/history/english/Old Chapter/notes.md')
            (root / legacy).parent.mkdir(parents=True)
            (root / legacy).write_text('Legacy chapter')
            records.append({'path': str(legacy), 'file': 'old.html'})
            with patch.multiple(bc, ROOT=root, CONTENT=content), patch.multiple(
                    sm, ROOT=root, CONTENT=content, OUT=root / 'study-manifest.json'):
                bc._STUDY_SIBLINGS.clear()
                self.assertEqual(bc.study_locator(legacy), ('history', 'english', 'Old Chapter'))
                self.assertEqual(bc.study_layout('content/study-material/history/Modern History/punjabi/Test/a.pdf'),
                                 ('history', 'modern-history', 'punjabi', 'Test'))
                for record in records[:-1]:
                    title = bc.study_title_for(Path(record['path']))
                    self.assertLessEqual(len(title), 60)
                    self.assertIn(' - Part ', title)
                    self.assertTrue(title.endswith('(English)') or title.endswith('(Punjabi)'))
                bc.stamp_study_fields(records)
                manifest = sm.build(records, registry)
                gk = next(s for s in manifest['subjects'] if s['id'] == 'gk')
                cat = gk['hierarchy']['regions'][0]['categories'][0]
                self.assertEqual({l['id'] for l in manifest['languages']}, {'en', 'pa'})
                self.assertEqual(len(cat['claimedChapters']), 3)
                for sub in cat['subCategories']:
                    self.assertEqual(sub['stats']['chapters'], 1)
                    self.assertEqual(sub['stats']['files'], 4)
                    for lang in sub['languages']:
                        self.assertEqual(len(lang['chapters']), 1)
                        chapter = lang['chapters'][0]
                        self.assertEqual(chapter['id'], sub['id'] + '/01 - A Very Long New Chapter Name About the Expansion of British Power in India')
                        self.assertEqual([p['n'] for p in chapter['parts']], [1, 2])
                self.assertEqual(records[-1]['studyChapter'], 'Old Chapter')
                bc._STUDY_SIBLINGS.clear()


if __name__ == '__main__':
    unittest.main()
