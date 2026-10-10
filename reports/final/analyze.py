"""Rebuild report evidence from archived CSVs; no solver runs are performed."""
import csv
import hashlib
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import scipy
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'generated'
SOURCES = {}


def read(relative):
    path = ROOT / relative
    SOURCES[relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def mean(rows, field):
    return st.fmean(float(r[field]) for r in rows)


def grouped(rows, key):
    result = defaultdict(list)

    for row in rows:
        result[row[key]].append(row)

    return result


def holm(values):
    adjusted = [0.0] * len(values)
    running = 0.0

    for rank, index in enumerate(sorted(range(len(values)), key=values.__getitem__)):
        running = max(running, (len(values) - rank) * values[index])
        adjusted[index] = min(1.0, running)

    return adjusted


def summary(rows):
    return {field: mean(rows, field) for field in
            ('vehicles', 'distance', 'risk_delay', 'objective', 'runtime_seconds')} | {
        'runs': len(rows),
        'feasible_percent': 100 * sum(r['feasible'] == 'True' for r in rows) / len(rows),
        'objective_std': st.stdev(float(r['objective']) for r in rows),
        'within_instance_objective_sd': st.fmean(
            st.stdev(float(r['objective']) for r in group)
            for group in grouped(rows, 'instance').values()),
    }


def static():
    base = read('benchmark/alns/c100_r5_s20_5000/raw.csv')
    ctx = read('benchmark/contextual/c100_r5_s20_5000/raw.csv')
    keyed = [{(r['instance'], int(r['seed'])): r for r in rows} for rows in (base, ctx)]

    assert len(keyed[0]) == len(base) == 1120
    assert len(keyed[1]) == len(ctx) == 1120
    assert keyed[0].keys() == keyed[1].keys()

    rank = lambda r: (int(r['vehicles']), float(r['objective']))
    pairs = [(keyed[0][k], keyed[1][k]) for k in sorted(keyed[0])]
    wins = sum(rank(c) < rank(b) for b, c in pairs)
    losses = sum(rank(c) > rank(b) for b, c in pairs)

    tests = []

    for field in ('vehicles', 'objective', 'risk_delay'):
        bm = {k: mean(v, field) for k, v in grouped(base, 'instance').items()}
        cm = {k: mean(v, field) for k, v in grouped(ctx, 'instance').items()}
        diffs = [bm[k] - cm[k] for k in sorted(bm)]

        tests.append({'field': field, 'pairs': len(diffs), 'mean_base_minus_ctx': st.fmean(diffs),
                      'median_base_minus_ctx': st.median(diffs),
                      'p': float(wilcoxon(diffs, alternative='two-sided', method='auto').pvalue)})

    for item, p in zip(tests, holm([t['p'] for t in tests]), strict=True):
        item['holm_p'] = p

    result = {'ALNS': summary(base), 'Contextual': summary(ctx), 'tests': tests,
              'wins_losses_ties': [wins, losses, len(pairs)-wins-losses]}
    lines = []

    for name, rows in [('ALNS', base), ('Contextual ALNS', ctx)]:
        s = summary(rows)
        lines.append(f"{name} & {s['vehicles']:.2f} & {s['distance']:.2f} & {s['risk_delay']:.4f} & {s['objective']:.4f} & {s['runtime_seconds']:.1f} & {s['feasible_percent']:.0f}\\\\")

    (OUT / 'static_rows.tex').write_text('\n'.join(lines)+'\n')
    return result


def dynamic():
    result = {}
    lines = []

    for size in (25, 100):
        for arrivals in (5, 12, 25):
            label = f'dynamic_n{size}_d{arrivals}'
            rows = read(f'phase1/results/{label}/raw.csv')
            policies = grouped(rows, 'policy')
            keys = {(r['scenario'], r['seed'], r['policy']) for r in rows}

            assert len(keys) == len(rows)
            assert len({r['scenario'] for r in rows}) == 90

            result[label] = {}

            for policy in ('greedy_insert', 'cold_restart', 'warm_alns'):
                group = policies[policy]
                assert len(group) == (900 if size == 25 else 270)
                s = summary(group)
                s['unserved'] = mean(group, 'unserved')

                s['served_all_percent'] = 100 * sum(int(r['unserved']) == 0 for r in group) / len(group)
                s['static_customers'] = sorted({int(r['static_customers']) for r in group})
                s['seeds'] = sorted({int(r['seed']) for r in group})

                result[label][policy] = s
                short = {'greedy_insert': 'Greedy', 'cold_restart': 'Cold', 'warm_alns': 'Warm'}[policy]
                total = int(group[0]['static_customers']) + arrivals

                lines.append(f"{total}/{arrivals} & {short} & {s['objective']:.4f} & {s['vehicles']:.2f} & {s['unserved']:.2f} & {s['served_all_percent']:.1f} & {s['runtime_seconds']:.1f}\\\\")

            lines.append('\\addlinespace')

    (OUT / 'dynamic_rows.tex').write_text('\n'.join(lines)+'\n')
    return result


def dynamic_tests():
    tests = []

    for size in (25, 100):
        for arrivals in (5, 12, 25):
            rows = read(f'phase1/results/dynamic_n{size}_d{arrivals}/raw.csv')
            cells = {(r['scenario'], r['seed'], r['policy']): r for r in rows}
            keys = {(r['scenario'], r['seed']) for r in rows}

            for other in ('greedy_insert', 'cold_restart'):
                pairs = [(cells[s, k, other], cells[s, k, 'warm_alns']) for s, k in sorted(keys)]
                rank = lambda r: (int(r['unserved']), int(r['vehicles']), float(r['objective']))
                by_instance = defaultdict(list)

                for b, w in pairs:
                    by_instance[b['instance']].append(float(b['objective']) - float(w['objective']))

                diffs = [st.fmean(v) for v in by_instance.values()]
                tests.append({'size': size, 'arrivals': arrivals, 'other': other,
                              'pairs': len(pairs), 'blocks': len(diffs),
                              'wins': sum(rank(w) < rank(b) for b, w in pairs),
                              'losses': sum(rank(w) > rank(b) for b, w in pairs),
                              'delta_f': st.fmean(diffs),
                              'p': float(wilcoxon(diffs, method='auto').pvalue)})

    for item, p in zip(tests, holm([t['p'] for t in tests]), strict=True):
        item['holm_p'] = p

    return tests


def sensitivity():
    result = {}

    for name in ('base', 'budget_100', 'budget_250', 'budget_1000', 'epoch_0.025',
                 'epoch_0.1', 'epoch_0.2', 'trigger_event', 'trigger_hybrid'):
        rows = read(f'phase1/results/ablation/{name}/raw.csv')
        result[name] = {'runs': len(rows), 'F': mean(rows, 'objective'),
                        'unserved': mean(rows, 'unserved'),
                        'served_all': 100 * sum(int(r['unserved']) == 0 for r in rows) / len(rows),
                        'runtime': mean(rows, 'runtime_seconds')}

    return result


def nsga():
    rows = read('benchmark/nsga/c100_r5_s10_35/nsga3_pareto_raw.csv')
    groups = defaultdict(list)

    for row in rows:
        groups[row['instance'], row['seed']].append(row)

    return {'runs': len(groups), 'pareto_rows': len(rows),
            'mean_archive_size': st.fmean(len(g) for g in groups.values()),
            'mean_runtime': st.fmean(float(g[0]['runtime_seconds']) for g in groups.values()),
            'min_vehicles_mean': st.fmean(min(float(r['vehicles']) for r in g) for g in groups.values())}


def main():
    OUT.mkdir(exist_ok=True)
    results = {'static': static(), 'dynamic': dynamic(), 'nsga': nsga(), 'dynamic_tests': dynamic_tests(), 'sensitivity': sensitivity()}

    results['analysis_environment'] = {'python': sys.version, 'scipy': scipy.__version__}
    results['source_sha256'] = SOURCES
    (OUT / 'evidence.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({k: v for k, v in results.items() if k != 'dynamic'}, indent=2))


if __name__ == '__main__':
    main()
