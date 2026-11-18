# -*- coding: utf-8 -*-
"""
Послідовна версія: C(n, k) mod p і P(n, k) mod p одним циклом, O(k).
Формат вхідних і вихідних файлів той самий, що й у паралельній версії.

Два способи запуску:
  1) з командного рядка:   python combinatorics_sequential.py input.txt [output.txt]
  2) як задача PARCS: клас Solver ігнорує воркерів і рахує все на майстрі.
     Так послідовна версія міряється на такій самій VM і тим самим Python 2.7,
     що й паралельна.

Файл самодостатній (не імпортує паралельну версію і Pyro4).
Код сумісний із Python 2.7 (вузли PARCS) і Python 3.
"""
from __future__ import print_function, division

import io
import sys
import time

try:
    range = xrange  # у Python 2 range створив би величезний список
except NameError:
    pass


def compute(n, k, p):
    """Повертає (C(n,k) mod p, P(n,k) mod p)."""
    num = 1
    den = 1
    # той самий цикл, що й у воркера паралельної версії, але на всьому [0, k)
    for x in range(n - k + 1, n + 1):
        num = num * x % p
    for d in range(1, k + 1):
        den = den * d % p
    perm = num % p
    comb = perm * pow(den, p - 2, p) % p  # мала теорема Ферма
    return comb, perm


def is_prime(m):
    """Міллер-Рабін; з цими основами детермінований для m < 3.3e24."""
    if m < 2:
        return False
    bases = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for b in bases:
        if m % b == 0:
            return m == b
    d = m - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in bases:
        x = pow(a, d, m)
        if x == 1 or x == m - 1:
            continue
        for _ in range(s - 1):
            x = x * x % m
            if x == m - 1:
                break
        else:
            return False
    return True


def read_input(file_name):
    with io.open(file_name, 'r', encoding='utf-8') as f:
        lines = [line.split('#')[0].strip() for line in f]
    lines = [line for line in lines if line]
    if len(lines) != 1:
        raise ValueError("Expected exactly one line: n k p")
    parts = lines[0].split()
    if len(parts) != 3:
        raise ValueError("Expected three integers: n k p")
    n, k, p = [int(x) for x in parts]
    if not 0 <= k <= n:
        raise ValueError("Expected 0 <= k <= n")
    if n >= p:
        raise ValueError("Expected n < p")
    if not is_prime(p):
        raise ValueError("p must be prime")
    return n, k, p


def wilson_check(n, k, p, comb):
    """Якщо n = p-1, то C(p-1, k) = (-1)^k mod p (наслідок теореми Вілсона)."""
    if n != p - 1:
        return "n/a"
    expected = 1 if k % 2 == 0 else p - 1
    return "OK" if comb == expected else "FAIL"


def run(input_file, output_file):
    t_start = time.time()
    n, k, p = read_input(input_file)
    comb, perm = compute(n, k, p)
    elapsed = time.time() - t_start
    with io.open(output_file, 'w', encoding='utf-8') as f:
        f.write(u"Workers: sequential\n")
        f.write(u"n: %d\n" % n)
        f.write(u"k: %d\n" % k)
        f.write(u"p: %d\n" % p)
        f.write(u"C(n,k) mod p: %d\n" % comb)
        f.write(u"P(n,k) mod p: %d\n" % perm)
        f.write(u"Wilson check: %s\n" % wilson_check(n, k, p, comb))
        f.write(u"Total time: %.3f s\n" % elapsed)
        f.write(u"Worker compute times: \n")
    print("Total time: %.3f s" % elapsed)
    return elapsed


class Solver:
    """Обгортка для PARCS: рахує на майстрі, воркери не використовуються."""

    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name
        self.workers = workers
        print("Inited")

    def solve(self):
        print("Job Started (sequential)")
        elapsed = run(self.input_file_name, self.output_file_name)
        print("Job Finished in %.3f s" % elapsed)


def main():
    if len(sys.argv) < 2:
        print("Usage: python combinatorics_sequential.py input.txt [output.txt]")
        return 1
    output = sys.argv[2] if len(sys.argv) > 2 else 'output_sequential.txt'
    run(sys.argv[1], output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
