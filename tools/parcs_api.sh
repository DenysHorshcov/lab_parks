#!/usr/bin/env bash
# Спільні функції для роботи з REST API майстра PARCS. Підключається через `source`.
# Потрібна змінна MASTER, наприклад http://1.2.3.4:8080

JOB_TIMEOUT=${JOB_TIMEOUT:-1800}

worker_ids() {
    curl -fsS --max-time 20 "$MASTER/api/worker" | tr ',{' '\n\n' | sed -n 's/^ *"id": *\([0-9]*\).*/\1/p' | sort -n
}

# Вмикає перших N воркерів, решту вимикає: так не треба перестворювати VM.
set_workers() {
    local want=$1 used=0 id state
    for id in $(worker_ids); do
        if [ "$used" -lt "$want" ]; then state=enable; used=$((used + 1)); else state=disable; fi
        curl -fsS --max-time 20 -o /dev/null -X POST "$MASTER/api/worker/$id/$state" || return 1
    done
    [ "$used" -eq "$want" ]
}

# PARCS нумерує задачі по порядку: номер наступної = останній + 1.
next_job_id() {
    local last
    last=$(curl -fsS --max-time 20 "$MASTER/jobs" | grep -o '/api/job/[0-9]*/solution' | grep -o '[0-9]*' | sort -n | tail -1)
    echo $(( ${last:--1} + 1 ))
}

# submit_and_wait НОМЕР_ЗАДАЧІ НАЗВА РІШЕННЯ.py ВХІД.txt ВИХІД.txt
submit_and_wait() {
    local job=$1 name=$2 solution=$3 input=$4 output=$5 code start
    curl -fsS --max-time 120 -o /dev/null \
        -F "job_name=$name" -F "solution_file=@$solution" -F "input_file=@$input" \
        "$MASTER/api/job" || { echo "Submit failed: $name"; return 1; }
    # Код 200 - готово, 400 - ще виконується, інший - помилка.
    start=$SECONDS
    while :; do
        code=$(curl -sS --max-time 60 -o "$output" -w '%{http_code}' "$MASTER/api/job/$job/output")
        [ "$code" = 200 ] && return 0
        if [ "$code" != 400 ]; then echo "Job $job ($name) failed: http $code"; return 1; fi
        if [ $((SECONDS - start)) -gt "$JOB_TIMEOUT" ]; then echo "Job $job ($name) timed out"; return 1; fi
        sleep 2
    done
}

# field ФАЙЛ "Назва поля" -> значення після двокрапки
field() { sed -n "s/^$2: *//p" "$1" | head -1; }
