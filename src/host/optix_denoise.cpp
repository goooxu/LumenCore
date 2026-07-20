// Standalone OptiX HDR denoiser for post-processing Vulkan (or other) float RGB buffers.
#include "nrtx/nrtx.h"

#include <optix.h>
#include <optix_stubs.h>
// optix_function_table_definition.h is provided once in renderer.cpp

#include <cuda_runtime.h>

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace nrtx {
namespace {

#define CUDA_CHECK(call)                                                                           \
  do {                                                                                             \
    const cudaError_t err = call;                                                                  \
    if (err != cudaSuccess) {                                                                      \
      throw std::runtime_error(std::string("CUDA error: ") + cudaGetErrorString(err) + " @ " +     \
                               #call);                                                             \
    }                                                                                              \
  } while (0)

#define OPTIX_CHECK(call)                                                                          \
  do {                                                                                             \
    const OptixResult res = call;                                                                  \
    if (res != OPTIX_SUCCESS) {                                                                    \
      throw std::runtime_error(std::string("OptiX error ") + std::to_string(static_cast<int>(res)) + \
                               " @ " + #call);                                                     \
    }                                                                                              \
  } while (0)

struct DenoiseContext {
  OptixDeviceContext context = nullptr;
  OptixDenoiser denoiser = nullptr;
  OptixDenoiserSizes sizes = {};
  CUdeviceptr state = 0;
  CUdeviceptr scratch = 0;
  size_t state_bytes = 0;
  size_t scratch_bytes = 0;
  int width = 0;
  int height = 0;
  bool inited = false;

  void ensure(int w, int h) {
    if (!inited) {
      CUDA_CHECK(cudaFree(0));
      OPTIX_CHECK(optixInit());
      OptixDeviceContextOptions options = {};
      options.logCallbackFunction = nullptr;
      options.logCallbackLevel = 0;
      CUcontext cu_ctx = 0;
      OPTIX_CHECK(optixDeviceContextCreate(cu_ctx, &options, &context));
      inited = true;
    }
    if (denoiser && (w != width || h != height)) {
      optixDenoiserDestroy(denoiser);
      denoiser = nullptr;
      if (state) {
        cudaFree(reinterpret_cast<void *>(state));
        state = 0;
      }
      if (scratch) {
        cudaFree(reinterpret_cast<void *>(scratch));
        scratch = 0;
      }
    }
    if (!denoiser) {
      OptixDenoiserOptions dopt = {};
      dopt.guideAlbedo = 1;
      dopt.guideNormal = 1;
      OPTIX_CHECK(optixDenoiserCreate(context, OPTIX_DENOISER_MODEL_KIND_HDR, &dopt, &denoiser));
      OPTIX_CHECK(optixDenoiserComputeMemoryResources(denoiser, w, h, &sizes));
      state_bytes = sizes.stateSizeInBytes;
      scratch_bytes = sizes.withoutOverlapScratchSizeInBytes;
      CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&state), state_bytes));
      CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&scratch), scratch_bytes));
      OPTIX_CHECK(optixDenoiserSetup(denoiser, 0, w, h, state, state_bytes, scratch, scratch_bytes));
      width = w;
      height = h;
    }
  }
};

DenoiseContext &ctx() {
  static DenoiseContext c;
  return c;
}

} // namespace

bool vulkan_denoise_available() {
#if defined(LUMENCORE_HAS_VULKAN)
  // Vulkan path post-processes with OptiX Denoiser (albedo/normal AOVs).
  return true;
#else
  return false;
#endif
}

void denoise_hdr_rgb(int width, int height, float *beauty_rgb, const float *albedo_rgb,
                     const float *normal_rgb) {
  if (width <= 0 || height <= 0 || !beauty_rgb || !albedo_rgb || !normal_rgb) {
    throw std::runtime_error("denoise_hdr_rgb: invalid arguments");
  }
  const size_t n = static_cast<size_t>(width) * static_cast<size_t>(height);
  ctx().ensure(width, height);

  std::vector<float4> beauty(n);
  std::vector<float3> albedo(n);
  std::vector<float3> normal(n);
  for (size_t i = 0; i < n; ++i) {
    beauty[i] = make_float4(beauty_rgb[i * 3 + 0], beauty_rgb[i * 3 + 1], beauty_rgb[i * 3 + 2], 1.f);
    albedo[i] = make_float3(albedo_rgb[i * 3 + 0], albedo_rgb[i * 3 + 1], albedo_rgb[i * 3 + 2]);
    float3 nn = make_float3(normal_rgb[i * 3 + 0], normal_rgb[i * 3 + 1], normal_rgb[i * 3 + 2]);
    const float len2 = nn.x * nn.x + nn.y * nn.y + nn.z * nn.z;
    if (len2 > 1e-12f) {
      const float inv = 1.f / sqrtf(len2);
      nn.x *= inv;
      nn.y *= inv;
      nn.z *= inv;
    } else {
      nn = make_float3(0.f, 0.f, 1.f);
    }
    normal[i] = nn;
  }

  float4 *d_beauty = nullptr;
  float3 *d_albedo = nullptr;
  float3 *d_normal = nullptr;
  float4 *d_out = nullptr;
  CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_beauty), n * sizeof(float4)));
  CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_albedo), n * sizeof(float3)));
  CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_normal), n * sizeof(float3)));
  CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_out), n * sizeof(float4)));
  CUDA_CHECK(cudaMemcpy(d_beauty, beauty.data(), n * sizeof(float4), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(d_albedo, albedo.data(), n * sizeof(float3), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(d_normal, normal.data(), n * sizeof(float3), cudaMemcpyHostToDevice));

  OptixDenoiserParams dparams = {};
  dparams.hdrIntensity = 0;
  dparams.blendFactor = 0.0f;
  dparams.hdrAverageColor = 0;
  dparams.temporalModeUsePreviousLayers = 0;

  auto make_img4 = [&](float4 *ptr) {
    OptixImage2D img = {};
    img.data = reinterpret_cast<CUdeviceptr>(ptr);
    img.width = width;
    img.height = height;
    img.rowStrideInBytes = width * sizeof(float4);
    img.pixelStrideInBytes = sizeof(float4);
    img.format = OPTIX_PIXEL_FORMAT_FLOAT4;
    return img;
  };
  auto make_img3 = [&](float3 *ptr) {
    OptixImage2D img = {};
    img.data = reinterpret_cast<CUdeviceptr>(ptr);
    img.width = width;
    img.height = height;
    img.rowStrideInBytes = width * sizeof(float3);
    img.pixelStrideInBytes = sizeof(float3);
    img.format = OPTIX_PIXEL_FORMAT_FLOAT3;
    return img;
  };

  OptixDenoiserGuideLayer guide = {};
  guide.albedo = make_img3(d_albedo);
  guide.normal = make_img3(d_normal);
  OptixDenoiserLayer layer = {};
  layer.input = make_img4(d_beauty);
  layer.output = make_img4(d_out);

  OPTIX_CHECK(optixDenoiserInvoke(ctx().denoiser, 0, &dparams, ctx().state, ctx().state_bytes, &guide,
                                  &layer, 1, 0, 0, ctx().scratch, ctx().scratch_bytes));
  CUDA_CHECK(cudaDeviceSynchronize());

  std::vector<float4> out(n);
  CUDA_CHECK(cudaMemcpy(out.data(), d_out, n * sizeof(float4), cudaMemcpyDeviceToHost));
  for (size_t i = 0; i < n; ++i) {
    beauty_rgb[i * 3 + 0] = out[i].x;
    beauty_rgb[i * 3 + 1] = out[i].y;
    beauty_rgb[i * 3 + 2] = out[i].z;
  }

  cudaFree(d_beauty);
  cudaFree(d_albedo);
  cudaFree(d_normal);
  cudaFree(d_out);
}

} // namespace nrtx
