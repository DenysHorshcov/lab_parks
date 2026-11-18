#!/usr/bin/env bash
# Створює кластер PARCS у Google Cloud: майстер і N воркерів. Запускати з Google Cloud Shell.
# VM коштують грошей, поки існують: після замірів ОДРАЗУ запусти tools/gcp_down.sh.
# Запуск: bash tools/gcp_up.sh PROJECT_ID [ВОРКЕРІВ=4] [ЗОНА=europe-central2-a] [ТВОЯ_IP]
#   ТВОЯ_IP - адреса твого ПК (дізнатися на https://ifconfig.me), щоб відкривати веб-інтерфейс PARCS
#   у браузері. Адреса самого Cloud Shell додається автоматично.
set -Eeuo pipefail

PROJECT=${1:?Usage: bash tools/gcp_up.sh PROJECT_ID [WORKERS] [ZONE] [YOUR_IP]}
WORKERS=${2:-4}
ZONE=${3:-europe-central2-a}
MY_IP=${4:-}
MACHINE_TYPE=${MACHINE_TYPE:-n1-standard-1}  # 1 vCPU, 3,75 ГБ пам'яті
IMAGE=registry.hub.docker.com/hummer12007/parcs-node
TOOLS=$(cd "$(dirname "$0")" && pwd)

# разом із майстром до 8 VM: стільки дозволяє квота зовнішніх IP-адрес у пробному акаунті
if ! [[ $WORKERS =~ ^[1-7]$ ]]; then echo "WORKERS must be 1..7"; exit 1; fi

gcloud config set project "$PROJECT" >/dev/null
echo "Enabling Compute Engine API (first time takes ~1 min)..."
gcloud services enable compute.googleapis.com --project="$PROJECT"

existing=$(gcloud compute instances list --project="$PROJECT" --filter=labels.lab=parcs --format='value(name)')
if [ -n "$existing" ]; then
    echo "The cluster already exists: $existing. Run tools/gcp_down.sh first."
    exit 1
fi

if [ -n "$MY_IP" ]; then bash "$TOOLS/gcp_firewall.sh" "$PROJECT" "$MY_IP"; else bash "$TOOLS/gcp_firewall.sh" "$PROJECT"; fi

# Зайві стандартні правила видаляємо. Помилку ігноруємо: правил могло не бути.
gcloud compute firewall-rules delete default-allow-rdp --project="$PROJECT" --quiet 2>/dev/null || true
gcloud compute firewall-rules delete default-allow-icmp --project="$PROJECT" --quiet 2>/dev/null || true

# Стартовий скрипт VM запускає контейнер PARCS. $1 - роль: "master" або "worker <внутрішня IP майстра>".
# Container-Optimized OS блокує вхідні з'єднання, тому на VM їх дозволяємо; ззовні доступ
# і далі обмежує firewall Google Cloud.
startup_script() {
    local file
    file=$(mktemp)
    cat > "$file" <<SCRIPT
#!/bin/bash
iptables -w -A INPUT -p tcp -j ACCEPT
docker rm -f parcs 2>/dev/null
docker run -d --name parcs --restart=always --network host -e PARCS_ARGS="$1" $IMAGE
SCRIPT
    echo "$file"
}

# --no-service-account: образ PARCS сторонній, тому VM не отримує доступу до API проєкту.
# --labels=lab=parcs: за цією міткою gcp_down.sh знаходить VM.
new_vm() {
    local name=$1 role=$2 tag=$3 disk=$4 script
    script=$(startup_script "$role")
    gcloud compute instances create "$name" --project="$PROJECT" --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" --image-family=cos-stable --image-project=cos-cloud \
        --boot-disk-size="${disk}GB" --no-service-account --no-scopes \
        --tags="$tag" --labels=lab=parcs --metadata-from-file=startup-script="$script"
    rm -f "$script"
}

# Не залишаємо частково створений кластер, бо його VM коштували б грошей.
cleanup_on_error() {
    echo "Cluster creation failed, removing the VMs created so far..."
    bash "$TOOLS/gcp_down.sh" "$PROJECT" "$ZONE" || echo "WARNING: could not remove the VMs, they are still billed. Run tools/gcp_down.sh now."
}
trap cleanup_on_error ERR

new_vm master master parcs-master 20  # диск більший: тут зберігаються файли задач

# Внутрішня адреса потрібна воркерам, зовнішня - для браузера і скриптів замірів.
internal=$(gcloud compute instances describe master --project="$PROJECT" --zone="$ZONE" --format='get(networkInterfaces[0].networkIP)')
external=$(gcloud compute instances describe master --project="$PROJECT" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
[ -n "$internal" ] || { echo "Could not read the master internal IP"; false; }

# Воркери самі реєструються на майстрі приблизно за 1-2 хвилини.
for i in $(seq 1 "$WORKERS"); do
    new_vm "worker$i" "worker $internal" parcs-worker 10
done
trap - ERR

echo "$external" > "$TOOLS/../.master_ip"
echo
echo "Master web UI: http://$external:8080  (open in 2-3 minutes)"
echo "Workers should appear at: http://$external:8080/workers"
echo "Saved to .master_ip. Use it as: MASTER=http://\$(cat .master_ip):8080"
echo "The cluster is billed until you run: bash tools/gcp_down.sh $PROJECT $ZONE"
