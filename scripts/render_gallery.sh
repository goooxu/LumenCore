#!/usr/bin/env bash
# Build once, then render gallery showcase + feature compares in parallel
# across host GPUs via NRTX_GPU (see docker/run.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

NUM_GPUS="${NRTX_NUM_GPUS:-}"
if [[ -z "${NUM_GPUS}" ]]; then
  NUM_GPUS="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU' || true)"
fi
NUM_GPUS="${NUM_GPUS:-1}"
if [[ "${NUM_GPUS}" -lt 1 ]]; then
  NUM_GPUS=1
fi

# Default arch: detect from first GPU compute_cap (e.g. 12.0 → 120, 10.0 → 100).
if [[ -z "${NRTX_CUDA_ARCH:-}" ]]; then
  CAP="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')"
  if [[ "${CAP}" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
    CUDA_ARCH="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
  else
    CUDA_ARCH=120
  fi
else
  CUDA_ARCH="${NRTX_CUDA_ARCH}"
fi
SHOWCASE_SPP="${SHOWCASE_SPP:-192}"
COMPARE_SPP="${COMPARE_SPP:-192}"
DENOISER_SPP="${DENOISER_SPP:-24}"
COMPARE_WIDTH="${COMPARE_WIDTH:-1024}"

HOST_OUT="${NRTX_OUT_DIR:-/tmp/LumenCore-out}"
HOST_BUILD="${NRTX_BUILD_DIR:-/tmp/LumenCore-build}"
# Optional machine-local PhysX (e.g. aarch64 build at /tmp/LumenCore-physx).
PHYSX_ROOT="${NRTX_PHYSX_ROOT:-}"
REPO_GALLERY="${ROOT}/outputs/gallery"
mkdir -p "${HOST_OUT}/gallery/compare" "${REPO_GALLERY}/compare"

echo "[render_gallery] root=${ROOT} gpus=${NUM_GPUS} arch=${CUDA_ARCH}"
echo "[render_gallery] host_out=${HOST_OUT} host_build=${HOST_BUILD}"
echo "[render_gallery] physx_root=${PHYSX_ROOT:-<repo third_party/physx>}"

CMAKE_EXTRA=""
if [[ -n "${PHYSX_ROOT}" ]]; then
  CMAKE_EXTRA="-DPHYSX_ROOT=/physx"
fi

run_docker() {
  local gpu="$1"
  shift
  NRTX_GPU="${gpu}" NRTX_BUILD_DIR="${HOST_BUILD}" NRTX_OUT_DIR="${HOST_OUT}" \
    NRTX_PHYSX_ROOT="${PHYSX_ROOT}" \
    ./docker/run.sh "$@"
}

# --- Build once (all GPUs available) ------------------------------------------
echo "[render_gallery] building ..."
run_docker all \
  "cmake -S /work -B /out -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCH} ${CMAKE_EXTRA} && cmake --build /out -j\$(nproc)"

# --- Job list: gpu_index|label|python_cmd -------------------------------------
# Round-robin GPU assignment.
JOBS=()
gpu_i=0
next_gpu() {
  echo "${gpu_i}"
  gpu_i=$(( (gpu_i + 1) % NUM_GPUS ))
}

g=$(next_gpu)
JOBS+=("${g}|showcase|python3 /work/python/scenes/atelier.py /results/gallery/showcase.png ${SHOWCASE_SPP} 1")
g=$(next_gpu)
JOBS+=("${g}|dusk_observatory|python3 /work/python/scenes/dusk_observatory.py /results/gallery/dusk_observatory.png ${SHOWCASE_SPP} 1")
g=$(next_gpu)
JOBS+=("${g}|assembly_hall|python3 /work/python/scenes/assembly_hall.py /results/gallery/assembly_hall.png ${SHOWCASE_SPP} 1")

FEATURES=(normal nee denoiser flame beer)
for feat in "${FEATURES[@]}"; do
  for mode in on off; do
    spp="${COMPARE_SPP}"
    if [[ "${feat}" == "denoiser" ]]; then
      spp="${DENOISER_SPP}"
    fi
    g=$(next_gpu)
    JOBS+=("${g}|${feat}_${mode}|python3 /work/python/scenes/gallery_compare.py --feature ${feat} --mode ${mode} --out /results/gallery/compare/${feat}_${mode}.png --width ${COMPARE_WIDTH} --spp ${spp} --denoise 1")
  done
done

# --- Launch with limited concurrency (= NUM_GPUS) -----------------------------
# Per-GPU FIFO: at most one job per GPU at a time; different GPUs in parallel.
declare -A GPU_PID=()
declare -A GPU_LABEL=()
FAIL=0
LOG_DIR="${HOST_OUT}/gallery_logs"
mkdir -p "${LOG_DIR}"

wait_gpu_slot() {
  local want="$1"
  if [[ -n "${GPU_PID[$want]:-}" ]]; then
    local pid="${GPU_PID[$want]}"
    local label="${GPU_LABEL[$want]}"
    if ! wait "${pid}"; then
      echo "[render_gallery] FAILED job ${label} on GPU ${want}" >&2
      FAIL=1
    else
      echo "[render_gallery] ok ${label} (gpu ${want})"
    fi
    unset "GPU_PID[$want]"
    unset "GPU_LABEL[$want]"
  fi
}

for entry in "${JOBS[@]}"; do
  IFS='|' read -r gpu label cmd <<<"${entry}"
  wait_gpu_slot "${gpu}"
  log="${LOG_DIR}/${label}.log"
  echo "[render_gallery] start ${label} on GPU ${gpu}"
  (
    run_docker "${gpu}" "${cmd}"
  ) >"${log}" 2>&1 &
  GPU_PID[$gpu]=$!
  GPU_LABEL[$gpu]="${label}"
done

# Drain remaining
for gpu in "${!GPU_PID[@]}"; do
  wait_gpu_slot "${gpu}"
done

if [[ "${FAIL}" -ne 0 ]]; then
  echo "[render_gallery] one or more jobs failed; logs in ${LOG_DIR}" >&2
  exit 1
fi

# --- Copy into repo outputs/ --------------------------------------------------
echo "[render_gallery] copying into ${REPO_GALLERY}"
cp -f "${HOST_OUT}/gallery/showcase.png" "${REPO_GALLERY}/showcase.png"
cp -f "${HOST_OUT}/gallery/dusk_observatory.png" "${REPO_GALLERY}/dusk_observatory.png"
cp -f "${HOST_OUT}/gallery/assembly_hall.png" "${REPO_GALLERY}/assembly_hall.png"
cp -f "${HOST_OUT}/gallery/compare/"*.png "${REPO_GALLERY}/compare/"

echo "[render_gallery] done"
ls -la "${REPO_GALLERY}/showcase.png" "${REPO_GALLERY}/dusk_observatory.png" \
  "${REPO_GALLERY}/assembly_hall.png" "${REPO_GALLERY}/compare/"
