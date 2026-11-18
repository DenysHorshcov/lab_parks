# -*- coding: utf-8 -*-
"""
Тести правильності обох версій (Python 3.8+, бо потрібні math.comb і math.perm).
Запуск із кореня репозиторію:  python -m unittest discover -s tests -v
"""
import io
import math
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'solution'))

import local_run  # noqa: E402  (ставить заглушку Pyro4)
import combinatorics_sequential as seq  # noqa: E402
from combinatorics_parallel import Solver  # noqa: E402

PRIMES = [2, 3, 5, 7, 13, 101, 1009, 1000000007, 998244353, 2 ** 61 - 1]
WORKER_COUNTS = [1, 2, 3, 4, 7, 50]


def parse_output(path):
    result = {}
    with io.open(path, encoding='utf-8') as f:
        for line in f:
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
    return result


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def write_input(self, text):
        path = os.path.join(self.tmp.name, 'input.txt')
        with io.open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return path


def random_cases(count=200, seed=1):
    rnd = random.Random(seed)
    cases = []
    for _ in range(count):
        p = rnd.choice(PRIMES)
        n = rnd.randrange(0, min(p, 300))
        k = rnd.randrange(0, n + 1)
        cases.append((n, k, p))
    return cases


class SequentialTest(unittest.TestCase):
    def test_against_math(self):
        for n, k, p in random_cases():
            comb, perm = seq.compute(n, k, p)
            self.assertEqual(comb, math.comb(n, k) % p, (n, k, p))
            self.assertEqual(perm, math.perm(n, k) % p, (n, k, p))

    def test_edges(self):
        self.assertEqual(seq.compute(0, 0, 7), (1, 1))
        self.assertEqual(seq.compute(6, 0, 7), (1, 1))
        self.assertEqual(seq.compute(6, 6, 7), (1, math.factorial(6) % 7))

    def test_wilson(self):
        p = 1000003
        for k in [0, 1, 2, 3, 10, 999, 1000, p - 2, p - 1]:
            comb, _ = seq.compute(p - 1, k, p)
            self.assertEqual(comb, (-1) ** k % p, k)
            self.assertEqual(seq.wilson_check(p - 1, k, p, comb), "OK")


class ParallelTest(unittest.TestCase):
    def run_parallel(self, n, k, p, workers):
        ranges = Solver.split(k, workers)
        futures = [local_run.SyncFuture(Solver.mymap(n, p, s, e)) for s, e in ranges]
        num, den, times = Solver.myreduce(futures, p)
        self.assertEqual(len(times), workers)
        return Solver.finish(num, den, p)

    def test_split_covers_range(self):
        for k in [0, 1, 5, 49, 50, 51, 1000]:
            for w in WORKER_COUNTS:
                ranges = Solver.split(k, w)
                self.assertEqual(len(ranges), w)
                self.assertEqual(ranges[0][0], 0)
                self.assertEqual(ranges[-1][1], k)
                for (a, b), (c, d) in zip(ranges, ranges[1:]):
                    self.assertEqual(b, c)
                sizes = [e - s for s, e in ranges]
                self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_against_math_all_worker_counts(self):
        for n, k, p in random_cases(80, seed=2):
            for w in WORKER_COUNTS:
                comb, perm = self.run_parallel(n, k, p, w)
                self.assertEqual(comb, math.comb(n, k) % p, (n, k, p, w))
                self.assertEqual(perm, math.perm(n, k) % p, (n, k, p, w))

    def test_same_as_sequential_big_p(self):
        p = 2 ** 61 - 1
        n, k = p - 1, 20001
        expected = seq.compute(n, k, p)
        self.assertEqual(expected[0], p - 1)  # Вілсон: k непарне -> -1
        for w in WORKER_COUNTS:
            self.assertEqual(self.run_parallel(n, k, p, w), expected, w)

    def test_is_prime(self):
        small = [m for m in range(2, 2000) if all(m % d for d in range(2, int(m ** 0.5) + 1))]
        self.assertEqual([m for m in range(2000) if Solver.is_prime(m)], small)
        self.assertTrue(Solver.is_prime(2 ** 61 - 1))
        self.assertFalse(Solver.is_prime(2 ** 61 + 1))
        self.assertFalse(Solver.is_prime(3215031751))  # сильне псевдопросте за основами 2, 3, 5, 7


class FilesTest(TempDir):
    def test_parallel_solver_end_to_end(self):
        inp = self.write_input("# comment\n\n50 20 101  # inline comment\n")
        for w in WORKER_COUNTS:
            out = os.path.join(self.tmp.name, 'out_%d.txt' % w)
            local_run.run(inp, out, w, use_processes=False)
            data = parse_output(out)
            self.assertEqual(data['Workers'], str(w))
            self.assertEqual(int(data['C(n,k) mod p']), math.comb(50, 20) % 101)
            self.assertEqual(int(data['P(n,k) mod p']), math.perm(50, 20) % 101)
            self.assertEqual(len(data['Worker compute times'].split(',')), w)

    def test_parallel_with_processes(self):
        inp = self.write_input("1000002 4000 1000003\n")
        out = os.path.join(self.tmp.name, 'out.txt')
        local_run.run(inp, out, 3, use_processes=True)
        data = parse_output(out)
        self.assertEqual(data['C(n,k) mod p'], '1')
        self.assertEqual(data['Wilson check'], 'OK')

    def test_sequential_file(self):
        inp = self.write_input("20 7 1000000007\n")
        out = os.path.join(self.tmp.name, 'out.txt')
        seq.run(inp, out)
        data = parse_output(out)
        self.assertEqual(data['Workers'], 'sequential')
        self.assertEqual(data['C(n,k) mod p'], '77520')
        self.assertEqual(data['P(n,k) mod p'], '390700800')

    def test_repo_inputs_are_valid(self):
        for name in os.listdir(os.path.join(ROOT, 'input')):
            n, k, p = seq.read_input(os.path.join(ROOT, 'input', name))
            self.assertEqual((n, k, p), Solver.read_input(os.path.join(ROOT, 'input', name)))

    def test_bad_input(self):
        bad = [
            "",                      # порожньо
            "1 2\n",                 # два числа
            "1 2 3 4\n",             # чотири числа
            "5 3 7\n5 3 7\n",        # два рядки
            "a b c\n",               # не числа
            "5 6 7\n",               # k > n
            "5 -1 7\n",              # k < 0
            "7 3 7\n",               # n >= p
            "5 3 9\n",               # p не просте
            "5 3 1\n",               # p = 1
        ]
        for text in bad:
            path = self.write_input(text)
            with self.assertRaises(ValueError, msg=repr(text)):
                seq.read_input(path)
            with self.assertRaises(ValueError, msg=repr(text)):
                Solver.read_input(path)


if __name__ == '__main__':
    unittest.main()
