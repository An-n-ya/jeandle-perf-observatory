import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from perfview.reuse import ReplayDataset
from perfview.data import discover, catalog

DATA = ROOT.parent / 'jeandle-develop-log/artifacts/context-cache-reuse-2026-10-23'

@unittest.skipUnless(DATA.is_dir(), 'Frozen replay not installed')
class ReplayTests(unittest.TestCase):
    def test_diagnostics_and_complete_three_rounds(self):
        d = ReplayDataset(DATA)
        self.assertEqual(len(d.overview['timings']), 18)
        self.assertEqual(d.overview['summary']['prefix']['rounds'], 3)
        diag = d.overview['diagnostics']
        self.assertEqual(diag['final']['cached']['final_hits'], 15)
        self.assertEqual(diag['prefix']['cached']['final_hits'], 0)
        self.assertEqual(diag['prefix']['cached']['facts_hits'], 15)
        self.assertEqual(diag['mutation']['cached']['checksum'], 16*(22+22+33))
        self.assertEqual(catalog(d)['cases'], ['final','prefix','mutation'])
        self.assertEqual(discover([DATA], ROOT/'.cache')[d.id].fingerprint, d.fingerprint)
        self.assertEqual(json.loads(d.raw('replay/timings.json').read_text()), d.overview['timings'])
        with self.assertRaises(KeyError): d.raw('../../etc/passwd')
        with self.assertRaises(KeyError): d.profile('final','cached','all')

    def test_corrupt_or_incomplete_timings_and_summary_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/DATA.name
            shutil.copytree(DATA, target)
            timing = target/'replay/timings.json'
            original = json.loads(timing.read_text())
            mutations = [original[:-1], original[:-1]+[original[0]]]
            wrong = copy.deepcopy(original); wrong[0]['checksum'] += 1; mutations.append(wrong)
            for rows in mutations:
                timing.write_text(json.dumps(rows))
                with self.assertRaises(ValueError): ReplayDataset(target)
            timing.write_text(json.dumps(original))
            summary = target/'replay/summary.json'
            value = json.loads(summary.read_text()); value['final']['cached_user_median'] = 99
            summary.write_text(json.dumps(value))
            with self.assertRaises(ValueError): ReplayDataset(target)

if __name__ == '__main__': unittest.main()
