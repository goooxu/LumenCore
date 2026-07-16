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

enum MaterialFlags {
  MATERIAL_FLAG_NONE = 0,
  MATERIAL_FLAG_VOLUME_FLAME = 1
};

struct MaterialGPU {
  float3 base_color;
  float metallic;
  float roughness;
  float transmission;
  float ior;
  float3 emission;
  int flags;
  int volume_index;
  int albedo_tex; // -1 = none
  int pad;
};

struct TextureGPU {
  uchar4 *pixels;
  int width;
  int height;
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

struct FlameVolume {
  float3 center;
  float3 half_extents;
  float3 emission_scale;
  float density_scale;
  float absorption;
  float noise_scale;
  float time;
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
  FlameVolume *volumes;
  int volume_count;
  TextureGPU *textures;
  int texture_count;
  float3 background_top;
  float3 background_bottom;
  int enable_nee;
};

struct HitGroupData {
  float3 *vertices;
  float2 *texcoords;
  int3 *indices;
  int *material_ids;
};

} // namespace nrtx
