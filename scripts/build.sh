#!/usr/bin/env bash
# One-shot LumenCore build: check host GPU, run CMake inside Docker (fetches deps).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "[build] LumenCore — host preflight"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "error: only Linux is supported (got $(uname -s))" >&2
  exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "error: nvidia-smi not found. Install an NVIDIA driver so the GPU is visible." >&2
  exit 1
fi
if ! nvidia-smi >/dev/null 2>&1; then
  echo "error: nvidia-smi failed. Fix the GPU driver first." >&2
  nvidia-smi || true
  exit 1
fi
echo "[build] GPU:"
nvidia-smi -L || true

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker not found. The build uses a CUDA container for the compiler toolchain." >&2
  echo "  Install Docker + NVIDIA Container Toolkit, then re-run." >&2
  exit 1
fi

export NRTX_BUILD_DIR="${NRTX_BUILD_DIR:-/tmp/LumenCore-build}"
export NRTX_OUT_DIR="${NRTX_OUT_DIR:-/tmp/LumenCore-out}"
export NRTX_CMAKE_DIR="${NRTX_CMAKE_DIR:-/tmp/cmake}"
export NRTX_GPU="${NRTX_GPU:-all}"

# PhysX install lands under the CMake build tree; runtime looks here.
export NRTX_PHYSX_ROOT="${NRTX_PHYSX_ROOT:-${NRTX_BUILD_DIR}/_deps/physx}"

mkdir -p "${NRTX_BUILD_DIR}" "${NRTX_OUT_DIR}"

# CUDA arch for CMake (also auto-detected inside the container via nvidia-smi).
if [[ -z "${NRTX_CUDA_ARCH:-}" ]]; then
  CAP="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')"
  if [[ "${CAP}" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
    NRTX_CUDA_ARCH="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
  fi
fi
CMAKE_ARCH_ARGS=""
if [[ -n "${NRTX_CUDA_ARCH:-}" ]]; then
  CMAKE_ARCH_ARGS="-DCMAKE_CUDA_ARCHITECTURES=${NRTX_CUDA_ARCH}"
  echo "[build] CMAKE_CUDA_ARCHITECTURES=${NRTX_CUDA_ARCH}"
fi

echo "[build] configure + build (deps fetched on first run; PhysX may take several minutes)"
./docker/run.sh \
  "cmake -S /work -B /out -DCMAKE_BUILD_TYPE=Release -DLUMENCORE_FETCH_DEPS=ON ${CMAKE_ARCH_ARGS} && \
   cmake --build /out -j\$(nproc)"

SO="$(ls "${NRTX_BUILD_DIR}/python"/lumencore*.so 2>/dev/null | head -1 || true)"
if [[ -z "${SO}" ]]; then
  echo "error: build finished but lumencore*.so not found under ${NRTX_BUILD_DIR}/python" >&2
  exit 1
fi

echo "[build] OK: ${SO}"
echo "[build] PhysX root: ${NRTX_PHYSX_ROOT} (or ${NRTX_BUILD_DIR}/_deps/physx)"
echo "[build] Run a scene, for example:"
echo "  NRTX_PHYSX_ROOT=${NRTX_BUILD_DIR}/_deps/physx ./docker/run.sh \\"
echo "    'python3 /work/python/scenes/cornell.py /results/cornell.avif 64 1'"
