#pragma once

#include <cmath>
#include <cuda_runtime.h>
#include <vector_functions.h>

#ifndef __CUDACC__
#include <algorithm>
#endif

__forceinline__ __host__ __device__ float3 operator+(const float3 &a, const float3 &b) {
  return make_float3(a.x + b.x, a.y + b.y, a.z + b.z);
}
__forceinline__ __host__ __device__ float3 operator-(const float3 &a, const float3 &b) {
  return make_float3(a.x - b.x, a.y - b.y, a.z - b.z);
}
__forceinline__ __host__ __device__ float3 operator-(const float3 &a) {
  return make_float3(-a.x, -a.y, -a.z);
}
__forceinline__ __host__ __device__ float3 operator*(const float3 &a, const float3 &b) {
  return make_float3(a.x * b.x, a.y * b.y, a.z * b.z);
}
__forceinline__ __host__ __device__ float3 operator*(const float3 &a, float s) {
  return make_float3(a.x * s, a.y * s, a.z * s);
}
__forceinline__ __host__ __device__ float3 operator*(float s, const float3 &a) {
  return a * s;
}
__forceinline__ __host__ __device__ float2 operator*(const float2 &a, float s) {
  return make_float2(a.x * s, a.y * s);
}
__forceinline__ __host__ __device__ float2 operator*(float s, const float2 &a) {
  return a * s;
}
__forceinline__ __host__ __device__ float2 operator+(const float2 &a, const float2 &b) {
  return make_float2(a.x + b.x, a.y + b.y);
}
__forceinline__ __host__ __device__ float3 operator/(const float3 &a, float s) {
  return make_float3(a.x / s, a.y / s, a.z / s);
}
__forceinline__ __host__ __device__ float3 &operator+=(float3 &a, const float3 &b) {
  a.x += b.x;
  a.y += b.y;
  a.z += b.z;
  return a;
}
__forceinline__ __host__ __device__ float3 &operator*=(float3 &a, float s) {
  a.x *= s;
  a.y *= s;
  a.z *= s;
  return a;
}

namespace nrtx {

__forceinline__ __host__ __device__ float dot(const float3 &a, const float3 &b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}
__forceinline__ __host__ __device__ float3 cross(const float3 &a, const float3 &b) {
  return make_float3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z,
                     a.x * b.y - a.y * b.x);
}
__forceinline__ __host__ __device__ float length(const float3 &a) {
  return sqrtf(dot(a, a));
}
__forceinline__ __host__ __device__ float3 normalize(const float3 &a) {
  return a / length(a);
}
__forceinline__ __host__ __device__ float clamp(float v, float lo, float hi) {
#ifdef __CUDACC__
  return fminf(hi, fmaxf(lo, v));
#else
  return std::min(hi, std::max(lo, v));
#endif
}
__forceinline__ __host__ __device__ float3 clamp(const float3 &v, float lo, float hi) {
  return make_float3(clamp(v.x, lo, hi), clamp(v.y, lo, hi), clamp(v.z, lo, hi));
}
__forceinline__ __host__ __device__ float luminance(const float3 &c) {
  return 0.2126f * c.x + 0.7152f * c.y + 0.0722f * c.z;
}
__forceinline__ __host__ __device__ float3 lerp(const float3 &a, const float3 &b, float t) {
  return a * (1.0f - t) + b * t;
}

} // namespace nrtx
