import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from perfview.crosspass import ARTIFACTS, CrossPassDataset, MODES, PAIRS
from perfview.data import catalog
from perfview.methodology import CROSSPASS, CROSSPASS_PROTOCOL

DATA = Path(os.environ.get(
    'CROSS_PASS_DATA',
    '/home/annya/playground/jeandle/perf-results/2026-10-26-javatype-cross-pass-prod'))


@unittest.skipUnless(DATA.is_dir(), 'Frozen cross-pass run not installed')
class CrossPassTests(unittest.TestCase):
    def setUp(self):
        self.d = CrossPassDataset(DATA)

    def test_shape_and_catalog(self):
        o = self.d.overview
        self.assertEqual(o['kind'], 'cross-pass')
        self.assertEqual(o['modes'], list(MODES))
        self.assertEqual(o['pairs'], list(PAIRS))
        self.assertEqual(set(o['scenarios']), {'timing', 'mechanism', 'jvm', 'limits'})
        self.assertEqual(set(CROSSPASS), set(o['scenarios']))
        self.assertTrue(CROSSPASS_PROTOCOL.strip())
        entry = catalog(self.d)
        self.assertEqual(entry['kind'], 'cross-pass')
        self.assertEqual(entry['cases'], ['timing', 'mechanism', 'jvm', 'limits'])
        self.assertEqual(len(self.d.fingerprint), 64)
        self.assertEqual(self.d.status()['state'], 'ready')

    def test_timing_numbers_are_self_consistent(self):
        timing = self.d.overview['timing']
        self.assertEqual((timing['blocks'], timing['sessions'], timing['samples'],
                          timing['raw_rows']), (60, [0, 1], 64, 11520))
        for pair in PAIRS:
            p = timing['pairs'][pair]
            for metric in ('cpu', 'wall', 'cpu_eff', 'wall_eff'):
                m = p[metric]
                self.assertAlmostEqual(m['net_benefit'],
                                       1 - m['total_candidate_s'] / m['total_baseline_s'],
                                       places=9)
                ci = m['bootstrap_ci']
                self.assertLessEqual(ci['lo'], ci['mean'])
                self.assertLessEqual(ci['mean'], ci['hi'])
            v = timing['verdicts'][pair]
            self.assertAlmostEqual(v['net_benefit'], p['cpu']['net_benefit'], places=9)
            self.assertEqual(v['ci_crosses_zero'], v['ci'][0] <= 0 <= v['ci'][1])
            self.assertTrue(v['statement'].strip())

    def test_counters_add_up(self):
        subsystem = self.d.overview['subsystem']
        timeline = self.d.overview['timeline']
        for mode in MODES:
            totals = subsystem['totals'][mode]
            self.assertGreater(totals['queries'], 0)
            consumers = timeline['modes'][mode]['consumers']
            for total_key, consumer_key in (('queries', 'queries'),
                                            ('base insertions', 'base_insertions'),
                                            ('final type hits', 'final_hits'),
                                            ('final type misses', 'final_misses')):
                summed = sum(c[consumer_key] for c in consumers.values())
                self.assertAlmostEqual(summed, totals[total_key], places=6,
                                       msg=mode + '/' + total_key)

    def test_inventory_covers_the_corpus(self):
        corpus = self.d.overview['inventory']['corpus']
        self.assertEqual(corpus['accepted'], 64)
        self.assertEqual(corpus['accepted'] + corpus['rejected'], corpus['recorded'])

    def test_jvm_cost_and_jtreg(self):
        jvm = self.d.overview['jvm']
        self.assertEqual(jvm['controlled']['repeat'], 15)
        self.assertEqual(jvm['production']['repeat'], 10)
        self.assertIn('Passed. Execution successful', jvm['jtreg']['summary'])
        self.assertIn('passed: 1', jvm['jtreg']['stats'])

    def test_artifacts_are_published_and_readable(self):
        for name in ARTIFACTS:
            self.assertTrue(self.d.raw(name).is_file(), name)
        with self.assertRaises(KeyError):
            self.d.raw('../../etc/passwd')
        with self.assertRaises(KeyError):
            self.d.raw('timing/not-there.json')
        with self.assertRaises(KeyError):
            self.d.profile('timing', 'original', 'all')

    def test_timeline_drops_per_sample_detail(self):
        timeline = self.d.overview['timeline']
        self.assertEqual(timeline['samples'], 64)
        for mode in MODES:
            self.assertNotIn('per_sample', timeline['modes'][mode])


@unittest.skipUnless(DATA.is_dir(), 'Frozen cross-pass run not installed')
class CrossPassRejectionTests(unittest.TestCase):
    """Every published number must be rejected when the source no longer agrees."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name) / DATA.name
        shutil.copytree(DATA, self.target)

    def tearDown(self):
        self.tmp.cleanup()

    def mutate(self, relative, mutate):
        path = self.target / relative
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value))

    def test_missing_artifact_is_rejected(self):
        (self.target / 'timing/analysis.json').unlink()
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)

    def test_broken_net_benefit_is_rejected(self):
        def break_net(value):
            value['pairs']['original->cross_pass']['cpu']['net_benefit'] += 0.01
        self.mutate('timing/analysis.json', break_net)
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)

    def test_verdict_disagreeing_with_bootstrap_is_rejected(self):
        def break_verdict(value):
            value['verdicts']['pass_local->cross_pass']['ci'] = [0.0, 0.0]
        self.mutate('timing/analysis.json', break_verdict)
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)

    def test_counter_total_mismatch_is_rejected(self):
        def break_counter(value):
            value['totals']['cross_pass']['base insertions'] += 1
        self.mutate('diagnostics/subsystem_cost.json', break_counter)
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)

    def test_inventory_per_sample_mismatch_is_rejected(self):
        def break_sample(value):
            value['net_benefit_per_sample']['original->cross_pass'][0]['net_benefit'] += 0.02
        self.mutate('diagnostics/inventory.json', break_sample)
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)

    def test_jvm_net_gain_mismatch_is_rejected(self):
        def break_gain(value):
            pair = 'original->cross_pass'
            value['pairs'][pair]['total compile cost']['net_gain'] += 0.01
        self.mutate('jvm/jvm_compile_cost_controlled.json', break_gain)
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)

    def test_failed_jtreg_run_is_rejected(self):
        summary = self.target / 'jvm/jtreg/report/text/summary.txt'
        summary.write_text(summary.read_text().replace('Passed', 'FAILED'))
        with self.assertRaises(ValueError):
            CrossPassDataset(self.target)


if __name__ == '__main__':
    unittest.main()
