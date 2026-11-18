#!/usr/bin/env bash
# Серія замірів на кластері: послідовна версія (задача PARCS на майстрі) і паралельна
# для різної кількості воркерів. Результат - ПАПКА/results.csv і вихідні файли кожного прогону.
# Запуск (з кореня репозиторію в Cloud Shell):
#   bash tools/run_measurements.sh АДРЕСА_МАЙСТРА ВХІД ПАПКА [ПРОГОНІВ=3] [ВЕРСІЇ="seq 1 2 4"]
# Приклад:
#   bash tools/run_measurements.sh http://1.2.3.4:8080 input/big.txt results/big 3 "seq 1 2 4"
# Довгу серію краще запускати у фоні, бо сесія Cloud Shell може обірватися:
#   nohup bash tools/run_measurements.sh ... > measure.log 2>&1 &   ;  tail -f measure.log
set -u

MASTER=$1
INPUT=$2
OUT=$3
RUNS=${4:-3}
VERSIONS=${5:-"seq 1 2 4"}
PARALLEL=solution/combinatorics_parallel.py
SEQUENTIAL=solution/combinatorics_sequential.py
source "$(dirname "$0")/parcs_api.sh"

# Не дописуємо до старих замірів, щоб не змішати середні значення.
CSV="$OUT/results.csv"
if [ -e "$CSV" ]; then
    echo "$CSV already exists. Choose another folder so that new runs do not mix with old ones."
    exit 1
fi
mkdir -p "$OUT"
echo "version,workers,run,job_id,n,k,p,comb,perm,wilson,total_time_s,worker_times_s" > "$CSV"

all_workers=$(worker_ids | wc -l)
echo "Workers registered on the master: $all_workers"
[ "$all_workers" -gt 0 ] || { echo "No workers. Check $MASTER/workers"; exit 1; }

job=$(next_job_id)
for v in $VERSIONS; do
    if [ "$v" = seq ]; then
        version=sequential; workers=0; solution=$SEQUENTIAL; expect=sequential
        set_workers "$all_workers" || { echo "Could not enable workers"; exit 1; }
    else
        version=parallel; workers=$v; solution=$PARALLEL; expect=$v
        set_workers "$workers" || { echo "Could not select $workers workers (only $all_workers registered?)"; exit 1; }
    fi
    for run in $(seq 1 "$RUNS"); do
        file="$OUT/output_${v}_r${run}.txt"
        submit_and_wait "$job" "${v}_r${run}" "$solution" "$INPUT" "$file" || exit 1
        # Перевіряємо, що працювала потрібна кількість воркерів.
        got=$(field "$file" Workers)
        if [ "$got" != "$expect" ]; then echo "Job $job used '$got' workers instead of '$expect'"; exit 1; fi
        total=$(field "$file" 'Total time' | sed 's/ s$//')
        echo "$version,$workers,$run,$job,$(field "$file" n),$(field "$file" k),$(field "$file" p),$(field "$file" 'C(n,k) mod p'),$(field "$file" 'P(n,k) mod p'),$(field "$file" 'Wilson check'),$total,\"$(field "$file" 'Worker compute times')\"" >> "$CSV"
        echo "$version workers=$workers run=$run job=$job time=${total}s wilson=$(field "$file" 'Wilson check')"
        job=$((job + 1))
    done
done

set_workers "$all_workers"
echo "DONE: $CSV"
echo "Next: python3 tools/summarize.py $CSV"
