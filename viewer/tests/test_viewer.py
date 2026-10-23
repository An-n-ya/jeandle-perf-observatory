"""Unit tests plus conservation checks against the frozen real experiment."""
import collections
import gzip
import io
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from perfview.classify import classify
from perfview.data import Dataset, NotReady
from perfview.stacks import function_costs, merge, parse, speedscope
from server import create_server

DATA = ROOT.parent / 'jeandle-develop-log/artifacts/java-type-perf-2026-10-23'


class FakeSymbols:
    start = 0x100

    def lookup(self, address):
        return 'llvm::jeandle::JavaTypeAnalysisResult::getCachedJavaType(llvm::Value*)' if address == 0x200 else ''


class StackTests(unittest.TestCase):
    def test_period_weighting_filtering_and_native_mapping(self):
        text = '''opt 10 1.000: 900 cpu_atom/cycles/u:
  1200 factsAt+0x0 (inlined)
  1100 _start+0x0 (/opt)

opt 10 1.002: 100 cpu_atom/cycles/u:
  3000 [unknown] (/libc)
  1100 _start+0x0 (/opt)

other 11 1.003: 500 cpu_atom/cycles/u:
  3000 ignored+0x0 (/libc)

opt 10 1.004: 500 cpu_core/cycles/u:
  3000 ignored+0x0 (/libc)
'''
        p = parse(io.StringIO(text), FakeSymbols())
        self.assertEqual(len(p['samples']), 2)
        self.assertEqual(p['period_sum'], 1000)
        self.assertTrue(p['image_base_known'])
        self.assertIn('jt', p['samples'][0]['flags'])
        self.assertNotIn('jt', p['samples'][1]['flags'])
        jt_weight = sum(s['weight'] for s in p['samples'] if 'jt' in s['flags'])
        self.assertEqual(jt_weight / p['period_sum'], .9)  # Not 50% by sample count.
        self.assertEqual(p['frames'][p['samples'][0]['stack'][-1]]['name'], 'factsAt')

    def test_signature_type_is_not_execution(self):
        sample = {'frames': [dict(name='getCachedJavaType', native=
            'llvm::jeandle::JavaTypeAnalysisResult::getCachedJavaType(llvm::LazyValueInfo&, llvm::DominatorTree&)')]}
        info = classify(sample)
        self.assertTrue(info['jt'])
        self.assertFalse(info['lvi'])
        self.assertFalse(info['dt'])
        sample['frames'].insert(0, dict(name='solveBlockValueSelect', native='llvm::LazyValueInfoImpl::solveBlockValueSelect()'))
        self.assertEqual(classify(sample)['group'], 'javatype/query_lvi')

    def test_recursive_inclusive_conservation_and_export(self):
        p = dict(frames=[dict(name='recursive', native='', inline=False), dict(name='leaf', native='', inline=False)],
                 samples=[dict(stack=[0, 0, 1], weight=90, time=1, flags=[], category='external/other'),
                          dict(stack=[0], weight=10, time=2, flags=[], category='external/other')],
                 period_sum=100, image_base_known=False)
        costs = {r['id']: r for r in function_costs(p)}
        self.assertEqual(costs[0]['inclusive'], 100)
        self.assertEqual(costs[0]['self'], 10)
        self.assertEqual(sum(r['self'] for r in costs.values()), 100)
        m = merge([('run-00', p), ('run-01', p)])
        self.assertEqual(m['period_sum'], 200)
        self.assertEqual(len(m['frames']), 2)
        export = speedscope(m, 'test')
        self.assertEqual(len(export['profiles']), 2)
        for profile in export['profiles']:
            self.assertEqual(profile['unit'], 'none')
            self.assertEqual(profile['samples'][0], [0, 0, 1])
            self.assertEqual(profile['weights'], [90, 10])
            self.assertEqual(sum(profile['weights']), profile['endValue'])


@unittest.skipUnless(DATA.exists(), 'Frozen dataset not installed')
class RealDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the service's existing disposable cache when present; any new files
        # remain under the application, never in the frozen dataset.
        cls.dataset = Dataset(DATA, ROOT / '.cache')
        cls.dataset.index()
        cls.server = create_server({cls.dataset.id: cls.dataset}, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path, headers=None):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers or {}))

    def test_all_77_indexes_and_72_frozen_partitions(self):
        d = self.dataset
        self.assertEqual(d.status()['state'], 'ready', d.status()['errors'])
        self.assertEqual(d.status()['completed'], 77)
        self.assertEqual(len(d.indexes), 77)
        by_profile = collections.defaultdict(dict)
        for row in d.overview['partitions']:
            by_profile[(row['case'], row['mode'], row['run'])][row['category']] = int(row['period_sum'])
        for expected in d.attribution['profiles']:
            key = (expected['case'], expected['mode'], expected['run'])
            with self.subTest(profile=key):
                p = d.profile(*key)
                self.assertEqual(len(p['samples']), expected['samples'])
                self.assertEqual(p['period_sum'], expected['period_sum'])
                groups = collections.Counter()
                for sample in p['samples']:
                    groups[sample['category']] += sample['weight']
                self.assertEqual(dict(groups), by_profile[key])
                jt = sum(s['weight'] for s in p['samples'] if 'jt' in s['flags'])
                self.assertAlmostEqual(100 * jt / p['period_sum'], expected['jt_pct'], places=9)

    def test_diagnostics_remain_separate_from_three_repeats(self):
        for check in self.dataset.overview['quality']['quality_checks']:
            p = self.dataset.profile(check['case'], 's1', 'diag:' + check['tag'])
            self.assertEqual(len(p['samples']), check['samples'])
        p = self.dataset.profile('deep-static', 's1', 'all')
        self.assertEqual(len(p['runs']), 3)
        self.assertEqual(len(p['samples']), 3535)

    def test_known_baseline_and_rss(self):
        d = self.dataset.overview
        self.assertAlmostEqual(d['baseline']['deep-static']['s1']['user_s']['median'], 5.7674575)
        scheduling = next(q for q in d['quality']['scheduling'] if q['case'] == 'deep-static' and q['mode'] == 's1')
        self.assertLess(scheduling['max_rss_kb_median'], 600000)
        self.assertGreater(scheduling['involuntary_context_switches_median'], 0)

    def test_http_profile_export_and_artifact(self):
        with self.get('/api/profile?case=deep-static&mode=s1&run=all', {'Accept-Encoding':'gzip'}) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(r.headers.get('Content-Encoding'), 'gzip')
            profile = json.loads(gzip.decompress(r.read()))
        with self.get('/api/speedscope?case=deep-static&mode=s1&run=all') as r:
            export = json.load(r)
        self.assertEqual(len(export['profiles']), 3)
        self.assertEqual(sum(p['endValue'] for p in export['profiles']), profile['period_sum'])
        with self.get('/api/record?case=deep-static&mode=s1&run=run-00&kind=run.json') as r:
            self.assertIn('elapsed_ns', json.load(r))
        with self.get('/api/raw?file=source-context.json') as r:
            self.assertEqual(len(json.load(r)), 7)

    def test_path_traversal_host_origin_and_bad_selections(self):
        for path in ('/api/raw?file=../../etc/passwd', '/../../etc/passwd',
                     '/api/profile?case=../../&mode=s1&run=run-00',
                     '/api/profile?case=deep-static&mode=s1&run=run-99',
                     '/api/record?case=deep-static&mode=s1&run=run-00&kind=../../etc/passwd'):
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as e:
                self.get(path)
            self.assertEqual(e.exception.code, 404)
            e.exception.close()
        for headers in ({'Host':'evil.example'}, {'Origin':'https://evil.example'}):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.get('/api/overview', headers)
            self.assertEqual(e.exception.code, 403)
            e.exception.close()


if __name__ == '__main__':
    unittest.main()
