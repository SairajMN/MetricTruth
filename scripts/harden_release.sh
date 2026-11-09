#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGED_DIR="${ROOT_DIR}/build/release-staged"
SHIELDED_DIR="${ROOT_DIR}/build/release-staged.shielded"

echo "[MetricTruth Counter-REA] Preparing staged release bundle at ${STAGED_DIR}..."
rm -rf "${STAGED_DIR}" "${SHIELDED_DIR}"
mkdir -p "${STAGED_DIR}"

cp -R "${ROOT_DIR}/apps/api/backend" "${STAGED_DIR}/backend"

echo "[MetricTruth Counter-REA] 1/3 Running pre-protection REA surface audit..."
npx -y bla-agents@latest audit "${STAGED_DIR}" || true

echo "[MetricTruth Counter-REA] 2/3 Applying BLA AI Tarpit & Semantic Shield to staged bundle..."
npx -y bla-agents@latest protect "${STAGED_DIR}" || true

echo "[MetricTruth Counter-REA] 3/3 Verifying Counter-REA protection on ${SHIELDED_DIR}..."
npx -y bla-agents@latest verify "${SHIELDED_DIR}" || true

echo "[MetricTruth Counter-REA] Staged release artifact hardened at ${SHIELDED_DIR} (git source tree untouched)."
