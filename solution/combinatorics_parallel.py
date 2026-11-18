# -*- coding: utf-8 -*-
"""
PARCS: паралельне обчислення C(n, k) mod p і P(n, k) mod p (map-reduce).

P(n, k) = n * (n-1) * ... * (n-k+1),  C(n, k) = P(n, k) / k!
Ділення за модулем простого p виконується через малу теорему Ферма:
C = P * (k!)^(p-2) mod p  (k < p, тому k! не ділиться на p).

Майстер ділить індекси [0, k) на рівні діапазони. Кожен воркер рахує для свого
діапазону часткові добутки чисельника і знаменника за модулем p (map), майстер
перемножує їх і рахує C через обернений елемент (reduce). Між вузлами
передаються лише кілька чисел, тому обсяг комунікації не залежить від k.

Вхідний файл: один рядок "n k p" (рядки з # - коментарі).
Код сумісний із Python 2.7 (вузли PARCS) і Python 3.
"""
from __future__ import print_function, division

import io
import time

from Pyro4 import expose

try:
    range = xrange  # у Python 2 range створив би величезний список
except NameError:
    pass


class Solver:

    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name
        self.workers = workers
        print("Inited")

    def solve(self):
        print("Job Started")
        n_workers = len(self.workers)
        print("Workers %d" % n_workers)
        t_start = time.time()

        n, k, p = Solver.read_input(self.input_file_name)

        # map: виклики асинхронні, тому всі воркери рахують одночасно
        ranges = Solver.split(k, n_workers)
        mapped = []
        for i in range(n_workers):
            start, end = ranges[i]
            mapped.append(self.workers[i].mymap(n, p, start, end))

        # reduce: чекаємо всіх воркерів і перемножуємо часткові добутки
        num, den, worker_times = self.myreduce(mapped, p)
        comb, perm = Solver.finish(num, den, p)

        elapsed = time.time() - t_start
        Solver.write_output(self.output_file_name, str(n_workers), n, k, p, comb, perm,
                            elapsed, ranges, worker_times)
        print("Job Finished in %.3f s" % elapsed)

    @staticmethod
    def split(k, n_workers):
        """Рівні діапазони індексів [start, end) для кожного воркера."""
        return [(k * i // n_workers, k * (i + 1) // n_workers) for i in range(n_workers)]

    @staticmethod
    @expose
    def mymap(n, p, start, end):
        """Виконується на воркері; повертає (num_i, den_i, секунди)."""
        t0 = time.time()
        num, den = Solver.partial_products(n, p, start, end)
        return num, den, time.time() - t0

    @staticmethod
    @expose
    def myreduce(mapped, p):
        num = 1
        den = 1
        worker_times = []
        for future in mapped:
            part_num, part_den, seconds = future.value  # .value чекає завершення воркера
            num = num * part_num % p
            den = den * part_den % p
            worker_times.append(seconds)
        return num, den, worker_times

    @staticmethod
    def partial_products(n, p, start, end):
        """num = (n-start)(n-start-1)...(n-end+1), den = (start+1)...end, обидва mod p."""
        num = 1
        den = 1
        if end <= start:
            return num, den
        # два прості цикли швидші за один спільний: значення дає сам range
        for x in range(n - end + 1, n - start + 1):
            num = num * x % p
        for d in range(start + 1, end + 1):
            den = den * d % p
        return num, den

    @staticmethod
    def finish(num, den, p):
        """C = P * den^(p-2) mod p (Ферма), P = num."""
        perm = num % p
        comb = perm * pow(den, p - 2, p) % p
        return comb, perm

    @staticmethod
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

    @staticmethod
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
        if not Solver.is_prime(p):
            raise ValueError("p must be prime")
        return n, k, p

    @staticmethod
    def wilson_check(n, k, p, comb):
        """Якщо n = p-1, то C(p-1, k) = (-1)^k mod p (наслідок теореми Вілсона)."""
        if n != p - 1:
            return "n/a"
        expected = 1 if k % 2 == 0 else p - 1
        return "OK" if comb == expected else "FAIL"

    @staticmethod
    def write_output(file_name, workers_label, n, k, p, comb, perm, elapsed, ranges, worker_times):
        with io.open(file_name, 'w', encoding='utf-8') as f:
            f.write(u"Workers: %s\n" % workers_label)
            f.write(u"n: %d\n" % n)
            f.write(u"k: %d\n" % k)
            f.write(u"p: %d\n" % p)
            f.write(u"C(n,k) mod p: %d\n" % comb)
            f.write(u"P(n,k) mod p: %d\n" % perm)
            f.write(u"Wilson check: %s\n" % Solver.wilson_check(n, k, p, comb))
            f.write(u"Total time: %.3f s\n" % elapsed)
            f.write(u"Worker compute times: %s\n" % u", ".join(u"%.3f" % t for t in worker_times))
            # номер воркера, діапазон індексів [start, end), кількість множень, секунди
            for i in range(len(ranges)):
                start, end = ranges[i]
                f.write(u"Worker %d: %d %d %d %.3f\n" % (i + 1, start, end, end - start, worker_times[i]))
        print("output done")
