#!/usr/bin/env bash
# Дозволяє доступ до майстра PARCS (порт 8080) і SSH лише з потрібних IP-адрес:
#   - з поточної адреси Cloud Shell (визначається автоматично; вона змінюється між сесіями!)
#   - з додаткових адрес (наприклад, твоя домашня IP, щоб відкрити веб-інтерфейс у браузері).
# PARCS без пароля виконує будь-який код, тому відкривати порт усьому інтернету не можна.
# Запуск: bash tools/gcp_firewall.sh PROJECT_ID [ДОДАТКОВА_IP ...]
set -euo pipefail

PROJECT=${1:?Usage: bash tools/gcp_firewall.sh PROJECT_ID [EXTRA_IP ...]}
shift

ip_re='^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
shell_ip=$(curl -fsS --max-time 15 https://checkip.amazonaws.com | tr -d '[:space:]')
[[ $shell_ip =~ $ip_re ]] || { echo "Unexpected Cloud Shell IP: $shell_ip"; exit 1; }
ranges="$shell_ip/32"
echo "Cloud Shell IP: $shell_ip"
for ip in "$@"; do
    [[ $ip =~ $ip_re ]] || { echo "Not an IPv4 address: $ip"; exit 1; }
    ranges="$ranges,$ip/32"
    echo "Extra IP:       $ip"
done

# Порт 8080 (сайт і API PARCS) - лише для майстра.
if [ -n "$(gcloud compute firewall-rules list --project="$PROJECT" --filter=name=parcs-web --format='value(name)')" ]; then
    gcloud compute firewall-rules update parcs-web --project="$PROJECT" --source-ranges="$ranges"
else
    gcloud compute firewall-rules create parcs-web --project="$PROJECT" --direction=INGRESS \
        --network=default --action=ALLOW --rules=tcp:8080 --source-ranges="$ranges" --target-tags=parcs-master
fi

# Стандартне правило SSH відкрите на весь інтернет - обмежуємо. Помилку ігноруємо: правила могло не бути.
gcloud compute firewall-rules update default-allow-ssh --project="$PROJECT" --source-ranges="$ranges" 2>/dev/null || true
echo "Firewall: port 8080 allowed from $ranges"
