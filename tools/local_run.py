# -*- coding: utf-8 -*-
"""
Локальний запуск PARCS-рішення без кластера — лише для перевірки логіки.
Воркери імітуються процесами (multiprocessing), Pyro4 підміняється заглушкою.
Час звідси у звіт НЕ йде: заміри беруться тільки з кластера Google Cloud.

Запуск:  python tools/local_run.py input/small.txt output.txt [кількість_воркерів]
"""
from __future__ import print_function

import os
import sys
import types
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def install_fake_pyro4():
    """PARCS позначає методи воркера декоратором Pyro4.expose; локально він нічого не робить."""
    if 'Pyro4' not in sys.modules:
        fake = types.ModuleType('Pyro4')
        fake.expose = lambda f: f
        sys.modules['Pyro4'] = fake


install_fake_pyro4()
sys.path.insert(0, os.path.join(ROOT, 'solution'))
from combinatorics_parallel import Solver  # noqa: E402


def _call_mymap(args):
    return Solver.mymap(*args)


class Future(object):
    """Як у PARCS: результат воркера читається через .value."""

    def __init__(self, async_result):
        self._result = async_result

    @property
    def value(self):
        return self._result.get()


class LocalWorker(object):
    def __init__(self, pool):
        self.pool = pool

    def mymap(self, *args):
        return Future(self.pool.apply_async(_call_mymap, (args,)))


class SyncFuture(object):
    def __init__(self, value):
        self.value = value


class SyncWorker(object):
    """Воркер без окремого процесу: для тестів."""

    def mymap(self, *args):
        return SyncFuture(Solver.mymap(*args))


def run(input_file, output_file, n_workers, use_processes=True):
    if use_processes:
        pool = Pool(n_workers)
        try:
            Solver([LocalWorker(pool) for _ in range(n_workers)], input_file, output_file).solve()
        finally:
            pool.close()
            pool.join()
    else:
        Solver([SyncWorker() for _ in range(n_workers)], input_file, output_file).solve()


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/local_run.py input.txt output.txt [workers]")
        return 1
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    run(sys.argv[1], sys.argv[2], workers)
    return 0


if __name__ == '__main__':
    sys.exit(main())
