#!/usr/bin/env bash
# Fetch and build NVIDIA PhysX 5, then install headers/libs into third_party/physx.
# First run needs network. GPU .so comes from PhysX packman (PM_PhysXGpu_PATH) or the build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="${PHYSX_INSTALL:-${ROOT}/third_party/physx}"
SRC="${PHYSX_SRC:-/tmp/PhysX-src}"
TAG="${PHYSX_TAG:-106.1-physx-5.4.2}"
CMAKE_DIR="${NRTX_CMAKE_DIR:-/tmp/cmake}"

HOST_ARCH="$(uname -m)"
case "${HOST_ARCH}" in
  aarch64|arm64)
    CMAKE_ARCH=aarch64
    PRESET_CANDIDATES=(linux-aarch64 linux-gcc linux)
    ;;
  *)
    CMAKE_ARCH=x86_64
    PRESET_CANDIDATES=(linux-gcc linux)
    ;;
esac

echo "==> Install target: ${INSTALL} (host=${HOST_ARCH})"
mkdir -p "${INSTALL}/include" "${INSTALL}/lib" "${INSTALL}/bin"

if [[ ! -d "${SRC}/.git" ]]; then
  echo "==> Cloning PhysX ${TAG} into ${SRC}"
  rm -rf "${SRC}"
  git clone --depth 1 --branch "${TAG}" https://github.com/NVIDIA-Omniverse/PhysX.git "${SRC}"
fi

if [[ ! -x "${CMAKE_DIR}/bin/cmake" ]] || ! "${CMAKE_DIR}/bin/cmake" --version >/dev/null 2>&1; then
  echo "==> Downloading portable CMake (${CMAKE_ARCH}) into ${CMAKE_DIR}"
  rm -rf "${CMAKE_DIR}"
  curl -fsSL -o /tmp/cmake-linux.tgz \
    "https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5-linux-${CMAKE_ARCH}.tar.gz"
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
  if [[ -f "${PRESET_DIR}/linux.xml" ]]; then
    cp "${PRESET_DIR}/linux.xml" "${PRESET_DIR}/linux-gcc.xml"
    sed -i 's/clang/gcc/g; s/Clang/Gcc/g' "${PRESET_DIR}/linux-gcc.xml" || true
  fi
fi

echo "==> Available presets:"
ls "${PRESET_DIR}" | head -40 || true

echo "==> Generating PhysX projects"
(
  cd "${SRC}/physx"
  ok=0
  if [[ -x ./generate_projects.sh ]]; then
    for p in "${PRESET_CANDIDATES[@]}"; do
      if [[ ! -f "${PRESET_DIR}/${p}.xml" ]]; then
        echo "==> skip missing preset xml: ${p}"
        continue
      fi
      echo "==> try preset: ${p}"
      # generate_projects may exit 0 even on missing preset; require compiler output.
      rm -rf "${SRC}/physx/compiler/${p}"* 2>/dev/null || true
      ./generate_projects.sh "${p}" || true
      if ls -d "${SRC}/physx/compiler/"*release* "${SRC}/physx/compiler/"*checked* "${SRC}/physx/compiler/${p}"* 2>/dev/null | grep -v '/public$' >/dev/null; then
        ok=1
        break
      fi
      echo "==> preset ${p} did not produce a build dir"
    done
  fi
  if [[ "${ok}" -ne 1 ]]; then
    echo "ERROR: generate_projects.sh failed for candidates: ${PRESET_CANDIDATES[*]}" >&2
    ls -la "${SRC}/physx/compiler" 2>&1 || true
    exit 1
  fi
)

BUILD_DIR=$(ls -d "${SRC}/physx/compiler/"*release* 2>/dev/null | head -1 || true)
if [[ -z "${BUILD_DIR}" ]]; then
  BUILD_DIR=$(ls -d "${SRC}/physx/compiler/"* 2>/dev/null | head -1 || true)
fi
if [[ -z "${BUILD_DIR}" ]]; then
  echo "ERROR: no PhysX compiler dir under ${SRC}/physx/compiler" >&2
  ls -la "${SRC}/physx/compiler" 2>&1 || true
  exit 1
fi

echo "==> Building PhysX (${BUILD_DIR})"
# Build SDK libs only — snippet/GL targets need system OpenGL headers we may lack.
(
  cd "${BUILD_DIR}"
  targets=(PhysX PhysXCommon PhysXFoundation PhysXCooking PhysXExtensions PhysXPvdSDK
           PhysXCharacterKinematic PhysXVehicle PhysXVehicle2)
  cmake --build . --config release -j"$(nproc)" --target "${targets[@]}" 2>/dev/null || \
    cmake --build . -j"$(nproc)" --target "${targets[@]}"
)

BIN_DIR=$(ls -d "${SRC}/physx/bin/"*/release 2>/dev/null | head -1)
if [[ -z "${BIN_DIR}" ]]; then
  BIN_DIR=$(ls -d "${SRC}/physx/bin/"*/checked 2>/dev/null | head -1)
fi
if [[ -z "${BIN_DIR}" ]]; then
  echo "ERROR: PhysX bin directory not found" >&2
  find "${SRC}/physx/bin" -maxdepth 3 -type d 2>/dev/null | head -40
  exit 1
fi

echo "==> Installing headers + static libs → ${INSTALL}"
rm -rf "${INSTALL}/include" "${INSTALL}/lib"
mkdir -p "${INSTALL}/include" "${INSTALL}/lib" "${INSTALL}/bin"
cp -a "${SRC}/physx/include/." "${INSTALL}/include/"
cp -a "${BIN_DIR}/"*.a "${INSTALL}/lib/" 2>/dev/null || true
if ! ls "${INSTALL}/lib/"*.a >/dev/null 2>&1; then
  find "${SRC}/physx/bin" -name '*.a' -exec cp -a {} "${INSTALL}/lib/" \;
fi

GPU_SO=$(find "${PM_PhysXGpu_PATH:-/nonexistent}" "${BIN_DIR}" "${SRC}/physx/bin" -name 'libPhysXGpu_64.so' 2>/dev/null | head -1 || true)
if [[ -n "${GPU_SO}" ]]; then
  cp -a "${GPU_SO}" "${INSTALL}/bin/"
  echo "==> Installed GPU runtime: ${INSTALL}/bin/libPhysXGpu_64.so ($(file "${INSTALL}/bin/libPhysXGpu_64.so"))"
else
  echo "WARN: libPhysXGpu_64.so not found; GPU rigid bodies will fail to init"
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
file "${INSTALL}/lib/"*.a 2>/dev/null | head -3
