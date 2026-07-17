#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${NRTX_DOCKER_IMAGE:-nvidia/cuda:13.0.1-devel-ubuntu24.04}"
BUILD_DIR="${NRTX_BUILD_DIR:-/tmp/LumenCore-build}"
OUT_DIR="${NRTX_OUT_DIR:-/tmp/LumenCore-out}"
CMAKE_DIR="${NRTX_CMAKE_DIR:-/tmp/cmake}"
# NRTX_GPU=all (default) or a host GPU index like 0,1,2 for parallel jobs.
NRTX_GPU="${NRTX_GPU:-all}"
CMD="${*:-bash}"

mkdir -p "${BUILD_DIR}" "${OUT_DIR}"

# Portable CMake (CUDA devel images often lack apt write access as non-root)
HOST_ARCH="$(uname -m)"
case "${HOST_ARCH}" in
  aarch64|arm64) CMAKE_ARCH=aarch64 ;;
  *) CMAKE_ARCH=x86_64 ;;
esac
if [[ ! -x "${CMAKE_DIR}/bin/cmake" ]] || ! "${CMAKE_DIR}/bin/cmake" --version >/dev/null 2>&1; then
  echo "Downloading portable CMake (${CMAKE_ARCH}) into ${CMAKE_DIR} ..."
  rm -rf "${CMAKE_DIR}"
  curl -fsSL -o /tmp/cmake-linux.tgz \
    "https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5-linux-${CMAKE_ARCH}.tar.gz"
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

# Host multiarch lib dirs (x86_64 and aarch64).
LIB_DIRS=(/usr/lib/x86_64-linux-gnu /usr/lib/aarch64-linux-gnu)
HOST_LIB_DIR=""
for d in "${LIB_DIRS[@]}"; do
  if [[ -d "${d}" ]]; then
    HOST_LIB_DIR="${d}"
    break
  fi
done
if [[ -z "${HOST_LIB_DIR}" ]]; then
  echo "error: no host multiarch lib dir found" >&2
  exit 1
fi

# PhysX GPU .so: prefer NRTX_PHYSX_ROOT (machine-local aarch64 builds), else repo vendored.
if [[ -n "${NRTX_PHYSX_ROOT:-}" ]]; then
  PHYSX_ROOT_HOST="${NRTX_PHYSX_ROOT}"
else
  PHYSX_ROOT_HOST="${ROOT}/third_party/physx"
fi
PHYSX_MOUNT_ARGS=()
if [[ "${PHYSX_ROOT_HOST}" != "${ROOT}/third_party/physx" ]]; then
  PHYSX_MOUNT_ARGS+=(-v "${PHYSX_ROOT_HOST}:/physx:ro")
  PHYSX_BIN_IN_CT="/physx/bin"
else
  PHYSX_BIN_IN_CT="/work/third_party/physx/bin"
fi
LD_EXTRA="${PHYSX_BIN_IN_CT}:${HOST_LIB_DIR}"

# NFS scratch is often not writable as root inside Docker; build/output stay on local disk.
# Mount driver OptiX/RTX libraries — stock CUDA images do not ship them.
# Do NOT bind-mount libnvoptix.so.1: nvidia-container-toolkit already injects it
# and a duplicate mount causes "device or resource busy".
# libnvidia-rtcore is usually NOT injected — mount the host versioned .so.
RTCORE_VER=""
for d in "${LIB_DIRS[@]}"; do
  cand="$(ls "${d}"/libnvidia-rtcore.so.* 2>/dev/null | grep -v '\.1$' | head -1 || true)"
  if [[ -n "${cand}" ]]; then
    RTCORE_VER="${cand}"
    break
  fi
done
if [[ -z "${RTCORE_VER}" ]]; then
  echo "error: libnvidia-rtcore.so.* not found on host" >&2
  exit 1
fi
NVOPTIX_VER=""
for d in "${LIB_DIRS[@]}"; do
  if [[ -e "${d}/libnvoptix.so.1" ]]; then
    NVOPTIX_VER="$(readlink -f "${d}/libnvoptix.so.1" 2>/dev/null || true)"
    break
  fi
done
OPTIX_MOUNT_ARGS=()
if [[ -n "${NVOPTIX_VER}" && -f "${NVOPTIX_VER}" ]]; then
  # Provide the versioned soname the .so.1 symlink resolves to (toolkit may omit it).
  OPTIX_MOUNT_ARGS+=(-v "${NVOPTIX_VER}:${NVOPTIX_VER}:ro")
fi

GPU_ARGS=(--gpus all)
if [[ "${NRTX_GPU}" != "all" ]]; then
  GPU_ARGS=(--gpus "device=${NRTX_GPU}")
fi

docker run --rm "${GPU_ARGS[@]}" \
  -u "$(id -u):$(id -g)" \
  -v "${ROOT}:/work:ro" \
  -v "${BUILD_DIR}:/out" \
  -v "${OUT_DIR}:/results" \
  -v "${CMAKE_DIR}:/cmake:ro" \
  -v /usr/share/nvidia:/usr/share/nvidia:ro \
  -v "${RTCORE_VER}:${RTCORE_VER}:ro" \
  "${OPTIX_MOUNT_ARGS[@]}" \
  "${PHYSX_MOUNT_ARGS[@]}" \
  -w /out \
  -e PATH=/cmake/bin:/usr/local/cuda/bin:/usr/bin:/bin \
  -e LD_LIBRARY_PATH="${LD_EXTRA}" \
  -e NRTX_PTX=/out/shaders.optixir \
  -e LUMENCORE_ROOT=/work \
  -e PYTHONPATH=/out/python \
  -e HOME=/tmp \
  "${IMAGE}" \
  bash -lc "${CMD}"
