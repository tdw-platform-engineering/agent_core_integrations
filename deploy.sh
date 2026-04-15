#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# deploy.sh — Lee el .env y despliega a AgentCore pasando todas las
#              variables como --env KEY=VALUE automáticamente.
#
# Uso:
#   ./deploy.sh                  # deploy normal (cloud build)
#   ./deploy.sh --local-build    # build local, deploy a cloud
#   ./deploy.sh --local          # solo correr local
#
# Opciones extra se pasan directo a `agentcore deploy`.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ No se encontró .env en ${SCRIPT_DIR}"
  echo "   Copia el template:  cp env.example .env"
  exit 1
fi

# ── Construir los flags --env KEY=VALUE ──────────────────────────────
ENV_FLAGS=()
while IFS= read -r line || [ -n "$line" ]; do
  # Ignorar líneas vacías y comentarios
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # Extraer KEY=VALUE (trim espacios)
  key="${line%%=*}"
  value="${line#*=}"
  key="$(echo "$key" | xargs)"
  value="$(echo "$value" | xargs)"

  # Saltar si el valor está vacío
  [ -z "$value" ] && continue

  ENV_FLAGS+=(--env "${key}=${value}")
done < "$ENV_FILE"

echo "🚀 Desplegando con ${#ENV_FLAGS[@]} variables de entorno desde .env"
echo "   Flags extra: $*"
echo ""

# ── Deploy ───────────────────────────────────────────────────────────
agentcore deploy "${ENV_FLAGS[@]}" "$@"
