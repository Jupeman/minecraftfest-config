#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${REPO_ROOT}/shared/plugin-jars"
MSM_SERVERS_DIR="/opt/msm/servers"

if [[ ! -d "${SRC}" ]]; then
  echo "ERROR: ${SRC} does not exist."
  echo "Create it and put plugin jars in shared/plugin-jars/"
  exit 1
fi

if [[ ! -d "${MSM_SERVERS_DIR}" ]]; then
  echo "ERROR: MSM servers dir not found: ${MSM_SERVERS_DIR}"
  exit 1
fi

echo "==> Syncing plugin jars from:"
echo "    ${SRC}"
echo "==> To MSM servers under:"
echo "    ${MSM_SERVERS_DIR}"
echo

mapfile -t SERVERS < <(find "${MSM_SERVERS_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

if [[ ${#SERVERS[@]} -eq 0 ]]; then
  echo "No servers found under ${MSM_SERVERS_DIR}"
  exit 0
fi

for S in "${SERVERS[@]}"; do
  DST="${MSM_SERVERS_DIR}/${S}/plugins"
  mkdir -p "${DST}"

  echo "==> ${S}"
  # Copy only .jar files; do not touch plugin data folders.
  rsync -av --checksum \
	--include='*.jar' --exclude='*' \
	"${SRC}/" "${DST}/"
done

echo
echo "Done. Restart servers manually when you want changes to take effect."