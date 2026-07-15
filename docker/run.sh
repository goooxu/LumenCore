#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${NRTX_DOCKER_IMAGE:-spectraldock-dev:cuda13.3}"
BUILD_DIR="${NRTX_BUILD_DIR:-/tmp/LumenCore-build}"
OUT_DIR="${NRTX_OUT_DIR:-/tmp/LumenCore-out}"
CMD="${*:-bash}"

mkdir -p "${BUILD_DIR}" "${OUT_DIR}"

# NFS scratch is often not writable as root inside Docker; build/output stay on local disk.
docker run --rm --gpus all \
  -u "$(id -u):$(id -g)" \
  -v "${ROOT}:/work:ro" \
  -v "${BUILD_DIR}:/out" \
  -v "${OUT_DIR}:/results" \
  -v /usr/share/nvidia/nvoptix.bin:/usr/share/nvidia/nvoptix.bin:ro \
  -w /out \
  -e NRTX_PTX=/out/shaders.optixir \
  "${IMAGE}" \
  bash -lc "${CMD}"
