#!/usr/bin/env bash
# Fetch and build NVIDIA PhysX 5, then install headers/libs into third_party/physx.
# First run needs network. GPU .so comes from PhysX packman (PM_PhysXGpu_PATH).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="${PHYSX_INSTALL:-${ROOT}/third_party/physx}"
SRC="${PHYSX_SRC:-/tmp/PhysX-src}"
TAG="${PHYSX_TAG:-106.1-physx-5.4.2}"
CMAKE_DIR="${NRTX_CMAKE_DIR:-/tmp/cmake}"

echo "==> Install target: ${INSTALL}"
mkdir -p "${INSTALL}/include" "${INSTALL}/lib" "${INSTALL}/bin"

if [[ ! -d "${SRC}/.git" ]]; then
  echo "==> Cloning PhysX ${TAG} into ${SRC}"
  rm -rf "${SRC}"
  git clone --depth 1 --branch "${TAG}" https://github.com/NVIDIA-Omniverse/PhysX.git "${SRC}"
fi

if [[ ! -x "${CMAKE_DIR}/bin/cmake" ]]; then
  echo "==> Downloading portable CMake into ${CMAKE_DIR}"
  curl -fsSL -o /tmp/cmake-linux.tgz \
    https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5-linux-x86_64.tar.gz
  mkdir -p "${CMAKE_DIR}"
  tar -xzf /tmp/cmake-linux.tgz -C "${CMAKE_DIR}" --strip-components=1
fi
export PATH="${CMAKE_DIR}/bin:${PATH}"

# Packman PhysXGpu (required when building GPU-capable binaries)
if [[ -z "${PM_PhysXGpu_PATH:-}" ]]; then
  GPU_CANDIDATE=$(ls -d "${HOME}/.cache/packman/chk/PhysXGpu/"*release*linux* 2>/dev/null | head -1 || true)
  if [[ -n "${GPU_CANDIDATE}" ]]; then
    export PM_PhysXGpu_PATH="${GPU_CANDIDATE}"
  fi
fi

PRESET_DIR="${SRC}/physx/buildtools/presets/public"
if [[ ! -f "${PRESET_DIR}/linux-gcc.xml" ]]; then
  # Generate a gcc preset from the clang one if missing.
  if [[ -f "${PRESET_DIR}/linux.xml" ]]; then
    cp "${PRESET_DIR}/linux.xml" "${PRESET_DIR}/linux-gcc.xml"
    sed -i 's/clang/gcc/g; s/Clang/Gcc/g' "${PRESET_DIR}/linux-gcc.xml" || true
  fi
fi

echo "==> Generating PhysX projects"
(
  cd "${SRC}/physx"
  if [[ -x ./generate_projects.sh ]]; then
    ./generate_projects.sh linux-gcc || ./generate_projects.sh linux
  fi
)

BUILD_DIR=$(ls -d "${SRC}/physx/compiler/"*release* 2>/dev/null | head -1 || true)
if [[ -z "${BUILD_DIR}" ]]; then
  echo "ERROR: no PhysX compiler release dir under ${SRC}/physx/compiler" >&2
  exit 1
fi

echo "==> Building PhysX static release (${BUILD_DIR})"
cmake --build "${BUILD_DIR}" --config release -j"$(nproc)"

BIN_DIR=$(ls -d "${SRC}/physx/bin/"*/release 2>/dev/null | head -1)
if [[ -z "${BIN_DIR}" ]]; then
  echo "ERROR: PhysX bin release directory not found" >&2
  exit 1
fi

echo "==> Installing headers + static libs → ${INSTALL}"
rm -rf "${INSTALL}/include" "${INSTALL}/lib"
mkdir -p "${INSTALL}/include" "${INSTALL}/lib" "${INSTALL}/bin"
cp -a "${SRC}/physx/include/." "${INSTALL}/include/"
cp -a "${BIN_DIR}/"*.a "${INSTALL}/lib/"

GPU_SO=$(find "${PM_PhysXGpu_PATH:-/nonexistent}" "${BIN_DIR}" -name 'libPhysXGpu_64.so' 2>/dev/null | head -1 || true)
if [[ -n "${GPU_SO}" ]]; then
  cp -a "${GPU_SO}" "${INSTALL}/bin/"
  echo "==> Installed GPU runtime: ${INSTALL}/bin/libPhysXGpu_64.so"
else
  echo "WARN: libPhysXGpu_64.so not found; GPU rigid bodies will fall back to CPU"
fi

# Ensure static-lib define is present for consumers
if ! grep -q PX_PHYSX_STATIC_LIB "${INSTALL}/include/PxConfig.h" 2>/dev/null; then
  cat > "${INSTALL}/include/PxConfig.h" <<'EOF'
#ifndef PX_CONFIG
#define PX_CONFIG
#ifndef PX_PHYSX_STATIC_LIB
#define PX_PHYSX_STATIC_LIB
#endif
#endif
EOF
fi

echo "==> PhysX ready at ${INSTALL}"
ls -la "${INSTALL}/lib" | head
