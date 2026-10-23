#!/usr/bin/env python3
"""Build the read-only static site from the frozen experiment dataset."""
from pathlib import Path
import argparse
import json
import shutil
import sys

sys.path.insert(0, str(Path(__file__).parent))
from perfview.data import Dataset, catalog
from perfview.reuse import ReplayDataset
from perfview.stacks import speedscope


def slug(value):
    return ''.join(c if c.isalnum() or c in '._-' else '-' for c in str(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'dist')
    parser.add_argument('--cache', type=Path, default=Path(__file__).parent / '.cache')
    parser.add_argument('--domain')
    parser.add_argument('--reuse-data', type=Path)
    args = parser.parse_args()

    out = args.out
    if (out / ".git").exists():
        raise ValueError("Build into a staging directory, not a Git checkout")
    if out.exists():
        shutil.rmtree(out)
    for name in ('api/artifacts', 'api/profiles', 'api/records', 'api/speedscope'):
        (out / name).mkdir(parents=True, exist_ok=True)
    for name in ('style.css', 'app.js'):
        shutil.copy2(Path(__file__).parent / 'web' / name, out / name)
    source_html = Path(__file__).parent / 'web' / 'index.html'
    (out / 'index.html').write_text(source_html.read_text().replace('data-base=""', 'data-base="."'))

    dataset = Dataset(args.data, args.cache)
    dataset.index()
    status = dataset.status()
    if status['state'] != 'ready':
        raise RuntimeError('dataset indexing failed: ' + '; '.join(status['errors']))

    compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n'
    catalogs = [catalog(dataset)]
    if args.reuse_data:
        reuse = ReplayDataset(args.reuse_data)
        folder = 'experiments/' + reuse.id
        target = out / 'api' / folder
        target.mkdir(parents=True)
        (target / 'overview.json').write_text(compact(reuse.overview))
        (target / 'status.json').write_text(compact(reuse.status()))
        catalogs.append(dict(catalog(reuse), overview_url=folder+'/overview.json',
                             status_url=folder+'/status.json', artifact_prefix=reuse.id+'/'))
        for name, source in reuse.files.items():
            dest = out / 'api/artifacts' / reuse.id / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    (out / 'api/datasets.json').write_text(compact(catalogs))
    (out / 'api/overview.json').write_text(compact(dataset.overview))
    (out / 'api/status.json').write_text(compact(status))
    for name, source in dataset.files.items():
        target = out / 'api/artifacts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def emit(case, mode, run, profile, archive_names=None):
        value = dict(profile)
        if archive_names is not None:
            value['archive_names'] = archive_names
        stem = f'{case}--{mode}--{run}'
        (out / 'api/profiles' / f'{stem}.json').write_text(compact(value))
        export = speedscope(value, f'{case} {mode}')
        (out / 'api/speedscope' / f'{stem}.speedscope.json').write_text(compact(export))

    for (case, mode, run), archive_name in sorted(dataset.members.items()):
        emit(case, mode, run, dataset.profile(case, mode, run), {run: archive_name})
        for kind in ('run.json', 'record.stderr', 'native-self.txt',
                     'native-stats.txt', 'stacks.txt'):
            try:
                value = dataset.record(case, mode, run, kind)
            except KeyError:
                continue
            safe = archive_name.replace('/', '__')
            (out / 'api/records' / f'{safe}__{kind}').write_bytes(value)

    for case in dataset.overview['baseline']:
        for mode in ('origin', 'full', 's0', 's1'):
            emit(case, mode, 'all', dataset.profile(case, mode, 'all'))
    if args.domain:
        (out / 'CNAME').write_text(args.domain + '\n')

    counts = {name: len(list((out / 'api' / name).glob('*')))
              for name in ('profiles', 'records', 'speedscope')}
    print('static site ready:', out)
    print('profiles=%(profiles)d records=%(records)d exports=%(speedscope)d' % counts)


if __name__ == '__main__':
    main()
