// GGX / dielectric BSDF helpers — algorithm aligned with src/common/bsdf.h
#ifndef LUMENCORE_VK_BSDF_GLSL
#define LUMENCORE_VK_BSDF_GLSL

#include "common.glsl"

float saturatef(float x) { return clamp(x, 0.0, 1.0); }

vec3 fresnel_schlick3(float cos_theta, vec3 f0) {
  float m = 1.0 - cos_theta;
  float m2 = m * m;
  float w = m2 * m2 * m;
  return f0 + (vec3(1.0) - f0) * w;
}

float fresnel_schlick_f0(float cos_theta, float f0) {
  float m = 1.0 - cos_theta;
  float m2 = m * m;
  return f0 + (1.0 - f0) * m2 * m2 * m;
}

float ggx_d(float n_dot_h, float a2) {
  float d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0;
  return a2 / (PI * d * d);
}

/** Exact GGX Smith G1 (Heitz); matches VNDF PDF. */
float smith_g1_ggx(float n_dot_x, float a) {
  float cos_theta = saturatef(n_dot_x);
  if (cos_theta < 1e-6) {
    return 0.0;
  }
  float tan2 = (1.0 - cos_theta * cos_theta) / (cos_theta * cos_theta);
  return 2.0 / (1.0 + sqrt(1.0 + a * a * tan2));
}

float smith_g_ggx(float n_dot_v, float n_dot_l, float a) {
  return smith_g1_ggx(n_dot_v, a) * smith_g1_ggx(n_dot_l, a);
}

/** Heitz JCGT 2018 GGX VNDF (isotropic). */
vec3 sample_ggx_vndf(inout uint seed, vec3 n, vec3 wo, float roughness) {
  float a = max(roughness, 0.045);
  vec3 t, b;
  orthonormal_basis(n, t, b);
  vec3 Ve = vec3(dot(wo, t), dot(wo, b), dot(wo, n));
  if (Ve.z < 1e-6) {
    Ve.z = 1e-6;
  }
  Ve = normalize(Ve);

  vec3 Vh = normalize(vec3(a * Ve.x, a * Ve.y, Ve.z));

  float lensq = Vh.x * Vh.x + Vh.y * Vh.y;
  vec3 T1 = lensq > 0.0 ? vec3(-Vh.y, Vh.x, 0.0) * inversesqrt(lensq) : vec3(1.0, 0.0, 0.0);
  vec3 T2 = cross(Vh, T1);

  float U1 = rnd(seed);
  float U2 = rnd(seed);
  float r = sqrt(U1);
  float phi = 2.0 * PI * U2;
  float t1 = r * cos(phi);
  float t2 = r * sin(phi);
  float s = 0.5 * (1.0 + Vh.z);
  t2 = (1.0 - s) * sqrt(max(0.0, 1.0 - t1 * t1)) + s * t2;

  vec3 Nh = T1 * t1 + T2 * t2 + Vh * sqrt(max(0.0, 1.0 - t1 * t1 - t2 * t2));
  vec3 Ne = normalize(vec3(a * Nh.x, a * Nh.y, max(Nh.z, 0.0)));
  return normalize(t * Ne.x + b * Ne.y + n * Ne.z);
}

float pdf_ggx_vndf_reflect(vec3 n, vec3 wo, vec3 wi, float roughness) {
  float n_dot_v = dot(n, wo);
  float n_dot_l = dot(n, wi);
  if (n_dot_v <= 0.0 || n_dot_l <= 0.0) {
    return 0.0;
  }
  vec3 h = normalize(wo + wi);
  float n_dot_h = max(dot(n, h), 0.0);
  float v_dot_h = max(dot(wo, h), 0.0);
  if (n_dot_h < 1e-6 || v_dot_h < 1e-6) {
    return 0.0;
  }
  float a = max(roughness, 0.045);
  float a2 = a * a;
  float D = ggx_d(n_dot_h, a2);
  float G1 = smith_g1_ggx(n_dot_v, a);
  float pdf_h = G1 * v_dot_h * D / max(n_dot_v, 1e-6);
  return pdf_h / max(4.0 * v_dot_h, 1e-6);
}

/** Evaluate opaque MR BRDF. Returns f (not f*cos). Sets pdf_out. */
vec3 eval_opaque_bsdf(vec3 base_color, float metallic, float roughness, vec3 n, vec3 wo, vec3 wi,
                      out float pdf_out) {
  pdf_out = 0.0;
  float n_dot_l = dot(n, wi);
  float n_dot_v = dot(n, wo);
  if (n_dot_l <= 0.0 || n_dot_v <= 0.0) {
    return vec3(0.0);
  }

  vec3 h = normalize(wo + wi);
  float n_dot_h = max(dot(n, h), 0.0);
  float v_dot_h = max(dot(wo, h), 0.0);

  float a = max(roughness, 0.045);
  float a2 = a * a;

  vec3 f0 = mix(vec3(0.04), base_color, metallic);
  vec3 F = fresnel_schlick3(v_dot_h, f0);
  float D = ggx_d(n_dot_h, a2);
  float G = smith_g_ggx(n_dot_v, n_dot_l, a);

  vec3 spec = F * (D * G / max(4.0 * n_dot_v * n_dot_l, 1e-6));
  float f_avg = (F.x + F.y + F.z) * (1.0 / 3.0);
  vec3 brdf = base_color * ((1.0 - metallic) * (1.0 - f_avg) * INV_PI) + spec;

  float pdf_spec = pdf_ggx_vndf_reflect(n, wo, wi, roughness);
  float pdf_diff = n_dot_l * INV_PI;
  float w_spec = saturatef(metallic + (1.0 - metallic) * f_avg);
  float w_diff = 1.0 - w_spec;
  pdf_out = w_diff * pdf_diff + w_spec * pdf_spec;
  return brdf;
}

struct BsdfSample {
  vec3 wi;
  vec3 f; // BRDF value; for opaque MC weight is f*cos/pdf applied by caller
  float pdf;
  bool valid;
  bool transmitted;
};

bool refract_wo(vec3 wo, vec3 n, float eta, out vec3 wi) {
  float cos_i = dot(wo, n);
  float sin2_t = eta * eta * max(0.0, 1.0 - cos_i * cos_i);
  if (sin2_t > 1.0) {
    return false;
  }
  float cos_t = sqrt(1.0 - sin2_t);
  wi = (eta * cos_i - cos_t) * n - eta * wo;
  return true;
}

/** Opaque metallic-roughness sample (cosine + VNDF mixture). */
BsdfSample sample_opaque_bsdf(inout uint seed, vec3 base_color, float metallic, float roughness,
                              vec3 n, vec3 wo) {
  BsdfSample outp;
  outp.valid = false;
  outp.transmitted = false;
  outp.pdf = 0.0;
  outp.f = vec3(0.0);
  outp.wi = vec3(0.0);

  if (dot(n, wo) <= 0.0) {
    return outp;
  }

  vec3 f0 = mix(vec3(0.04), base_color, metallic);
  float f_approx = (f0.x + f0.y + f0.z) * (1.0 / 3.0);
  float w_spec = saturatef(metallic + (1.0 - metallic) * f_approx);

  vec3 wi;
  if (rnd(seed) < w_spec) {
    vec3 h = sample_ggx_vndf(seed, n, wo, roughness);
    wi = normalize(2.0 * max(dot(wo, h), 0.0) * h - wo);
  } else {
    float r1 = rnd(seed);
    float r2 = rnd(seed);
    wi = to_world(cosine_sample_hemisphere(r1, r2), n);
  }

  if (dot(n, wi) <= 0.0) {
    return outp;
  }

  float pdf = 0.0;
  vec3 f = eval_opaque_bsdf(base_color, metallic, roughness, n, wo, wi, pdf);
  if (pdf < 1e-8) {
    return outp;
  }
  outp.wi = wi;
  outp.f = f;
  outp.pdf = pdf;
  outp.valid = true;
  return outp;
}

/**
 * GGX microfacet dielectric. Returns MC weight in f with pdf=1
 * (f already includes cos/pdf via G1(wi)). Caller skips NEE/MIS for glass.
 */
BsdfSample sample_dielectric_bsdf(inout uint seed, vec3 base_color, float roughness, float ior,
                                  vec3 n, vec3 wo, bool entering) {
  BsdfSample outp;
  outp.valid = false;
  outp.transmitted = false;
  outp.pdf = 1.0;
  outp.f = vec3(0.0);
  outp.wi = vec3(0.0);

  if (dot(n, wo) <= 0.0) {
    return outp;
  }

  float ior_safe = max(ior, 1.0001);
  float a = max(roughness, 0.045);
  float eta = entering ? (1.0 / ior_safe) : ior_safe;

  vec3 h = sample_ggx_vndf(seed, n, wo, roughness);
  if (dot(h, n) < 0.0) {
    h = -h;
  }

  float wo_dot_h = max(dot(wo, h), 0.0);
  float f0 = pow((1.0 - ior_safe) / (1.0 + ior_safe), 2.0);
  float F = fresnel_schlick_f0(wo_dot_h, f0);

  vec3 wi_t;
  bool can_transmit = refract_wo(wo, h, eta, wi_t);
  if (!can_transmit) {
    F = 1.0;
  }

  if (rnd(seed) < F || !can_transmit) {
    vec3 wi = normalize(2.0 * wo_dot_h * h - wo);
    if (dot(n, wi) <= 0.0) {
      return outp;
    }
    float g1 = smith_g1_ggx(max(dot(n, wi), 1e-6), a);
    outp.wi = wi;
    outp.f = vec3(g1);
    outp.pdf = 1.0;
    outp.valid = true;
    outp.transmitted = false;
    return outp;
  }

  vec3 wi = normalize(wi_t);
  if (dot(n, wi) >= 0.0) {
    return outp;
  }
  float g1 = smith_g1_ggx(max(-dot(n, wi), 1e-6), a);
  outp.wi = wi;
  outp.f = base_color * g1;
  outp.pdf = 1.0;
  outp.valid = true;
  outp.transmitted = true;
  return outp;
}

float mis_balance(float pdf_a, float pdf_b) {
  float a = max(pdf_a, 0.0);
  float b = max(pdf_b, 0.0);
  float s = a + b;
  return s > 0.0 ? a / s : 0.0;
}

float smoothstep_cone(float edge0, float edge1, float x) {
  float t = saturatef((x - edge0) / max(edge1 - edge0, 1e-6));
  return t * t * (3.0 - 2.0 * t);
}

#endif // LUMENCORE_VK_BSDF_GLSL
