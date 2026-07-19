#pragma once

#include "vec.h"

namespace nrtx {

__forceinline__ __device__ unsigned tea(unsigned v0, unsigned v1) {
  unsigned s0 = 0;
  for (int n = 0; n < 4; ++n) {
    s0 += 0x9e3779b9;
    v0 += ((v1 << 4) + 0xa341316c) ^ (v1 + s0) ^ ((v1 >> 5) + 0xc8013ea4);
    v1 += ((v0 << 4) + 0xad90777d) ^ (v0 + s0) ^ ((v0 >> 5) + 0x7e95761e);
  }
  return v0;
}

__forceinline__ __device__ unsigned lcg(unsigned &prev) {
  prev = prev * 1664525u + 1013904223u;
  return prev & 0x00ffffffu;
}

__forceinline__ __device__ float rnd(unsigned &prev) {
  return static_cast<float>(lcg(prev)) / static_cast<float>(0x01000000);
}

__forceinline__ __device__ float2 sample_uniform_disk(unsigned &seed) {
  const float r = sqrtf(rnd(seed));
  const float phi = 2.0f * 3.14159265f * rnd(seed);
  return make_float2(r * cosf(phi), r * sinf(phi));
}

__forceinline__ __device__ void orthonormal_basis(const float3 &n, float3 &t, float3 &b) {
  if (fabsf(n.x) > fabsf(n.z)) {
    t = normalize(make_float3(-n.y, n.x, 0.0f));
  } else {
    t = normalize(make_float3(0.0f, -n.z, n.y));
  }
  b = cross(n, t);
}

__forceinline__ __device__ float3 cosine_sample_hemisphere(unsigned &seed, const float3 &n) {
  const float r1 = rnd(seed);
  const float r2 = rnd(seed);
  const float phi = 2.0f * 3.14159265f * r1;
  const float x = cosf(phi) * sqrtf(r2);
  const float y = sinf(phi) * sqrtf(r2);
  const float z = sqrtf(1.0f - r2);
  float3 t, b;
  orthonormal_basis(n, t, b);
  return normalize(t * x + b * y + n * z);
}

/**
 * Ray Tracing Gems Ch.6 — robust origin offset along geometric normal to avoid
 * self-intersection (int-domain nudge for large |p|, float nudge near origin).
 */
__forceinline__ __device__ float3 offset_ray_origin(const float3 &p, const float3 &n) {
  constexpr float kOrigin = 1.0f / 32.0f;
  constexpr float kFloatScale = 1.0f / 65536.0f;
  constexpr float kIntScale = 256.0f;

  const int3 of_i = make_int3(static_cast<int>(kIntScale * n.x), static_cast<int>(kIntScale * n.y),
                              static_cast<int>(kIntScale * n.z));

  const float3 p_i = make_float3(
      __int_as_float(__float_as_int(p.x) + ((p.x < 0.0f) ? -of_i.x : of_i.x)),
      __int_as_float(__float_as_int(p.y) + ((p.y < 0.0f) ? -of_i.y : of_i.y)),
      __int_as_float(__float_as_int(p.z) + ((p.z < 0.0f) ? -of_i.z : of_i.z)));

  return make_float3(fabsf(p.x) < kOrigin ? p.x + kFloatScale * n.x : p_i.x,
                     fabsf(p.y) < kOrigin ? p.y + kFloatScale * n.y : p_i.y,
                     fabsf(p.z) < kOrigin ? p.z + kFloatScale * n.z : p_i.z);
}

} // namespace nrtx
