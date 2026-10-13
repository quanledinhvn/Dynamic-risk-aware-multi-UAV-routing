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


def sci(p):
    """Format a p-value as LaTeX scientific notation with two significant digits."""
    if p >= 1e-3:
        return f'{p:.3f}'

    mantissa, exponent = f'{p:.1e}'.split('e')

    return f'${mantissa}\\times10^{{{int(exponent)}}}$'


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


def static_difference_figure(pairs):
    differences = defaultdict(list)

    for base, contextual in pairs:
        differences[base['instance']].append(
            float(contextual['objective']) - float(base['objective']))

    means = {Path(name).stem.upper(): st.fmean(values)
             for name, values in differences.items()}
    limit = max(abs(value) for value in means.values()) * 1.2
    panels = []

    for family in ('C', 'R', 'RC'):
        names = sorted(name for name in means
                       if name.rstrip('0123456789') == family)
        coordinates = ' '.join(f'({name},{means[name]:.10f})' for name in names)

        panels.append(
            '\\begin{tikzpicture}\n'
            '\\begin{axis}[width=0.95\\linewidth,height=4cm,'
            'ybar,bar width=4pt,ymin=' + f'{-limit:.8f},ymax={limit:.8f},'
            'symbolic x coords={' + ','.join(names) + '},xtick=data,'
            'xticklabel style={rotate=60,anchor=east,font=\\scriptsize},'
            'yticklabel style={font=\\scriptsize},scaled y ticks=false,'
            'ylabel={$\\Delta F$},title={Nhóm ' + family + '},'
            'title style={font=\\small},ymajorgrids=true,'
            'grid style={gray!20},extra y ticks={0},'
            'extra y tick labels={},extra y tick style={grid=major,'
            'grid style={black!65}},enlarge x limits=0.035]\n'
            '\\addplot[fill=blue!50!black,draw=none] coordinates {'
            + coordinates + '};\n'
            '\\end{axis}\n\\end{tikzpicture}\\par\n')

    (OUT / 'static_differences.tex').write_text('\n'.join(panels))


def static():
    base = read('benchmark/alns/c100_r5_s20_5000/raw.csv')
    ctx = read('benchmark/contextual/c100_r5_s20_5000/raw.csv')
    keyed = [{(r['instance'], int(r['seed'])): r for r in rows} for rows in (base, ctx)]

    assert len(keyed[0]) == len(base) == 1120
    assert len(keyed[1]) == len(ctx) == 1120
    assert keyed[0].keys() == keyed[1].keys()

    rank = lambda r: (int(r['vehicles']), float(r['objective']))
    pairs = [(keyed[0][k], keyed[1][k]) for k in sorted(keyed[0])]
    static_difference_figure(pairs)

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
                s['unserved_priority'] = mean(group, 'unserved_priority')

                s['served_all_percent'] = 100 * sum(int(r['unserved']) == 0 for r in group) / len(group)
                s['static_customers'] = sorted({int(r['static_customers']) for r in group})
                s['seeds'] = sorted({int(r['seed']) for r in group})

                result[label][policy] = s
                short = {'greedy_insert': 'Greedy', 'cold_restart': 'Cold', 'warm_alns': 'Warm'}[policy]
                total = int(group[0]['static_customers']) + arrivals

                lines.append(
                    f"{total}/{arrivals} & {short} & {s['objective']:.4f} & "
                    f"{s['vehicles']:.2f} & {s['unserved']:.2f} & "
                    f"{s['unserved_priority']:.4f} & "
                    f"{s['served_all_percent']:.1f} & "
                    f"{s['runtime_seconds']:.1f}\\\\"
                )

            lines.append('\\addlinespace')

    (OUT / 'dynamic_rows.tex').write_text('\n'.join(lines)+'\n')
    return result


def dynamic_tests():
    tests = []
    lines = []

    for size in (25, 100):
        for arrivals in (5, 12, 25):
            rows = read(f'phase1/results/dynamic_n{size}_d{arrivals}/raw.csv')
            cells = {(r['scenario'], r['seed'], r['policy']): r for r in rows}
            keys = {(r['scenario'], r['seed']) for r in rows}
            level_tests = []
            level_lines = []

            for other in ('greedy_insert', 'cold_restart'):
                pairs = [(cells[s, k, other], cells[s, k, 'warm_alns']) for s, k in sorted(keys)]
                rank = lambda r: (int(r['unserved']), int(r['vehicles']), float(r['objective']))
                by_instance = defaultdict(list)

                for b, w in pairs:
                    by_instance[b['instance']].append(float(b['objective']) - float(w['objective']))

                diffs = [st.fmean(v) for v in by_instance.values()]
                wins = sum(rank(w) < rank(b) for b, w in pairs)
                losses = sum(rank(w) > rank(b) for b, w in pairs)
                ties = len(pairs) - wins - losses

                full_pairs = [
                    (b, w) for b, w in pairs
                    if int(b['unserved']) == 0 and int(w['unserved']) == 0
                ]
                full_delta_f = st.fmean(
                    float(w['objective']) - float(b['objective'])
                    for b, w in full_pairs
                )

                pair_diffs = [
                    float(b['objective']) - float(w['objective']) for b, w in pairs
                ]
                level_tests.append({
                    'size': size, 'arrivals': arrivals, 'other': other,
                    'pairs': len(pairs), 'blocks': len(diffs),
                    'wins': wins, 'losses': losses, 'ties': ties,
                    'full_service_pairs': len(full_pairs),
                    'full_service_mean_warm_minus_other_f': full_delta_f,
                    'delta_f': st.fmean(diffs),
                    'p': float(wilcoxon(diffs, method='auto').pvalue),
                    'pair_p': float(wilcoxon(pair_diffs, method='auto').pvalue),
                })

                total = size + arrivals if size == 25 else 100
                short = 'Greedy' if other == 'greedy_insert' else 'Cold'
                level_lines.append(
                    f"{total}/{arrivals} & Warm--{short} & "
                    f"{wins}/{losses}/{ties} & {len(full_pairs)} & "
                    f"{full_delta_f:.4f}"
                )

            # Pair-level Wilcoxon, Holm-adjusted within the level (two comparisons).
            for item, p, line in zip(
                level_tests, holm([t['pair_p'] for t in level_tests]), level_lines,
                strict=True,
            ):
                item['pair_holm_p'] = p
                lines.append(f"{line} & {sci(p)}\\\\")

            tests.extend(level_tests)
            lines.append('\\addlinespace')

    for item, p in zip(tests, holm([t['p'] for t in tests]), strict=True):
        item['holm_p'] = p

    (OUT / 'dynamic_paired_rows.tex').write_text('\n'.join(lines) + '\n')

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
