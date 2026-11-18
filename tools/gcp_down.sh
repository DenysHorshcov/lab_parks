#!/usr/bin/env bash
# Видаляє кластер PARCS: VM, їхні диски та правило parcs-web.
# VM коштують грошей, поки існують, тому запускай це ОДРАЗУ після замірів.
# Запуск: bash tools/gcp_down.sh PROJECT_ID [ЗОНА=europe-central2-a]
set -uo pipefail

PROJECT=${1:?Usage: bash tools/gcp_down.sh PROJECT_ID [ZONE]}
ZONE=${2:-europe-central2-a}  # має збігатися із зоною з gcp_up.sh

# Мітку lab=parcs ставить gcp_up.sh, тому інші VM проєкту не постраждають.
names=$(gcloud compute instances list --project="$PROJECT" --filter=labels.lab=parcs --format='value(name)')
if [ -n "$names" ]; then
    # Без --delete-disks=all за диски довелося б платити й далі.
    # shellcheck disable=SC2086
    gcloud compute instances delete $names --project="$PROJECT" --zone="$ZONE" --delete-disks=all --quiet \
        || { echo "Could not delete VMs"; exit 1; }
else
    echo "No PARCS VMs to delete."
fi

gcloud compute firewall-rules delete parcs-web --project="$PROJECT" --quiet 2>/dev/null || true

# Контроль: якщо список не порожній, щось ще може коштувати грошей.
echo
echo "What is left (both lists must be empty):"
echo "--- VMs"
gcloud compute instances list --project="$PROJECT"
echo "--- Disks"
gcloud compute disks list --project="$PROJECT"
