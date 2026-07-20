#!/usr/bin/env bash
# Clone + build NVIDIA PhysX 5 static libs and install to PHYSX_INSTALL.
# Used by CMake (FetchPhysX.cmake) and scripts/build.sh. Needs network + cmake + gcc/g++ + curl.
set -euo pipefail

TAG="${PHYSX_TAG:-106.1-physx-5.4.2}"
SRC="${PHYSX_SRC:-}"
INSTALL="${PHYSX_INSTALL:-}"
JOBS="${PHYSX_JOBS:-$(nproc 2>/dev/null || echo 4)}"

if [[ -z "${SRC}" || -z "${INSTALL}" ]]; then
  echo "usage: PHYSX_SRC=... PHYSX_INSTALL=... $0" >&2
  echo "  optional: PHYSX_TAG=${TAG} PHYSX_JOBS=${JOBS}" >&2
  exit 2
fi

if [[ -f "${INSTALL}/lib/libPhysX_static_64.a" && -f "${INSTALL}/include/PxPhysicsAPI.h" &&
      -f "${INSTALL}/bin/libPhysXGpu_64.so" ]]; then
  echo "==> PhysX already installed at ${INSTALL} (skip)"
  exit 0
fi

echo "==> PhysX fetch/build tag=${TAG}"
echo "    SRC=${SRC}"
echo "    INSTALL=${INSTALL}"

mkdir -p "${INSTALL}/include" "${INSTALL}/lib" "${INSTALL}/bin"

if [[ ! -d "${SRC}/.git" ]]; then
  echo "==> Cloning PhysX ${TAG}"
  if [[ -d "${SRC}" ]] && [[ -n "$(ls -A "${SRC}" 2>/dev/null || true)" ]]; then
    rm -rf "${SRC}"
  fi
  mkdir -p "$(dirname "${SRC}")"
  git clone --depth 1 --branch "${TAG}" https://github.com/NVIDIA-Omniverse/PhysX.git "${SRC}"
fi

export CC="${CC:-gcc}"
export CXX="${CXX:-g++}"
if ! command -v "${CC}" >/dev/null || ! command -v "${CXX}" >/dev/null; then
  echo "ERROR: need gcc/g++ (CC=${CC} CXX=${CXX})" >&2
  exit 1
fi
if ! command -v cmake >/dev/null; then
  echo "ERROR: cmake not on PATH" >&2
  exit 1
fi
if ! command -v curl >/dev/null; then
  echo "ERROR: curl not on PATH (required by PhysX packman)" >&2
  exit 1
fi

PHYSX_DIR="${SRC}/physx"
PRESET_DIR="${PHYSX_DIR}/buildtools/presets/public"

# --- Ensure PhysXGpu prebuilt .so is available (cmake FILE COPY requires it) ---
ensure_physx_gpu() {
  # Already in tree?
  if [[ -f "${PHYSX_DIR}/bin/linux.clang/release/libPhysXGpu_64.so" ]]; then
    export PM_PhysXGpu_PATH="${PHYSX_DIR}"
    echo "==> PhysXGpu present under ${PHYSX_DIR}/bin"
    return 0
  fi

  # Search common packman cache locations (host RO mount, build-tree, HOME).
  local cand=""
  local d
  for d in \
    ${PM_PhysXGpu_PATH:-} \
    /packman-physxgpu/*linux* \
    /tmp/packman-cache/chk/PhysXGpu/*linux* \
    /out/packman-cache/chk/PhysXGpu/*linux* \
    /tmp/.cache/packman/chk/PhysXGpu/*linux* \
    "${HOME}/.cache/packman/chk/PhysXGpu/"*linux* \
    "${HOME}/.packman/chk/PhysXGpu/"*linux*; do
    if [[ -n "${d}" && -f "${d}/bin/linux.clang/release/libPhysXGpu_64.so" ]]; then
      cand="${d}"
      break
    fi
  done

  if [[ -z "${cand}" ]]; then
    echo "==> Pulling PhysXGpu via packman (needs network)"
    (
      cd "${PHYSX_DIR}"
      # Bootstrap packman python / fetch dependency packages for linux.
      if [[ -x ./buildtools/packman/packman ]]; then
        # pull all packages listed for this platform
        # packman wants --platform (not +platform-linux).
        ./buildtools/packman/packman pull dependencies.xml --platform linux \
          || ./buildtools/packman/packman pull dependencies.xml \
          || true
      fi
    )
    for d in \
      /tmp/packman-cache/chk/PhysXGpu/*linux* \
      /tmp/.cache/packman/chk/PhysXGpu/*linux* \
      "${HOME}/.cache/packman/chk/PhysXGpu/"*linux* \
      "${PHYSX_DIR}/../.."/*/PhysXGpu/*linux*; do
      if [[ -n "${d}" && -f "${d}/bin/linux.clang/release/libPhysXGpu_64.so" ]]; then
        cand="${d}"
        break
      fi
    done
    # generate_projects also runs packman — try a dry generate to populate cache
    if [[ -z "${cand}" ]]; then
      (
        cd "${PHYSX_DIR}"
        unset PM_PhysXGpu_PATH || true
        ./generate_projects.sh linux-gcc 2>/dev/null || ./generate_projects.sh linux 2>/dev/null || true
      )
      cand="$(find /tmp /out "${HOME}" "${PHYSX_DIR}" -path '*/PhysXGpu/*/bin/linux.clang/release/libPhysXGpu_64.so' 2>/dev/null | head -1 | xargs -r dirname | xargs -r dirname | xargs -r dirname || true)"
      # cand should be package root containing bin/
      if [[ -n "${cand}" && ! -f "${cand}/bin/linux.clang/release/libPhysXGpu_64.so" ]]; then
        # walk up from the .so
        local so
        so="$(find /tmp /out "${HOME}" "${PHYSX_DIR}" -path '*/bin/linux.clang/release/libPhysXGpu_64.so' 2>/dev/null | head -1 || true)"
        if [[ -n "${so}" ]]; then
          cand="$(cd "$(dirname "${so}")/../../.." && pwd)"
        fi
      fi
    fi
  fi

  if [[ -z "${cand}" || ! -f "${cand}/bin/linux.clang/release/libPhysXGpu_64.so" ]]; then
    # Last resort: find any libPhysXGpu_64.so and synthesize expected layout under PHYSX_DIR.
    local so
    so="$(find /tmp /out "${HOME}" -name 'libPhysXGpu_64.so' 2>/dev/null | head -1 || true)"
    if [[ -n "${so}" ]]; then
      echo "==> Staging PhysXGpu from ${so}"
      mkdir -p "${PHYSX_DIR}/bin/linux.clang/"{release,checked,profile,debug}
      for cfg in release checked profile debug; do
        cp -a "${so}" "${PHYSX_DIR}/bin/linux.clang/${cfg}/libPhysXGpu_64.so"
      done
      export PM_PhysXGpu_PATH="${PHYSX_DIR}"
      return 0
    fi
    echo "ERROR: could not obtain libPhysXGpu_64.so (packman PhysXGpu package)" >&2
    return 1
  fi

  echo "==> Using PhysXGpu package at ${cand}"
  # Copy into PhysX tree so FILE COPY paths resolve with PM_PhysXGpu_PATH=PHYSX_DIR.
  mkdir -p "${PHYSX_DIR}/bin"
  cp -a "${cand}/bin/." "${PHYSX_DIR}/bin/"
  export PM_PhysXGpu_PATH="${PHYSX_DIR}"
}

if [[ -f "${PRESET_DIR}/linux.xml" ]]; then
  cp "${PRESET_DIR}/linux.xml" "${PRESET_DIR}/linux-gcc.xml"
  sed -i \
    -e 's/compiler="clang"/compiler="gcc"/g' \
    -e 's/clang/gcc/g' \
    -e 's/Clang/Gcc/g' \
    -e 's/name="PX_BUILDSNIPPETS" value="True"/name="PX_BUILDSNIPPETS" value="False"/g' \
    -e 's/name="PX_BUILDPVDRUNTIME" value="True"/name="PX_BUILDPVDRUNTIME" value="False"/g' \
    -e 's/name="PX_GENERATE_STATIC_LIBRARIES" value="False"/name="PX_GENERATE_STATIC_LIBRARIES" value="True"/g' \
    "${PRESET_DIR}/linux-gcc.xml" || true
  if ! grep -q 'PX_GENERATE_STATIC_LIBRARIES' "${PRESET_DIR}/linux-gcc.xml"; then
    sed -i 's|</CMakeSwitches>|    <cmakeSwitch name="PX_GENERATE_STATIC_LIBRARIES" value="True" comment="static" />\n  </CMakeSwitches>|' \
      "${PRESET_DIR}/linux-gcc.xml" || true
  fi
fi

ensure_physx_gpu

echo "==> generate_projects (gcc)"
(
  cd "${PHYSX_DIR}"
  rm -rf compiler/linux-release compiler/linux-checked compiler/linux-debug compiler/linux-profile \
    compiler/linux-gcc* 2>/dev/null || true
  if [[ ! -x ./generate_projects.sh ]]; then
    echo "ERROR: generate_projects.sh missing" >&2
    exit 1
  fi
  export PM_PhysXGpu_PATH="${PM_PhysXGpu_PATH:-${PHYSX_DIR}}"
  # Writable packman root (avoid root-owned host caches).
  export PM_PACKAGES_ROOT="${PM_PACKAGES_ROOT:-${PHYSX_DIR}/../../packman-cache}"
  mkdir -p "${PM_PACKAGES_ROOT}" || true
  set +e
  ./generate_projects.sh linux-gcc
  gen_rc=$?
  if [[ ${gen_rc} -ne 0 ]]; then
    ./generate_projects.sh linux
    gen_rc=$?
  fi
  set -e
  # generate_projects may return non-zero if packman warns; accept Makefile presence.
  if [[ ! -f compiler/linux-release/Makefile && ! -f compiler/linux-release/build.ninja ]]; then
    echo "ERROR: generate_projects failed (exit ${gen_rc})" >&2
    exit 1
  fi
)

BUILD_DIR=""
for cand in \
  "${PHYSX_DIR}/compiler/linux-release" \
  "${PHYSX_DIR}/compiler/linux-checked"; do
  if [[ -f "${cand}/Makefile" || -f "${cand}/build.ninja" ]]; then
    BUILD_DIR="${cand}"
    break
  fi
done
if [[ -z "${BUILD_DIR}" ]]; then
  BUILD_DIR="$(ls -d "${PHYSX_DIR}/compiler/"*release* 2>/dev/null | head -1 || true)"
fi
if [[ -z "${BUILD_DIR}" || ( ! -f "${BUILD_DIR}/Makefile" && ! -f "${BUILD_DIR}/build.ninja" ) ]]; then
  echo "ERROR: no PhysX build directory with Makefile under ${PHYSX_DIR}/compiler" >&2
  ls -la "${PHYSX_DIR}/compiler" 2>&1 || true
  exit 1
fi

echo "==> Building PhysX in ${BUILD_DIR} (-j${JOBS})"
# GCC 13+ treats several PhysX 5.4 warnings as errors; disable -Werror for the SDK build.
export CXXFLAGS="${CXXFLAGS:-} -Wno-error -Wno-stringop-overread -Wno-nonnull -Wno-error=stringop-overread -Wno-error=nonnull"
export CFLAGS="${CFLAGS:-} -Wno-error"
targets=(PhysX PhysXCommon PhysXFoundation PhysXCooking PhysXExtensions PhysXPvdSDK
         PhysXCharacterKinematic PhysXVehicle PhysXVehicle2)
(
  cd "${BUILD_DIR}"
  # Re-inject flags into the generated cache (generate_projects already configured once).
  cmake . \
    -DCMAKE_CXX_FLAGS="${CXXFLAGS}" \
    -DCMAKE_C_FLAGS="${CFLAGS}" \
    >/dev/null
  cmake --build . -j"${JOBS}" --target "${targets[@]}"
)

BIN_DIR="$(ls -d "${PHYSX_DIR}/bin/"*/release 2>/dev/null | head -1 || true)"
if [[ -z "${BIN_DIR}" ]]; then
  BIN_DIR="$(ls -d "${PHYSX_DIR}/bin/"*/checked 2>/dev/null | head -1 || true)"
fi
if [[ -z "${BIN_DIR}" ]]; then
  echo "ERROR: PhysX bin directory not found" >&2
  find "${PHYSX_DIR}/bin" -maxdepth 3 -type d 2>/dev/null | head -40
  exit 1
fi

echo "==> Installing → ${INSTALL}"
rm -rf "${INSTALL}/include" "${INSTALL}/lib"
mkdir -p "${INSTALL}/include" "${INSTALL}/lib" "${INSTALL}/bin"
cp -a "${PHYSX_DIR}/include/." "${INSTALL}/include/"
find "${BIN_DIR}" -maxdepth 1 -name '*.a' -exec cp -a {} "${INSTALL}/lib/" \;
if ! ls "${INSTALL}/lib/"*.a >/dev/null 2>&1; then
  find "${PHYSX_DIR}/bin" -name '*.a' -exec cp -a {} "${INSTALL}/lib/" \;
fi

GPU_SO="$(find "${BIN_DIR}" "${PHYSX_DIR}/bin" -name 'libPhysXGpu_64.so' 2>/dev/null | head -1 || true)"
if [[ -n "${GPU_SO}" ]]; then
  cp -a "${GPU_SO}" "${INSTALL}/bin/libPhysXGpu_64.so"
  echo "==> Installed ${INSTALL}/bin/libPhysXGpu_64.so"
else
  echo "WARN: libPhysXGpu_64.so not found; GPU rigid bodies will fail at runtime" >&2
fi

if [[ ! -f "${INSTALL}/lib/libPhysX_static_64.a" ]]; then
  echo "ERROR: libPhysX_static_64.a missing after install" >&2
  ls -la "${INSTALL}/lib" || true
  exit 1
fi

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
ls -la "${INSTALL}/bin" 2>/dev/null | head || true
