// Shared GLSL definitions for LumenCore Vulkan RT path tracer (Phase 1).
#ifndef LUMENCORE_VK_COMMON_GLSL
#define LUMENCORE_VK_COMMON_GLSL

#extension GL_EXT_ray_tracing : require
#extension GL_EXT_nonuniform_qualifier : enable
#extension GL_EXT_scalar_block_layout : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require
#extension GL_EXT_buffer_reference2 : require

const float PI = 3.14159265358979323846;
const float INV_PI = 0.31830988618379067154;
const float TMIN = 0.001;
const float TMAX = 1.0e4;

struct CameraGPU {
  vec3 eye;
  float pad0;
  vec3 U;
  float pad1;
  vec3 V;
  float pad2;
  vec3 W;
  float lens_radius;
  float focus_dist;
  float pad3;
  float pad4;
  float pad5;
};

struct MaterialGPU {
  vec3 base_color;
  float metallic;
  float roughness;
  float transmission;
  float ior;
  float pad0;
  vec3 emission;
  float pad1;
  vec3 absorption;
  int flags;
};

struct QuadLight {
  vec3 corner;
  float pad0;
  vec3 u;
  float pad1;
  vec3 v;
  float pad2;
  vec3 emission;
  float inv_area;
  int use_mis;
  int pad3;
  int pad4;
  int pad5;
};

// std430-friendly scene params (matches host VulkanLaunchParams).
struct LaunchParams {
  uint64_t tlas; // unused in shader (bound as AS); keep layout sync
  int width;
  int height;
  int sample_index;
  int samples_per_launch;
  int max_depth;
  int material_count;
  int light_count;
  int enable_nee;
  vec3 background_top;
  float pad0;
  vec3 background_bottom;
  float pad1;
  CameraGPU camera;
};

// Radiance payload filled by miss/chit, consumed by rgen.
struct HitPayload {
  vec3 radiance;     // miss: env; chit: emission at hit (path weight applied in rgen)
  vec3 hit_pos;
  vec3 hit_normal;   // geometric outward
  vec3 base_color;
  vec3 emission;
  float metallic;
  float roughness;
  float transmission;
  float ior;
  float t_hit;
  int hit;           // 0 = miss, 1 = hit
  uint seed;
};

// Shadow payload: miss sets visible=1.
struct ShadowPayload {
  uint visible; // 1 if unoccluded
};

// PCG hash (tiny)
uint pcg_hash(uint v) {
  uint state = v * 747796405u + 2891336453u;
  uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
  return (word >> 22u) ^ word;
}

float rnd(inout uint seed) {
  seed = pcg_hash(seed);
  return float(seed) * (1.0 / 4294967296.0);
}

vec3 cosine_sample_hemisphere(float r1, float r2) {
  float phi = 2.0 * PI * r1;
  float r = sqrt(r2);
  float x = r * cos(phi);
  float y = r * sin(phi);
  float z = sqrt(max(0.0, 1.0 - r2));
  return vec3(x, y, z);
}

void orthonormal_basis(vec3 n, out vec3 t, out vec3 b) {
  if (abs(n.y) < 0.999) {
    t = normalize(cross(n, vec3(0.0, 1.0, 0.0)));
  } else {
    t = normalize(cross(n, vec3(1.0, 0.0, 0.0)));
  }
  b = cross(n, t);
}

vec3 to_world(vec3 local, vec3 n) {
  vec3 t, b;
  orthonormal_basis(n, t, b);
  return normalize(local.x * t + local.y * b + local.z * n);
}

vec3 offset_ray_origin(vec3 p, vec3 n) {
  return p + n * 1e-3;
}

float luminance(vec3 c) {
  return 0.2126 * c.x + 0.7152 * c.y + 0.0722 * c.z;
}

// Schlick Fresnel
float fresnel_schlick(float cos_theta, float ior_ratio) {
  float r0 = (1.0 - ior_ratio) / (1.0 + ior_ratio);
  r0 = r0 * r0;
  float m = 1.0 - cos_theta;
  return r0 + (1.0 - r0) * m * m * m * m * m;
}

#endif // LUMENCORE_VK_COMMON_GLSL
