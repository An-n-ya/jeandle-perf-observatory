"""Frozen cross-pass production measurements: counters, paired timing and JVM cost."""
import hashlib
import json
import math
from pathlib import Path

from .methodology import CROSSPASS, CROSSPASS_PROTOCOL

MODES = ('original', 'pass_local', 'cross_pass')
PAIRS = ('original->cross_pass', 'pass_local->cross_pass')
METRICS = ('cpu', 'wall', 'cpu_eff', 'wall_eff')
JVM_METRICS = ('total compile cost', 'Jeandle compile time', 'LLVM Optimize',
               'LLVM CodeGen', 'application time', 'process wall clock')

# Published with the site. Raw perf.data, per-run flame graphs and crash logs stay on the server.
ARTIFACTS = (
    'report.md',
    'identity/identity.json',
    'timing/analysis.json',
    'timing/environment.json',
    'timing/summary.md',
    'timing/raw.csv',
    'timing/baseline.csv',
    'diagnostics/subsystem_cost.json',
    'diagnostics/cross_pass_trace_summary.json',
    'diagnostics/inventory.json',
    'diagnostics/inventory.md',
    'diagnostics/eligibility.json',
    'profiles/cost_decomposition.json',
    'profiles/cost_decomposition.svg',
    'profiles/pass_invocation_timeline.json',
    'profiles/perf_stat_original.csv',
    'profiles/perf_stat_pass_local.csv',
    'profiles/perf_stat_cross_pass.csv',
    'jvm/jvm_compile_cost_controlled.json',
    'jvm/jvm_compile_cost_production.json',
    'jvm/jvm_compile_cost_summary.md',
    'jvm/jtreg/report/text/summary.txt',
    'jvm/jtreg/report/text/stats.txt',
    'jvm/jtreg/report/text/timeStats.txt',
    'jvm/jtreg/report/text/cmdArgs.txt',
    'jvm/jtreg/artifacts/argv_original.txt',
    'jvm/jtreg/artifacts/argv_pass_local.txt',
    'jvm/jtreg/artifacts/argv_cross_pass.txt',
    'jvm/jtreg/artifacts/citime_original.txt',
    'jvm/jtreg/artifacts/citime_pass_local.txt',
    'jvm/jtreg/artifacts/citime_cross_pass.txt',
    'jvm/jtreg/artifacts/trace_original.txt',
    'jvm/jtreg/artifacts/trace_pass_local.txt',
    'jvm/jtreg/artifacts/trace_cross_pass.txt',
    'jvm/ab/baseline_head.summary',
    'jvm/ab/current_worktree.summary',
)

PRIMARY = (
    'timing/analysis.json', 'timing/environment.json', 'diagnostics/subsystem_cost.json',
    'diagnostics/cross_pass_trace_summary.json', 'diagnostics/inventory.json',
    'profiles/cost_decomposition.json', 'profiles/pass_invocation_timeline.json',
    'jvm/jvm_compile_cost_controlled.json', 'jvm/jvm_compile_cost_production.json',
    'identity/identity.json',
)

# Counter keys quoted from the experiment, spelled exactly as the tools wrote them.
QUERY_COUNTERS = ('queries', 'bypasses', 'base insertions', 'final type hits',
                  'final type misses', 'path facts hits', 'path facts misses',
                  'invalidation requests', 'selective invalidations',
                  'pass-local cache clears', 'base entries retained', 'base entries invalidated',
                  'final type entries invalidated')
# The two nanosecond counters are timings, not counts: the counter run and the
# trace run are separate processes, so only the counts are compared.
TIME_COUNTERS = ('total query time (ns)', 'total invalidation time (ns)')


def _close(a, b, tol=1e-9):
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


def _parse_perf_stat(text):
    """perf stat -x, output: value,unit,event,runtime,percentage,..."""
    values = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 3 or parts[0].startswith('#') or not parts[0]:
            continue
        if parts[0].startswith('<'):
            continue
        try:
            values[parts[2]] = float(parts[0])
        except ValueError:
            continue
    return values


class CrossPassDataset:
    """Read-only view of one frozen cross-pass production run.

    Every number is cross-checked against the raw records before it is published:
    net benefit must equal 1 - candidate/baseline, verdicts must agree with the
    bootstrap intervals, and the consumer counters must add up to the totals.
    """

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.id = self.path.name
        self.files = {}
        for name in ARTIFACTS:
            p = self.path / name
            if not p.is_file():
                raise ValueError('Missing required artifact: ' + name)
            self.files[name] = p

        def read(name):
            return json.loads(self.files[name].read_text())

        analysis = read('timing/analysis.json')
        environment = read('timing/environment.json')
        subsystem = read('diagnostics/subsystem_cost.json')
        trace = read('diagnostics/cross_pass_trace_summary.json')
        inventory = read('diagnostics/inventory.json')
        decomposition = read('profiles/cost_decomposition.json')
        timeline = read('profiles/pass_invocation_timeline.json')
        controlled = read('jvm/jvm_compile_cost_controlled.json')
        production = read('jvm/jvm_compile_cost_production.json')
        identity = read('identity/identity.json')

        self._check_timing(analysis, environment)
        self._check_counters(subsystem, trace, timeline)
        self._check_inventory(inventory)
        self._check_jvm(controlled, production)
        jtreg = self._check_jtreg()
        perf_stat = {mode: _parse_perf_stat(self.files['profiles/perf_stat_%s.csv' % mode].read_text())
                     for mode in MODES}

        digest = hashlib.sha256()
        for name in PRIMARY:
            digest.update(self.files[name].read_bytes())
        self.fingerprint = digest.hexdigest()

        self.overview = dict(
            id=self.id, kind='cross-pass', label='跨 pass 缓存 · 生产流水线性能',
            fingerprint=self.fingerprint, scenarios=CROSSPASS, methodology=CROSSPASS,
            protocol=CROSSPASS_PROTOCOL, modes=list(MODES), pairs=list(PAIRS),
            identity=identity, environment=environment, timing=analysis,
            subsystem=subsystem, trace=trace, inventory=inventory,
            decomposition=decomposition, timeline=self._trim_timeline(timeline),
            perf_stat=perf_stat, jvm=dict(controlled=controlled, production=production,
                                           jtreg=jtreg, ab=self._read_ab()),
            files=list(self.files))

    # ---------------------------------------------------------------- checks

    def _check_timing(self, analysis, environment):
        if (analysis['blocks'], analysis['sessions'], analysis['samples'],
                analysis['raw_rows']) != (60, [0, 1], 64, 11520):
            raise ValueError('Unexpected timing shape')
        if analysis['baseline_samples'] != 128:
            raise ValueError('Unexpected no-op baseline sample count')
        if environment['samples'] != 64 or environment['blocks_per_session'] != 30:
            raise ValueError('Environment does not match the timing run')
        if set(analysis['pairs']) != set(PAIRS) or set(analysis['verdicts']) != set(PAIRS):
            raise ValueError('Unexpected comparison pairs')
        for pair in PAIRS:
            p = analysis['pairs'][pair]
            for metric in METRICS:
                m = p[metric]
                expected = 1 - m['total_candidate_s'] / m['total_baseline_s']
                if not _close(m['net_benefit'], expected):
                    raise ValueError('Net benefit does not match the totals: ' + pair + '/' + metric)
                ci = m['bootstrap_ci']
                if not ci['lo'] <= ci['mean'] <= ci['hi'] or not ci['lo'] <= ci['hi']:
                    raise ValueError('Invalid bootstrap interval: ' + pair + '/' + metric)
                if m['block_net_sd'] < 0 or m['per_round_baseline_s'] <= 0 or \
                        m['per_round_candidate_s'] <= 0:
                    raise ValueError('Invalid block statistics: ' + pair + '/' + metric)
                spread = m['per_sample']
                if not (spread['min'] <= spread['p50'] <= spread['max']):
                    raise ValueError('Invalid per-sample spread: ' + pair + '/' + metric)
                if not 0 <= spread['negative_share'] <= 1:
                    raise ValueError('Invalid negative share: ' + pair + '/' + metric)
            v = analysis['verdicts'][pair]
            cpu, cpu_eff = p['cpu'], p['cpu_eff']
            if not _close(v['net_benefit'], cpu['net_benefit']):
                raise ValueError('Verdict disagrees with the CPU net benefit: ' + pair)
            if not _close(v['effective_net_benefit'], cpu_eff['net_benefit']):
                raise ValueError('Verdict disagrees with the effective net benefit: ' + pair)
            for verdict_key, metric in (('ci', 'cpu'), ('effective_ci', 'cpu_eff')):
                lo, hi = v[verdict_key]
                if not _close(lo, p[metric]['bootstrap_ci']['lo']) or \
                        not _close(hi, p[metric]['bootstrap_ci']['hi']):
                    raise ValueError('Verdict interval disagrees with the bootstrap interval: ' + pair)
                crosses = lo <= 0 <= hi
                if v[verdict_key + '_crosses_zero'] != crosses:
                    raise ValueError('Verdict cross-zero flag is wrong: ' + pair)
            if not v['statement']:
                raise ValueError('Missing verdict statement: ' + pair)

    def _check_counters(self, subsystem, trace, timeline):
        if set(subsystem['totals']) != set(MODES) or set(trace) != set(MODES):
            raise ValueError('Unexpected counter modes')
        if timeline['samples'] != 64 or set(timeline['modes']) != set(MODES):
            raise ValueError('Unexpected timeline shape')
        for mode in MODES:
            totals = subsystem['totals'][mode]
            for key in QUERY_COUNTERS:
                if key not in totals or key not in trace[mode]:
                    raise ValueError('Missing counter: ' + mode + '/' + key)
                if not _close(totals[key], trace[mode][key], tol=1e-6):
                    raise ValueError('Counter totals disagree with the trace: ' + mode + '/' + key)
            for key in TIME_COUNTERS:
                if key not in totals or totals[key] < 0:
                    raise ValueError('Missing timing counter: ' + mode + '/' + key)
            consumers = timeline['modes'][mode]['consumers']
            for key, consumer_key in (('queries', 'queries'), ('base insertions', 'base_insertions'),
                                      ('final type hits', 'final_hits'), ('final type misses', 'final_misses')):
                summed = sum(c[consumer_key] for c in consumers.values())
                if not _close(summed, totals[key]):
                    raise ValueError('Consumer counters do not add up: ' + mode + '/' + key)
        pairs = subsystem['pairs']
        if set(pairs) != set(PAIRS):
            raise ValueError('Unexpected counter comparison pairs')

    def _check_inventory(self, inventory):
        corpus = inventory['corpus']
        if corpus['accepted'] + corpus['rejected'] != corpus['recorded']:
            raise ValueError('Corpus counts do not add up')
        if corpus['accepted'] != 64 or corpus['recorded'] != 76:
            raise ValueError('Unexpected corpus size')
        for pair in PAIRS:
            per_sample = inventory['net_benefit_per_sample'][pair]
            if len(per_sample) != corpus['accepted']:
                raise ValueError('Per-sample net benefit does not cover the corpus: ' + pair)
            for row in per_sample:
                expected = 1 - row['candidate_cpu_mean_s'] / row['baseline_cpu_mean_s']
                if not _close(row['net_benefit'], expected):
                    raise ValueError('Per-sample net benefit is wrong: ' + row['sample'])
            negative = inventory['negative_samples'][pair]
            positive = inventory['positive_samples_count'][pair]
            if len(negative) + positive != corpus['accepted']:
                raise ValueError('Negative and positive sample counts do not add up: ' + pair)
            if len(negative) != sum(1 for r in per_sample if r['net_benefit'] < 0):
                raise ValueError('Negative sample list disagrees with the per-sample data: ' + pair)

    def _check_jvm(self, controlled, production):
        for data, blocks in ((controlled, 15), (production, 10)):
            if data['repeat'] != blocks:
                raise ValueError('Unexpected JVM block count')
            if set(data['pairs']) != set(PAIRS) or set(data['summary']) != set(MODES):
                raise ValueError('Unexpected JVM shape')
            for pair, metrics in data['pairs'].items():
                for metric, d in metrics.items():
                    expected = 1 - d['candidate_total_s'] / d['baseline_total_s']
                    if not _close(d['net_gain'], expected, tol=1e-6):
                        raise ValueError('JVM net gain does not match the totals: ' + pair + '/' + metric)
                    if d['blocks'] != blocks or d['ci95_low'] > d['ci95_high']:
                        raise ValueError('Invalid JVM interval: ' + pair + '/' + metric)
            for mode in MODES:
                summary = data['summary'][mode]
                for metric in JVM_METRICS:
                    if metric not in summary:
                        raise ValueError('Missing JVM metric: ' + mode + '/' + metric)
                    s = summary[metric]
                    if len(s['values_s']) != blocks or s['n'] != blocks:
                        raise ValueError('JVM summary does not cover every block: ' + mode)
                if summary.get('ok') != blocks:
                    raise ValueError('JVM summary does not cover every block: ' + mode)
        if controlled['group'] != 'controlled' or production['group'] != 'production':
            raise ValueError('Unexpected JVM group names')

    def _check_jtreg(self):
        summary = self.files['jvm/jtreg/report/text/summary.txt'].read_text()
        stats = self.files['jvm/jtreg/report/text/stats.txt'].read_text()
        if 'Passed. Execution successful' not in summary:
            raise ValueError('jtreg test did not pass')
        if 'passed: 1' not in stats:
            raise ValueError('Unexpected jtreg statistics')
        time_stats = self.files['jvm/jtreg/report/text/timeStats.txt'].read_text()
        return dict(summary=summary.strip(), stats=stats.strip(), time=time_stats.strip())

    def _read_ab(self):
        values = {}
        for label, name in (('baseline_head', 'baseline_head'), ('current_worktree', 'current_worktree')):
            rows = {}
            for line in self.files['jvm/ab/%s.summary' % name].read_text().splitlines():
                if '=' in line:
                    key, _, value = line.partition('=')
                    rows[key.strip()] = value.strip()
            values[label] = rows
        return values

    @staticmethod
    def _trim_timeline(timeline):
        """Drop the per-sample detail; the aggregate lifecycle numbers are published."""
        trimmed = dict(samples=timeline['samples'], modes={})
        for mode, payload in timeline['modes'].items():
            trimmed['modes'][mode] = {key: value for key, value in payload.items()
                                      if key != 'per_sample'}
        return trimmed

    # --------------------------------------------------------------- access

    def status(self):
        return dict(state='ready', completed=len(self.files), total=len(self.files), errors=[])

    def index(self):
        pass

    def raw(self, name):
        if name not in self.files:
            raise KeyError('Unknown artifact')
        return self.files[name]

    def profile(self, *args):
        raise KeyError('This dataset has no sampled profiles')

    record = profile
