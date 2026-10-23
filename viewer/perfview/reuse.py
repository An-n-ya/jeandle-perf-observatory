"""Frozen direct-API replay data: deliberately no perf sampling profiles."""
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from .methodology import REUSE, PROTOCOL

class ReplayDataset:
    def __init__(self, path, cache_root=None):
        self.path = Path(path).resolve()
        self.id = self.path.name
        names = ['replay/identity.json', 'replay/diagnostics.json', 'replay/timings.json',
                 'replay/summary.json', 'identity-post.json', 'tests.patch',
                 'unit-tests.log', 'lit-tests.log', 'replay.log']
        self.files = {n: self.path / n for n in names if (self.path / n).is_file()}
        report = self.path.parent.parent / 'JavaType-Context-Cache-Reuse-Execution-2026-10-23.md'
        if report.is_file():
            self.files['execution-report.md'] = report
        def read(name):
            return json.loads(self.files[name].read_text())
        identity, diagnostics, timings, summary, source = map(read, names[:5])
        if identity['rounds'] != 3 or identity['batches'] != 4096 or len(timings) != 18:
            raise ValueError('Expected exactly three paired rounds, 4096 batches and 18 timing runs')
        expected = set()
        for scenario, modes in diagnostics.items():
            if scenario not in REUSE or set(modes) != {'cached', 'full' if scenario == 'mutation' else 'cold'}:
                raise ValueError('Unexpected scenario or mode')
            for mode, d in modes.items():
                if not d['fresh_reference_checked'] or d['final_hits'] + d['final_misses'] != d['queries']:
                    raise ValueError('Diagnostic validation failed')
                for r in range(3):
                    expected.add((scenario, mode, r))
        seen = set()
        for t in timings:
            key = t['scenario'], t['mode'], t['round']
            if key not in expected or key in seen:
                raise ValueError('Missing, duplicate or unexpected timing run')
            seen.add(key)
            diag = diagnostics[t['scenario']][t['mode']]
            if (t['kind'] != 'timing' or t['batches'] != 4096 or
                t['checksum'] != diag['checksum'] * t['batches'] or
                not all(math.isfinite(t[k]) and t[k] > 0 for k in ('user_s', 'wall_s'))):
                raise ValueError('Invalid timing/checksum')
        if seen != expected or set(summary) != set(REUSE):
            raise ValueError('Incomplete replay')
        for scenario, s in summary.items():
            baseline = 'full' if scenario == 'mutation' else 'cold'
            values = {(t['mode'], t['round']): t['user_s'] for t in timings if t['scenario'] == scenario}
            reductions = [100 * (1 - values['cached', r] / values[baseline, r]) for r in range(3)]
            checks = {'baseline_user_median': median(values[baseline, r] for r in range(3)),
                      'cached_user_median': median(values['cached', r] for r in range(3)),
                      'paired_cpu_reduction_pct_median': median(reductions)}
            if s['baseline_mode'] != baseline or s['rounds'] != 3 or any(
                    not math.isclose(s[k], v, abs_tol=1e-9) for k, v in checks.items()):
                raise ValueError('Saved summary disagrees with raw timings')
            if len(s['paired_reductions_pct']) != 3 or any(not math.isclose(a,b,abs_tol=1e-9)
                    for a,b in zip(s['paired_reductions_pct'], reductions)):
                raise ValueError('Saved paired reductions disagree')
        self.fingerprint = hashlib.sha256(b''.join(self.files[n].read_bytes() for n in names[:5])).hexdigest()
        self.overview = dict(id=self.id, kind='context-reuse', label='上下文缓存复用 · 三轮回放',
            fingerprint=self.fingerprint, scenarios=REUSE, methodology=REUSE, protocol=PROTOCOL,
            identity=identity, source=source, diagnostics=diagnostics, timings=timings,
            summary=summary, files=list(self.files))

    def status(self):
        return dict(state='ready', completed=18, total=18, errors=[])

    def index(self):
        pass

    def raw(self, name):
        if name not in self.files:
            raise KeyError('Unknown artifact')
        return self.files[name]

    def profile(self, *args):
        raise KeyError('This replay has no sampled profiles')

    record = profile
