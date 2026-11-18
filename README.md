# Комбінаторика на PARCS: C(n, k) і P(n, k) за модулем p

Лабораторна робота 1 з курсу «Хмарні обчислення»: система [PARCS-Python](https://github.com/Hummer12007/parcs-python) у Google Cloud і паралельне (map-reduce) обчислення біноміального коефіцієнта C(n, k) mod p та кількості розміщень P(n, k) mod p.

## Ідея

P(n, k) = n·(n−1)·…·(n−k+1), C(n, k) = P(n, k) / k!. Ділення за модулем простого p замінюється множенням на обернений елемент: C = P · (k!)^(p−2) mod p (мала теорема Ферма; k < p, тому k! не ділиться на p).

- **Послідовна версія:** один прохід по i = 0…k−1, складність O(k).
- **Паралельна версія:** майстер ділить індекси [0, k) на W рівних діапазонів (**map**): воркер рахує часткові добутки чисельника і знаменника за модулем p і повертає 2 числа та свій час. Майстер перемножує їх і застосовує Ферма (**reduce**). Комунікація — кілька чисел, не залежить від k; кожне множення коштує однаково, тому статичного рівномірного поділу досить.
- **Перевірка правильності:** тести проти `math.comb`/`math.perm`; для великих даних n = p−1, тоді за теоремою Вілсона C(p−1, k) ≡ (−1)^k (mod p) — відповідь відома наперед і перевіряється в кожному вихідному файлі (`Wilson check: OK`). Простота p перевіряється тестом Міллера–Рабіна.

## Результати

Заміри виконуються на кластері Google Cloud (див. [docs/report.md](docs/report.md)). Після замірів тут з'являться таблиця з `results/big/summary.md` і графік `results/big/speedup.png`.

## Структура

| Шлях | Призначення |
|---|---|
| `solution/combinatorics_parallel.py` | паралельна версія для PARCS (Python 2.7 і 3) |
| `solution/combinatorics_sequential.py` | послідовна версія: з командного рядка і як задача PARCS на майстрі |
| `input/small.txt` | малі дані для демо: C(20,7) = 77520 |
| `input/wilson.txt` | n = p−1, відповідь відома (1) |
| `input/big.txt` | дані для замірів: p = 2^61−1, n = p−1, k підбирається калібруванням |
| `tests/test_combinatorics.py` | тести обох версій |
| `tools/local_run.py` | локальний запуск PARCS-рішення без кластера (лише перевірка логіки) |
| `tools/gcp_up.sh`, `tools/gcp_down.sh` | створення й видалення кластера (з Cloud Shell) |
| `tools/gcp_firewall.sh` | доступ до порту 8080 лише з Cloud Shell і твоєї IP |
| `tools/calibrate.sh` | підбір k для `big.txt` на кластері |
| `tools/run_measurements.sh` | серія замірів через API майстра → `results.csv` |
| `tools/summarize.py` | таблиця, прискорення, ефективність, `speedup.png` |
| `docs/report.md`, `docs/presentation.md` | звіт і план презентації |

Формат вхідного файлу: один рядок `n k p` (0 ≤ k ≤ n < p, p — просте), рядки з `#` — коментарі.

## Запуск

### Локально (лише перевірка правильності, без Google)

```bash
python -m unittest discover -s tests -v
python solution/combinatorics_sequential.py input/small.txt output.txt
python tools/local_run.py input/wilson.txt output.txt 4
```

### У Google Cloud — усе з Cloud Shell

Усе, що стосується Google, робиться в **Google Cloud Shell** (кнопка `>_` у консолі): `gcloud` там уже є, локально нічого ставити не треба.

```bash
git clone https://github.com/DenysHorshcov/lab_parks && cd lab_parks
bash tools/gcp_up.sh PROJECT_ID 4 europe-central2-a ТВОЯ_IP   # ТВОЯ_IP: https://ifconfig.me на своєму ПК
MASTER=http://$(cat .master_ip):8080                            # через 2-3 хв відкрий $MASTER/workers
bash tools/calibrate.sh $MASTER 10000000 30000000                # підбір k для ~60 с
nano input/big.txt                                               # вписати парне k
nohup bash tools/run_measurements.sh $MASTER input/big.txt results/big 3 "seq 1 2 4" > measure.log 2>&1 &
tail -f measure.log                                              # чекати DONE
pip3 install --user matplotlib; python3 tools/summarize.py results/big/results.csv
bash tools/gcp_down.sh PROJECT_ID europe-central2-a              # ОДРАЗУ видалити кластер
```

Якщо Cloud Shell перепідключився (змінилась його IP-адреса) і майстер перестав відповідати: `bash tools/gcp_firewall.sh PROJECT_ID ТВОЯ_IP`.

Послідовна версія на кластері запускається як звичайна задача PARCS: її `Solver` не використовує воркерів і рахує все на майстрі. Так обидві версії міряються на однакових VM (`n1-standard-1`) і тим самим Python 2.7.

**VM коштують грошей, поки існують**, тому після замірів обов'язково запускай `gcp_down.sh` і перевіряй, що списки VM і дисків порожні.

## Безпека

PARCS приймає й виконує код без пароля, тому порт 8080 і SSH відкриті лише для адреси Cloud Shell і твоєї IP, а VM створюються без сервісного акаунта. Образ `hummer12007/parcs-node` сторонній і працює на Python 2.7, тому кластер тримається ввімкненим лише на час роботи.
