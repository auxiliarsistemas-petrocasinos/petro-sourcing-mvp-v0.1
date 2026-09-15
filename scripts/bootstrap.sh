#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv no está disponible en PATH."
  exit 1
}

uv python install 3.12
uv sync

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Se creó .env. Agrega OPENAI_API_KEY antes de investigar proveedores."
fi

echo
echo "Entorno listo."
echo "Ejecuta: make dev"
