#pragma once

#include "sampling.h"
#include "vec.h"

#include <cuda_runtime.h>

namespace nrtx {

__forceinline__ __host__ __device__ float saturatef(float x) {
  return fminf(1.0f, fmaxf(0.0f, x));
}

__forceinline__ __host__ __device__ float3 fresnel_schlick3(float cos_theta, const float3 &f0) {
  const float m = 1.0f - cos_theta;
  const float m2 = m * m;
  const float w = m2 * m2 * m;
  return f0 + (make_float3(1.0f, 1.0f, 1.0f) - f0) * w;
}

__forceinline__ __host__ __device__ float ggx_d(float n_dot_h, float a2) {
  const float d = n_dot_h * n_dot_h * (a2 - 1.0f) + 1.0f;
  return a2 / (3.14159265f * d * d);
}

/** Exact GGX Smith G1 (Heitz); matches VNDF PDF. */
__forceinline__ __host__ __device__ float smith_g1_ggx(float n_dot_x, float a) {
  const float cos_theta = saturatef(n_dot_x);
  if (cos_theta < 1e-6f) {
    return 0.0f;
  }
  const float tan2 = (1.0f - cos_theta * cos_theta) / (cos_theta * cos_theta);
  return 2.0f / (1.0f + sqrtf(1.0f + a * a * tan2));
}

__forceinline__ __host__ __device__ float smith_g_ggx(float n_dot_v, float n_dot_l, float a) {
  return smith_g1_ggx(n_dot_v, a) * smith_g1_ggx(n_dot_l, a);
}

/**
 * Heitz JCGT 2018 GGX VNDF (isotropic αx=αy=a).
 * Samples microfacet normal h with PDF D_v(h) = G1(v) max(0,v·h) D(h) / (n·v).
 */
__forceinline__ __host__ __device__ float3 sample_ggx_vndf(unsigned &seed, const float3 &n,
                                                          const float3 &wo, float roughness) {
  const float a = fmaxf(roughness, 0.045f);
  float3 t, b;
  orthonormal_basis(n, t, b);
  // View in local frame (n = +Z).
  float3 Ve = make_float3(dot(wo, t), dot(wo, b), dot(wo, n));
  if (Ve.z < 1e-6f) {
    Ve.z = 1e-6f;
  }
  Ve = normalize(Ve);

  // Section 3.2: stretch to hemisphere configuration.
  float3 Vh = normalize(make_float3(a * Ve.x, a * Ve.y, Ve.z));

  // Section 4.1: orthonormal basis around Vh.
  const float lensq = Vh.x * Vh.x + Vh.y * Vh.y;
  const float3 T1 = lensq > 0.0f
                        ? make_float3(-Vh.y, Vh.x, 0.0f) * (1.0f / sqrtf(lensq))
                        : make_float3(1.0f, 0.0f, 0.0f);
  const float3 T2 = cross(Vh, T1);

  // Section 4.2: sample projected area (unit disk + warp).
  const float U1 = rnd(seed);
  const float U2 = rnd(seed);
  const float r = sqrtf(U1);
  const float phi = 2.0f * 3.14159265f * U2;
  float t1 = r * cosf(phi);
  float t2 = r * sinf(phi);
  const float s = 0.5f * (1.0f + Vh.z);
  t2 = (1.0f - s) * sqrtf(fmaxf(0.0f, 1.0f - t1 * t1)) + s * t2;

  // Section 4.3: reproject onto hemisphere.
  const float3 Nh =
      T1 * t1 + T2 * t2 + Vh * sqrtf(fmaxf(0.0f, 1.0f - t1 * t1 - t2 * t2));

  // Section 3.4: unstretch back to ellipsoid.
  const float3 Ne = normalize(make_float3(a * Nh.x, a * Nh.y, fmaxf(Nh.z, 0.0f)));
  return normalize(t * Ne.x + b * Ne.y + n * Ne.z);
}

/** Solid-angle PDF for reflecting wo → wi when h was sampled from GGX VNDF. */
__forceinline__ __host__ __device__ float pdf_ggx_vndf_reflect(const float3 &n, const float3 &wo,
                                                             const float3 &wi, float roughness) {
  const float n_dot_v = dot(n, wo);
  const float n_dot_l = dot(n, wi);
  if (n_dot_v <= 0.0f || n_dot_l <= 0.0f) {
    return 0.0f;
  }
  const float3 h = normalize(wo + wi);
  const float n_dot_h = fmaxf(dot(n, h), 0.0f);
  const float v_dot_h = fmaxf(dot(wo, h), 0.0f);
  if (n_dot_h < 1e-6f || v_dot_h < 1e-6f) {
    return 0.0f;
  }
  const float a = fmaxf(roughness, 0.045f);
  const float a2 = a * a;
  const float D = ggx_d(n_dot_h, a2);
  const float G1 = smith_g1_ggx(n_dot_v, a);
  const float pdf_h = G1 * v_dot_h * D / fmaxf(n_dot_v, 1e-6f);
  return pdf_h / fmaxf(4.0f * v_dot_h, 1e-6f);
}

// Evaluate opaque metallic-roughness BRDF. Returns f (not f*cos). Sets pdf_out.
__forceinline__ __host__ __device__ float3 eval_opaque_bsdf(const float3 &base_color, float metallic,
                                                           float roughness, const float3 &n,
                                                           const float3 &wo, const float3 &wi,
                                                           float &pdf_out) {
  pdf_out = 0.0f;
  const float n_dot_l = dot(n, wi);
  const float n_dot_v = dot(n, wo);
  if (n_dot_l <= 0.0f || n_dot_v <= 0.0f) {
    return make_float3(0.0f, 0.0f, 0.0f);
  }

  const float3 h = normalize(wo + wi);
  const float n_dot_h = fmaxf(dot(n, h), 0.0f);
  const float v_dot_h = fmaxf(dot(wo, h), 0.0f);

  const float a = fmaxf(roughness, 0.045f);
  const float a2 = a * a;

  const float3 f0 = lerp(make_float3(0.04f, 0.04f, 0.04f), base_color, metallic);
  const float3 F = fresnel_schlick3(v_dot_h, f0);
  const float D = ggx_d(n_dot_h, a2);
  const float G = smith_g_ggx(n_dot_v, n_dot_l, a);

  const float3 spec = F * (D * G / fmaxf(4.0f * n_dot_v * n_dot_l, 1e-6f));
  const float f_avg = (F.x + F.y + F.z) * (1.0f / 3.0f);
  const float3 brdf =
      base_color * ((1.0f - metallic) * (1.0f - f_avg) * (1.0f / 3.14159265f)) + spec;

  const float pdf_spec = pdf_ggx_vndf_reflect(n, wo, wi, roughness);
  const float pdf_diff = n_dot_l * (1.0f / 3.14159265f);

  const float w_spec = saturatef(metallic + (1.0f - metallic) * f_avg);
  const float w_diff = 1.0f - w_spec;
  pdf_out = w_diff * pdf_diff + w_spec * pdf_spec;
  return brdf;
}

struct BsdfSample {
  float3 wi;
  float3 f;
  float pdf;
  bool valid;
  bool transmitted; // dielectric refraction (rough glass)
};

__forceinline__ __host__ __device__ float fresnel_schlick(float cos_theta, float f0) {
  const float m = 1.0f - cos_theta;
  const float m2 = m * m;
  return f0 + (1.0f - f0) * m2 * m2 * m;
}

// wo points away from the interface; eta = eta_i / eta_t (Snell).
__forceinline__ __host__ __device__ bool refract_wo(const float3 &wo, const float3 &n, float eta,
                                                   float3 &wi) {
  const float cos_i = dot(wo, n);
  const float sin2_t = eta * eta * fmaxf(0.0f, 1.0f - cos_i * cos_i);
  if (sin2_t > 1.0f) {
    return false;
  }
  const float cos_t = sqrtf(1.0f - sin2_t);
  wi = (eta * cos_i - cos_t) * n - eta * wo;
  return true;
}

// GGX microfacet dielectric (Walter / Heitz VNDF). Returns MC weight in f with pdf=1
// (f already includes the cos/pdf factor via G1(wi)). No NEE/MIS — caller skips those.
__forceinline__ __host__ __device__ BsdfSample sample_dielectric_bsdf(unsigned &seed,
                                                                     const float3 &base_color,
                                                                     float roughness, float ior,
                                                                     const float3 &n,
                                                                     const float3 &wo,
                                                                     bool entering) {
  BsdfSample out;
  out.valid = false;
  out.transmitted = false;
  out.pdf = 1.0f;
  out.f = make_float3(0.0f, 0.0f, 0.0f);
  out.wi = make_float3(0.0f, 0.0f, 0.0f);

  if (dot(n, wo) <= 0.0f) {
    return out;
  }

  const float ior_safe = fmaxf(ior, 1.0001f);
  const float a = fmaxf(roughness, 0.045f);
  const float eta = entering ? (1.0f / ior_safe) : ior_safe;

  float3 h = sample_ggx_vndf(seed, n, wo, roughness);
  if (dot(h, n) < 0.0f) {
    h = -h;
  }

  const float wo_dot_h = fmaxf(dot(wo, h), 0.0f);
  const float f0 = powf((1.0f - ior_safe) / (1.0f + ior_safe), 2.0f);
  float F = fresnel_schlick(wo_dot_h, f0);

  float3 wi_t;
  const bool can_transmit = refract_wo(wo, h, eta, wi_t);
  if (!can_transmit) {
    F = 1.0f;
  }

  if (rnd(seed) < F || !can_transmit) {
    const float3 wi = normalize(2.0f * wo_dot_h * h - wo);
    if (dot(n, wi) <= 0.0f) {
      return out;
    }
    const float g1 = smith_g1_ggx(fmaxf(dot(n, wi), 1e-6f), a);
    out.wi = wi;
    out.f = make_float3(g1, g1, g1);
    out.pdf = 1.0f;
    out.valid = true;
    out.transmitted = false;
    return out;
  }

  const float3 wi = normalize(wi_t);
  if (dot(n, wi) >= 0.0f) {
    return out;
  }
  const float g1 = smith_g1_ggx(fmaxf(-dot(n, wi), 1e-6f), a);
  out.wi = wi;
  out.f = base_color * g1;
  out.pdf = 1.0f;
  out.valid = true;
  out.transmitted = true;
  return out;
}

__forceinline__ __host__ __device__ BsdfSample sample_opaque_bsdf(unsigned &seed,
                                                                 const float3 &base_color,
                                                                 float metallic, float roughness,
                                                                 const float3 &n, const float3 &wo) {
  BsdfSample out;
  out.valid = false;
  out.transmitted = false;
  out.pdf = 0.0f;
  out.f = make_float3(0.0f, 0.0f, 0.0f);
  out.wi = make_float3(0.0f, 0.0f, 0.0f);

  if (dot(n, wo) <= 0.0f) {
    return out;
  }

  const float3 f0 = lerp(make_float3(0.04f, 0.04f, 0.04f), base_color, metallic);
  const float f_approx = (f0.x + f0.y + f0.z) * (1.0f / 3.0f);
  const float w_spec = saturatef(metallic + (1.0f - metallic) * f_approx);

  float3 wi;
  if (rnd(seed) < w_spec) {
    const float3 h = sample_ggx_vndf(seed, n, wo, roughness);
    wi = normalize(2.0f * fmaxf(dot(wo, h), 0.0f) * h - wo);
  } else {
    wi = cosine_sample_hemisphere(seed, n);
  }

  if (dot(n, wi) <= 0.0f) {
    return out;
  }

  float pdf = 0.0f;
  const float3 f = eval_opaque_bsdf(base_color, metallic, roughness, n, wo, wi, pdf);
  if (pdf < 1e-8f) {
    return out;
  }
  out.wi = wi;
  out.f = f;
  out.pdf = pdf;
  out.valid = true;
  return out;
}

__forceinline__ __host__ __device__ float mis_balance(float pdf_a, float pdf_b) {
  const float a = fmaxf(pdf_a, 0.0f);
  const float b = fmaxf(pdf_b, 0.0f);
  const float sum = a + b;
  return sum > 0.0f ? a / sum : 0.0f;
}

} // namespace nrtx
