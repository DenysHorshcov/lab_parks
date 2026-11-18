# -*- coding: utf-8 -*-
"""
Підсумок замірів: середній час, прискорення, ефективність і графік speedup.png.

Запуск:  python3 tools/summarize.py results/big/results.csv
Створює поруч із CSV файли summary.md і speedup.png (графік - якщо є matplotlib;
у Cloud Shell:  pip3 install --user matplotlib).

S_seq = T_seq / T_n  - прискорення відносно послідовної версії;
S_1   = T_1 / T_n    - прискорення відносно PARCS з 1 воркером;
E     = S_seq / n    - ефективність.
"""
from __future__ import print_function, division

import csv
import io
import os
import sys
from collections import OrderedDict


def mean(values):
    return sum(values) / len(values)


def stdev(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def fmt(x, digits=2):
    return ("%." + str(digits) + "f") % x


def load(path):
    rows = []
    with io.open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            row['workers'] = int(row['workers'])
            row['total_time_s'] = float(row['total_time_s'])
            rows.append(row)
    return rows


def check(rows):
    """Усі прогони мають дати однакову відповідь, а перевірка Вілсона - не FAIL."""
    problems = []
    answers = set((r['n'], r['k'], r['p'], r['comb'], r['perm']) for r in rows)
    if len(answers) != 1:
        problems.append("different answers in runs: %s" % sorted(answers))
    for r in rows:
        if r['wilson'] == 'FAIL':
            problems.append("Wilson check FAIL in job %s" % r['job_id'])
    return problems


def summarize(rows):
    groups = OrderedDict()
    for r in sorted(rows, key=lambda r: (r['version'] != 'sequential', r['workers'])):
        key = ('sequential', 0) if r['version'] == 'sequential' else ('parallel', r['workers'])
        groups.setdefault(key, []).append(r['total_time_s'])

    t_seq = mean(groups[('sequential', 0)]) if ('sequential', 0) in groups else None
    t_one = mean(groups[('parallel', 1)]) if ('parallel', 1) in groups else None

    table = []
    for (version, workers), times in groups.items():
        t = mean(times)
        s_seq = t_seq / t if t_seq else None
        s_one = t_one / t if t_one and version == 'parallel' else None
        eff = s_seq / workers if s_seq and workers else None
        table.append(OrderedDict([
            ('version', version), ('workers', workers), ('runs', len(times)),
            ('times', times), ('mean', t), ('std', stdev(times)),
            ('s_seq', s_seq), ('s_one', s_one), ('eff', eff),
        ]))
    return table


def to_markdown(table, rows):
    r0 = rows[0]
    lines = [
        "Задача: n = %s, k = %s, p = %s" % (r0['n'], r0['k'], r0['p']),
        "",
        "Відповідь: C(n,k) mod p = %s, P(n,k) mod p = %s, перевірка Вілсона: %s"
        % (r0['comb'], r0['perm'], r0['wilson']),
        "",
        "| Версія | Воркерів | Прогони, с | Середній час, с | σ, с | Прискорення S = T_seq/T_n | S₁ = T₁/T_n | Ефективність E = S/n |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in table:
        name = "Послідовна" if row['version'] == 'sequential' else "PARCS"
        workers = "—" if row['version'] == 'sequential' else str(row['workers'])
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            name, workers,
            "; ".join(fmt(t) for t in row['times']),
            fmt(row['mean']), fmt(row['std']),
            fmt(row['s_seq']) if row['s_seq'] is not None else "1,00" if row['version'] == 'sequential' else "—",
            fmt(row['s_one']) if row['s_one'] is not None else "—",
            "%d %%" % round(row['eff'] * 100) if row['eff'] is not None else "—",
        ))
    return "\n".join(lines).replace(".", ",") + "\n"


def plot(table, path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed, speedup.png skipped (pip3 install --user matplotlib)")
        return False
    par = [r for r in table if r['version'] == 'parallel' and r['s_seq'] is not None]
    if not par:
        print("No sequential baseline or parallel runs, speedup.png skipped")
        return False
    xs = [r['workers'] for r in par]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.plot(xs, [r['s_seq'] for r in par], 'o-', label='PARCS (виміряно)')
    ax1.plot([0] + xs, [0] + xs, '--', color='gray', label='ідеальне S = n')
    ax1.set_xlabel('Кількість воркерів n')
    ax1.set_ylabel('Прискорення S = T_seq / T_n')
    ax1.set_xticks(xs)
    ax1.grid(alpha=0.3)
    ax1.legend()
    ax2.bar([str(x) for x in xs], [r['mean'] for r in par], yerr=[r['std'] for r in par], capsize=4,
            label='PARCS')
    seq = [r for r in table if r['version'] == 'sequential']
    if seq:
        ax2.axhline(seq[0]['mean'], color='red', linestyle='--', label='послідовна')
    ax2.set_xlabel('Кількість воркерів n')
    ax2.set_ylabel('Середній час, с')
    ax2.grid(alpha=0.3, axis='y')
    ax2.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    return True


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')  # консоль Windows не вміє друкувати σ і ₁
    if len(sys.argv) < 2:
        print("Usage: python3 tools/summarize.py results/big/results.csv")
        return 1
    path = sys.argv[1]
    rows = load(path)
    if not rows:
        print("No rows in %s" % path)
        return 1
    problems = check(rows)
    for p in problems:
        print("WARNING: %s" % p)
    table = summarize(rows)
    md = to_markdown(table, rows)
    folder = os.path.dirname(os.path.abspath(path))
    with io.open(os.path.join(folder, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    print(md)
    if plot(table, os.path.join(folder, 'speedup.png')):
        print("Saved %s" % os.path.join(folder, 'speedup.png'))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
