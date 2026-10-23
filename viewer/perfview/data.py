"""Read-only dataset discovery and disposable stack indexes."""
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import threading

from .stacks import Symbols, merge, parse
from .methodology import ORIGINAL
from .reuse import ReplayDataset

CACHE_VERSION = '4'
MODES = ('origin', 'full', 's0', 's1')
PROFILE = re.compile(r'^(?:l2/)?profiles/([^/]+)/(origin|full|s0|s1)/(run-\d+)/stacks.txt$')
DIAGNOSTIC = re.compile(r'^diagnostics/quality/([^/]+)/stacks.txt$')


def read_json(path):
    return json.loads(path.read_text())


class NotReady(Exception):
    pass


class Dataset:
    def __init__(self, path, cache_root):
        self.path = Path(path).resolve()
        self.id = self.path.name
        self.manifest = read_json(self.path / 'manifest.json')
        self.attribution = read_json(self.path / 'attribution/summary.json')
        self.archive = self.path / 'run-records.tar.gz'
        digest = hashlib.sha256()
        for p in (self.archive, self.path / 'opt-symbols.gz'):
            with p.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    digest.update(block)
        self.fingerprint = digest.hexdigest()
        self.cache = Path(cache_root) / (self.fingerprint[:20] + '-' + CACHE_VERSION)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.progress = dict(state='waiting', completed=0, total=0, current='', errors=[])
        self.members = {}
        self.indexes = {}
        self.files = {}
        allowed = ['manifest.json', 'quality-summary.json', 'structural-diagnostics.json',
                   'source-context.json', 'perf-data-ledger.json', 'report-tables.md',
                   'correctness.json', 'correctness-l2.json', 'source.patch',
                   'analysis/baseline-summary.json', 'l2-analysis/baseline-summary.json',
                   'analysis/stat-summary.json', 'l2-analysis/stat-summary.json',
                   'attribution/summary.json', 'attribution/attribution.csv',
                   'attribution/consumers.csv', 'attribution/self-top.csv',
                   'annotate/poison.txt', 'annotate/lvi-select.txt', 'annotate/invalidate.txt']
        for key in allowed:
            p = self.path / key
            if p.is_file():
                self.files[key] = p
        report = self.path.parent.parent / 'JavaType-Cache-Perf-Profiling-Execution-2026-10-23.md'
        if report.is_file():
            self.files['execution-report.md'] = report
        self.overview = self._overview()

    def _overview(self):
        baseline, stat = {}, {}
        paired = {}
        for folder in ('analysis', 'l2-analysis'):
            b = read_json(self.path / folder / 'baseline-summary.json')
            baseline.update(b['metrics'])
            paired.update(b.get('paired_s1_user_delta_s', {}))
            stat.update(read_json(self.path / folder / 'stat-summary.json')['metrics'])
        def rows(name):
            with (self.path / 'attribution' / name).open() as f:
                return list(csv.DictReader(f))
        return dict(id=self.id, fingerprint=self.fingerprint, manifest=self.manifest,
                    kind="profiling", label="四策略性能剖析 · 原始六场景", methodology=ORIGINAL,
                    baseline=baseline, stat=stat, paired=paired,
                    attribution=self.attribution, partitions=rows('attribution.csv'),
                    consumers=rows('consumers.csv'),
                    quality=read_json(self.path / 'quality-summary.json'),
                    structural=read_json(self.path / 'structural-diagnostics.json'),
                    sources=read_json(self.path / 'source-context.json'),
                    files=list(self.files))

    def status(self):
        with self.lock:
            return dict(self.progress, errors=list(self.progress['errors']))

    def index(self):
        try:
            self._index()
        except Exception as exc:
            with self.lock:
                self.progress['state'] = 'failed'
                self.progress['errors'].append(str(exc))

    def _index(self):
        # Scan once in archive order: no extraction and no repeated gzip seeking.
        with tarfile.open(self.archive, 'r|gz') as archive:
            symbols = None
            checks = self.overview['quality']['quality_checks']
            total = len(self.attribution['profiles']) + len(checks)
            with self.lock:
                self.progress.update(state='indexing', total=total)
            for member in archive:
                name = member.name.removeprefix('./')
                m = PROFILE.fullmatch(name)
                diagnostic = DIAGNOSTIC.fullmatch(name)
                if not (m or diagnostic) or not member.isfile():
                    continue
                if m:
                    case, mode, run = m.groups()
                else:
                    check = next(c for c in checks if c['tag'] == diagnostic[1])
                    case, mode, run = check['case'], 's1', 'diag:' + check['tag']
                key = (case, mode, run)
                # Case names from the archive are keys, never used as filesystem paths.
                cache = self.cache / (hashlib.sha256(name.encode()).hexdigest() + '.json.gz')
                with self.lock:
                    self.progress['current'] = '/'.join(key)
                try:
                    if cache.exists():
                        # Validate cache before advertising it as available.
                        with gzip.open(cache, 'rt') as f:
                            json.load(f)
                    else:
                        if symbols is None:
                            symbols = Symbols(self.path / 'opt-symbols.gz')
                        # TextIOWrapper calls seekable(), unsupported by tar's
                        # streaming reader on Python 3.14. Decode complete lines.
                        stream = (line.decode('utf-8', errors='replace')
                                  for line in archive.extractfile(member))
                        profile = parse(stream, symbols)
                        expected = next((p for p in self.attribution['profiles']
                                         if (p['case'], p['mode'], p['run']) == key), None)
                        if expected and (profile['period_sum'] != expected['period_sum'] or
                                         len(profile['samples']) != expected['samples']):
                            raise ValueError('Sample or period mismatch against frozen summary: ' + name)
                        temp = cache.with_suffix('.tmp')
                        with gzip.open(temp, 'wt') as f:
                            json.dump(profile, f, separators=(',', ':'))
                        os.replace(temp, cache)
                    with self.lock:
                        self.indexes[key] = cache
                        self.members[key] = name
                except Exception as exc:
                    with self.lock:
                        self.progress['errors'].append(f'{name}: {exc}')
                with self.lock:
                    self.progress['completed'] += 1
        expected_keys = {(p['case'], p['mode'], p['run']) for p in self.attribution['profiles']}
        missing = expected_keys - self.indexes.keys()
        with self.lock:
            if missing:
                self.progress['errors'].append('Missing profiles: ' + str(sorted(missing)))
            self.progress.update(state='ready' if not self.progress['errors'] else 'failed', current='')

    def profile(self, case, mode, run):
        valid = [(p['case'], p['mode'], p['run']) for p in self.attribution['profiles']]
        if run and run.startswith('diag:'):
            valid += [(p['case'], 's1', 'diag:' + p['tag'])
                      for p in self.overview['quality']['quality_checks']]
        keys = [key for key in valid if key[0] == case and key[1] == mode
                and (run == 'all' or key[2] == run)]
        if not keys:
            raise KeyError('Unknown case, mode or run')
        profiles = []
        for key in sorted(keys):
            with self.lock:
                cache = self.indexes.get(key)
                state = self.progress['state']
            if cache is None:
                if state == 'failed':
                    raise ValueError('Profile index failed; see indexing status')
                raise NotReady()
            with gzip.open(cache, 'rt') as stream:
                profiles.append((key[2], json.load(stream)))
        result = merge(profiles)
        result.update(case=case, mode=mode, run=run)
        return result

    def raw(self, key):
        if key not in self.files:
            raise KeyError('Unknown artifact')
        return self.files[key]

    def record(self, case, mode, run, kind):
        if kind not in ('run.json', 'record.stderr', 'native-self.txt', 'native-stats.txt', 'stacks.txt'):
            raise KeyError('Unknown record kind')
        with self.lock:
            stack_name = self.members.get((case, mode, run))
        if stack_name is None:
            # Validate against the catalog and report indexing status consistently.
            self.profile(case, mode, run)
            raise KeyError('Unknown record')
        name = stack_name.rsplit('/', 1)[0] + '/' + kind
        with tarfile.open(self.archive, 'r|gz') as archive:
            for member in archive:
                if member.name.removeprefix('./') == name and member.isfile():
                    return archive.extractfile(member).read()
        raise KeyError('Record is not saved in this dataset')


def discover(paths, cache_root):
    datasets = {}
    for path in paths:
        dataset = (ReplayDataset if (Path(path) / "replay/timings.json").is_file() else Dataset)(path, cache_root)
        if dataset.id in datasets:
            raise ValueError('Dataset names must be unique: ' + dataset.id)
        datasets[dataset.id] = dataset
    return datasets


def catalog(dataset):
    o = dataset.overview
    return dict(id=dataset.id, label=o["label"], kind=o["kind"],
                cases=list(o.get("baseline", o.get("scenarios", {}))), fingerprint=dataset.fingerprint)
