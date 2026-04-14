#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

cd "${ROOT_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  python -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -e '.[tui]'

if [[ ! -f "${ROOT_DIR}/.env" && -f "${ROOT_DIR}/.env.example" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
fi

mkdir -p "${ROOT_DIR}/.orchestro"
if [[ ! -f "${ROOT_DIR}/.orchestro/global.md" && -f "${ROOT_DIR}/docs/global.md.example" ]]; then
  cp "${ROOT_DIR}/docs/global.md.example" "${ROOT_DIR}/.orchestro/global.md"
fi

exec orchestro tui --backend auto "$@"
