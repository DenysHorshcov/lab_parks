#!/usr/bin/env bash
# Калібрування k для input/big.txt: запускає ПОСЛІДОВНУ версію на майстрі PARCS
# для кількох значень k і друкує час. Мета - знайти k, за якого час ~60 с.
# Запуск: bash tools/calibrate.sh АДРЕСА_МАЙСТРА K1 [K2 ...]
# Приклад: bash tools/calibrate.sh http://1.2.3.4:8080 10000000 30000000
# Час росте лінійно з k, тому k_потрібне ~ k * 60 / час.
set -u

MASTER=${1:?Usage: bash tools/calibrate.sh MASTER_URL K1 [K2 ...]}
shift
source "$(dirname "$0")/parcs_api.sh"

P=2305843009213693951  # 2^61 - 1
tmp=$(mktemp -d)
job=$(next_job_id)
for k in "$@"; do
    printf '%d %d %d\n' $((P - 1)) "$k" "$P" > "$tmp/in.txt"
    submit_and_wait "$job" "calibrate_k$k" solution/combinatorics_sequential.py "$tmp/in.txt" "$tmp/out.txt" || exit 1
    t=$(field "$tmp/out.txt" 'Total time' | sed 's/ s$//')
    echo "k=$k time=${t}s  -> for 60 s use k ~ $(awk -v k="$k" -v t="$t" 'BEGIN { printf "%d", k * 60 / t }')"
    job=$((job + 1))
done
rm -rf "$tmp"
echo "Put the chosen k (EVEN number, so the Wilson answer is 1) into input/big.txt"
