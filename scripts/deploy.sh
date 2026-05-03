#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DEPLOY_HOST:-}" ]]; then
  echo "Set DEPLOY_HOST, for example: DEPLOY_HOST=1.2.3.4 npm run deploy" >&2
  exit 1
fi

if [[ -z "${DEPLOY_USER:-}" ]]; then
  echo "Set DEPLOY_USER, for example: DEPLOY_USER=root npm run deploy" >&2
  exit 1
fi

DEPLOY_PATH="${DEPLOY_PATH:-/var/www/gazel-express}"
DEPLOY_PORT="${DEPLOY_PORT:-22}"
TARGET="${DEPLOY_USER}@${DEPLOY_HOST}"

EXCLUDES=(
  --exclude ".DS_Store"
  --exclude ".git/"
  --exclude ".idea/"
  --exclude ".vscode/"
  --exclude "__pycache__/"
  --exclude "*.pyc"
  --exclude "node_modules/"
  --exclude "*.log"
)

if [[ "${DEPLOY_INCLUDE_DATA:-0}" != "1" ]]; then
  EXCLUDES+=(--exclude "data/")
fi

echo "Creating ${TARGET}:${DEPLOY_PATH}"
ssh -p "${DEPLOY_PORT}" "${TARGET}" "mkdir -p '${DEPLOY_PATH}/data'"

echo "Uploading project"
rsync -az --delete \
  -e "ssh -p ${DEPLOY_PORT}" \
  "${EXCLUDES[@]}" \
  ./ "${TARGET}:${DEPLOY_PATH}/"

echo "Building and starting Docker container"
ssh -p "${DEPLOY_PORT}" "${TARGET}" "cd '${DEPLOY_PATH}' && docker compose up -d --build"

echo "Deployed to ${TARGET}:${DEPLOY_PATH}"
