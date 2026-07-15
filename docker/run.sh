#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${NRTX_DOCKER_IMAGE:-nvidia/cuda:13.0.1-devel-ubuntu24.04}"
BUILD_DIR="${NRTX_BUILD_DIR:-/tmp/LumenCore-build}"
OUT_DIR="${NRTX_OUT_DIR:-/tmp/LumenCore-out}"
CMAKE_DIR="${NRTX_CMAKE_DIR:-/tmp/cmake}"
CMD="${*:-bash}"

mkdir -p "${BUILD_DIR}" "${OUT_DIR}"

# Portable CMake (CUDA devel images often lack apt write access as non-root)
if [[ ! -x "${CMAKE_DIR}/bin/cmake" ]]; then
  echo "Downloading portable CMake into ${CMAKE_DIR} ..."
  curl -fsSL -o /tmp/cmake-linux.tgz \
    https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5-linux-x86_64.tar.gz
  mkdir -p "${CMAKE_DIR}"
  tar -xzf /tmp/cmake-linux.tgz -C "${CMAKE_DIR}" --strip-components=1
fi

# Ensure a CUDA image with Python headers exists for pybind11 builds.
if [[ "${IMAGE}" == "nvidia/cuda:13.0.1-devel-ubuntu24.04" ]]; then
  if ! docker image inspect lumencore-build:cuda13 >/dev/null 2>&1; then
    echo "Building lumencore-build:cuda13 (adds python3-dev) ..."
    docker run --name lumencore-pysetup "${IMAGE}" bash -lc \
      "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-dev git"
    docker commit lumencore-pysetup lumencore-build:cuda13
    docker rm lumencore-pysetup
  fi
  IMAGE="lumencore-build:cuda13"
fi

# NFS scratch is often not writable as root inside Docker; build/output stay on local disk.
# Mount driver OptiX/RTX libraries — stock CUDA images do not ship them.
docker run --rm --gpus all \
  -u "$(id -u):$(id -g)" \
  -v "${ROOT}:/work:ro" \
  -v "${BUILD_DIR}:/out" \
  -v "${OUT_DIR}:/results" \
  -v "${CMAKE_DIR}:/cmake:ro" \
  -v /usr/share/nvidia:/usr/share/nvidia:ro \
  -v /usr/lib/x86_64-linux-gnu/libnvoptix.so.1:/usr/lib/x86_64-linux-gnu/libnvoptix.so.1:ro \
  -v /usr/lib/x86_64-linux-gnu/libnvoptix.so.615.36:/usr/lib/x86_64-linux-gnu/libnvoptix.so.615.36:ro \
  -v /usr/lib/x86_64-linux-gnu/libnvidia-rtcore.so.615.36:/usr/lib/x86_64-linux-gnu/libnvidia-rtcore.so.615.36:ro \
  -w /out \
  -e PATH=/cmake/bin:/usr/local/cuda/bin:/usr/bin:/bin \
  -e LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu \
  -e NRTX_PTX=/out/shaders.optixir \
  -e LUMENCORE_ROOT=/work \
  -e PYTHONPATH=/out/python \
  -e HOME=/tmp \
  "${IMAGE}" \
  bash -lc "${CMD}"
