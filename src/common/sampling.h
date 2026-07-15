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

} // namespace nrtx
