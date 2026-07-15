#pragma once

#include <cuda_runtime.h>
#include <optix.h>
#include <stdint.h>

namespace nrtx {

enum RayType {
  RAY_TYPE_RADIANCE = 0,
  RAY_TYPE_SHADOW = 1,
  RAY_TYPE_COUNT = 2
};

struct MaterialGPU {
  float3 base_color;
  float metallic;
  float roughness;
  float transmission;
  float ior;
  float3 emission;
  int pad;
};

struct QuadLight {
  float3 corner;
  float3 u;
  float3 v;
  float3 emission;
  float inv_area;
  int pad;
};

struct CameraGPU {
  float3 eye;
  float3 U;
  float3 V;
  float3 W;
  float lens_radius;
  float focus_dist;
};

struct LaunchParams {
  OptixTraversableHandle handle;
  float4 *accum_buffer;
  float3 *albedo_buffer;
  float3 *normal_buffer;
  int width;
  int height;
  int sample_index;
  int samples_per_launch;
  int max_depth;
  CameraGPU camera;
  MaterialGPU *materials;
  int material_count;
  QuadLight *lights;
  int light_count;
  float3 background_top;
  float3 background_bottom;
  int enable_nee;
};

struct HitGroupData {
  float3 *vertices;
  int3 *indices;
  int *material_ids;
};

} // namespace nrtx
