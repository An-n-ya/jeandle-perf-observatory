"""Read saved perf script text without inventing time or missing symbols."""
import bisect
import collections
import gzip
import re

from .classify import classify

HEADER = re.compile(r"^(\S+)\s+(\d+)\s+([\d.]+):\s+(\d+)\s+(.+):\s*$")
FRAME = re.compile(r"^\s+([a-fA-F0-9]+)\s+(.+)$")


class Symbols:
    def __init__(self, path):
        self.rows = []
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                m = re.match(r'([0-9a-f]+) ([0-9a-f]+) ([tTwW]) (.*)', line)
                if m:
                    self.rows.append((int(m[1], 16), int(m[2], 16), m[4]))
        self.rows.sort()
        self.addresses = [row[0] for row in self.rows]
        self.start = next(row[0] for row in self.rows if row[2] == '_start')

    def lookup(self, address):
        i = bisect.bisect_right(self.addresses, address) - 1
        if i < 0:
            return ''
        start, size, name = self.rows[i]
        return name if start <= address < start + size else ''


def parse(stream, symbols):
    samples, current = [], None
    for line in stream:
        m = HEADER.match(line.rstrip())
        if m:
            if current:
                samples.append(current)
            current = dict(comm=m[1], event=m[5], period=int(m[4]),
                           time=float(m[3]), frames=[])
        elif current:
            m = FRAME.match(line.rstrip())
            if m:
                raw = m[2]
                inline = raw.endswith(' (inlined)')
                raw = re.sub(r' \((?:inlined|/.*|\[.*)\)$', '', raw)
                offset = re.search(r'\+0x([0-9a-f]+)$', raw)
                current['frames'].append(dict(
                    ip=int(m[1], 16), inline=inline,
                    offset=int(offset[1], 16) if offset else 0,
                    name=re.sub(r'\+0x[0-9a-f]+$', '', raw)))
    if current:
        samples.append(current)
    samples = [s for s in samples if s['comm'] == 'opt' and s['event'] == 'cpu_atom/cycles/u']
    roots = collections.Counter(f['ip'] - f['offset'] - symbols.start
                               for s in samples for f in s['frames'] if f['name'] == '_start')
    base = roots.most_common(1)[0][0] if roots else None
    frames, frame_ids, result = [], {}, []
    for sample in samples:
        for frame in sample['frames']:
            frame['native'] = symbols.lookup(frame['ip'] - base) if base is not None else ''
        info = classify(sample)
        stack = []
        # Keep recursive occurrences in their original order in the stack.
        for f in reversed(sample['frames']):
            key = (f['name'], f['native'], f['inline'])
            if key not in frame_ids:
                frame_ids[key] = len(frames)
                frames.append(dict(name=f['name'], native=f['native'], inline=f['inline']))
            stack.append(frame_ids[key])
        if not stack:
            key = ('[missing]', '', False)
            if key not in frame_ids:
                frame_ids[key] = len(frames)
                frames.append(dict(name='[missing]', native='', inline=False))
            stack.append(frame_ids[key])
        result.append(dict(stack=stack, weight=sample['period'], time=sample['time'],
                           category=info['group'], consumer=info['consumer'],
                           flags=[k for k, v in info.items() if v is True]))
    return dict(frames=frames, samples=result, image_base_known=base is not None,
                period_sum=sum(s['weight'] for s in result))


def merge(profiles):
    frames, ids, samples, runs = [], {}, [], []
    for label, profile in profiles:
        mapping = {}
        for i, frame in enumerate(profile['frames']):
            key = (frame['name'], frame['native'], frame['inline'])
            if key not in ids:
                ids[key] = len(frames)
                frames.append(frame)
            mapping[i] = ids[key]
        for sample in profile['samples']:
            samples.append(dict(sample, stack=[mapping[i] for i in sample['stack']], run=label))
        runs.append(dict(run=label, samples=len(profile['samples']), period_sum=profile['period_sum'],
                         image_base_known=profile['image_base_known']))
    return dict(frames=frames, samples=samples, runs=runs,
                period_sum=sum(s['weight'] for s in samples))


def function_costs(profile):
    """Inclusive costs count a recursive frame once per sample."""
    inclusive, self_cost = collections.Counter(), collections.Counter()
    for sample in profile['samples']:
        for frame in set(sample['stack']):
            inclusive[frame] += sample['weight']
        self_cost[sample['stack'][-1]] += sample['weight']
    return [dict(id=i, inclusive=inclusive[i], self=self_cost[i]) for i in inclusive]


def speedscope(profile, name):
    runs = collections.defaultdict(list)
    for sample in profile['samples']:
        runs[sample.get('run', 'run-00')].append(sample)
    return {
        '$schema': 'https://www.speedscope.app/file-format-schema.json',
        'name': name + ' — sampled CPU cycles (not elapsed time)',
        'shared': {'frames': [{'name': f['name'] + (' [inlined]' if f['inline'] else '')}
                              for f in profile['frames']]},
        'profiles': [dict(type='sampled', name=f'{name} / {run} / cycles-weighted',
                          unit='none', startValue=0,
                          endValue=sum(s['weight'] for s in samples),
                          samples=[s['stack'] for s in samples],
                          weights=[s['weight'] for s in samples])
                     for run, samples in runs.items()],
        'activeProfileIndex': 0, 'exporter': 'Jeandle Perf Observatory',
    }
