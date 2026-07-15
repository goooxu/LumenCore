#include <optix.h>

#include "LaunchParams.h"
#include "sampling.h"
#include "vec.h"

extern "C" {
__constant__ nrtx::LaunchParams params;
}

namespace {

struct RadiancePRD {
  float3 origin;
  float3 direction;
  float3 throughput;
  float3 radiance;
  float3 albedo_aov;
  float3 normal_aov;
  unsigned seed;
  int depth;
  int done;
  int first_hit;
};

struct ShadowPRD {
  int occluded;
};

__forceinline__ __device__ void *unpack_pointer(unsigned i0, unsigned i1) {
  const unsigned long long uptr = (static_cast<unsigned long long>(i0) << 32) | i1;
  return reinterpret_cast<void *>(uptr);
}

__forceinline__ __device__ void pack_pointer(void *ptr, unsigned &i0, unsigned &i1) {
  const unsigned long long uptr = reinterpret_cast<unsigned long long>(ptr);
  i0 = static_cast<unsigned>((uptr) >> 32);
  i1 = static_cast<unsigned>(uptr);
}

__forceinline__ __device__ RadiancePRD *get_radiance_prd() {
  const unsigned u0 = optixGetPayload_0();
  const unsigned u1 = optixGetPayload_1();
  return reinterpret_cast<RadiancePRD *>(unpack_pointer(u0, u1));
}

__forceinline__ __device__ ShadowPRD *get_shadow_prd() {
  const unsigned u0 = optixGetPayload_0();
  const unsigned u1 = optixGetPayload_1();
  return reinterpret_cast<ShadowPRD *>(unpack_pointer(u0, u1));
}

__forceinline__ __device__ float3 env_color(const float3 &dir) {
  const float t = 0.5f * (nrtx::normalize(dir).y + 1.0f);
  return nrtx::lerp(params.background_bottom, params.background_top, t);
}

__forceinline__ __device__ bool refract(const float3 &v, const float3 &n, float eta,
                                       float3 &out) {
  const float cos_i = -nrtx::dot(v, n);
  const float sin2_t = eta * eta * (1.0f - cos_i * cos_i);
  if (sin2_t > 1.0f) {
    return false;
  }
  const float cos_t = sqrtf(1.0f - sin2_t);
  out = eta * v + (eta * cos_i - cos_t) * n;
  return true;
}

__forceinline__ __device__ float fresnel_schlick(float cos_theta, float f0) {
  const float m = 1.0f - cos_theta;
  const float m2 = m * m;
  return f0 + (1.0f - f0) * m2 * m2 * m;
}

__forceinline__ __device__ float3 sample_quad_light(const nrtx::QuadLight &light, unsigned &seed,
                                                   float3 &pos, float3 &normal, float &pdf) {
  const float ru = nrtx::rnd(seed);
  const float rv = nrtx::rnd(seed);
  pos = light.corner + light.u * ru + light.v * rv;
  normal = nrtx::normalize(nrtx::cross(light.u, light.v));
  pdf = light.inv_area;
  return light.emission;
}

__forceinline__ __device__ void trace_radiance(RadiancePRD *prd) {
  unsigned p0, p1;
  pack_pointer(prd, p0, p1);
  optixTrace(params.handle, prd->origin, prd->direction, 1e-3f, 1e16f, 0.0f,
             OptixVisibilityMask(255), OPTIX_RAY_FLAG_NONE, nrtx::RAY_TYPE_RADIANCE,
             nrtx::RAY_TYPE_COUNT, nrtx::RAY_TYPE_RADIANCE, p0, p1);
}

__forceinline__ __device__ bool trace_shadow(const float3 &origin, const float3 &dir, float tmax) {
  ShadowPRD prd;
  prd.occluded = 0;
  unsigned p0, p1;
  pack_pointer(&prd, p0, p1);
  optixTrace(params.handle, origin, dir, 1e-3f, tmax - 1e-3f, 0.0f, OptixVisibilityMask(255),
             OPTIX_RAY_FLAG_TERMINATE_ON_FIRST_HIT | OPTIX_RAY_FLAG_DISABLE_CLOSESTHIT,
             nrtx::RAY_TYPE_SHADOW, nrtx::RAY_TYPE_COUNT, nrtx::RAY_TYPE_SHADOW, p0, p1);
  return prd.occluded != 0;
}

} // namespace

extern "C" __global__ void __raygen__rg() {
  const uint3 idx = optixGetLaunchIndex();
  const uint3 dim = optixGetLaunchDimensions();
  const int pixel = idx.y * params.width + idx.x;

  unsigned seed = nrtx::tea(pixel, params.sample_index);

  float3 radiance_sum = make_float3(0.0f, 0.0f, 0.0f);
  float3 albedo_sum = make_float3(0.0f, 0.0f, 0.0f);
  float3 normal_sum = make_float3(0.0f, 0.0f, 0.0f);

  for (int s = 0; s < params.samples_per_launch; ++s) {
    const float u = (static_cast<float>(idx.x) + nrtx::rnd(seed)) / static_cast<float>(dim.x);
    const float v = (static_cast<float>(idx.y) + nrtx::rnd(seed)) / static_cast<float>(dim.y);

    float3 ray_origin = params.camera.eye;
    float3 ray_dir =
        nrtx::normalize(params.camera.U * (2.0f * u - 1.0f) + params.camera.V * (2.0f * v - 1.0f) +
                        params.camera.W);

    if (params.camera.lens_radius > 0.0f) {
      const float3 focal_point = params.camera.eye + ray_dir * params.camera.focus_dist;
      const float2 lens = nrtx::sample_uniform_disk(seed) * params.camera.lens_radius;
      const float3 right = nrtx::normalize(params.camera.U);
      const float3 up = nrtx::normalize(params.camera.V);
      ray_origin = params.camera.eye + right * lens.x + up * lens.y;
      ray_dir = nrtx::normalize(focal_point - ray_origin);
    }

    RadiancePRD prd;
    prd.origin = ray_origin;
    prd.direction = ray_dir;
    prd.throughput = make_float3(1.0f, 1.0f, 1.0f);
    prd.radiance = make_float3(0.0f, 0.0f, 0.0f);
    prd.albedo_aov = make_float3(0.0f, 0.0f, 0.0f);
    prd.normal_aov = make_float3(0.0f, 0.0f, 0.0f);
    prd.seed = seed;
    prd.depth = 0;
    prd.done = 0;
    prd.first_hit = 1;

    for (;;) {
      trace_radiance(&prd);
      if (prd.done || prd.depth >= params.max_depth) {
        break;
      }
    }

    radiance_sum += prd.radiance;
    albedo_sum += prd.albedo_aov;
    normal_sum += prd.normal_aov;
    seed = prd.seed;
  }

  const float inv = 1.0f / static_cast<float>(params.samples_per_launch);
  float3 color = radiance_sum * inv;
  float3 albedo = albedo_sum * inv;
  float3 normal = normal_sum * inv;

  if (params.sample_index > 0) {
    const float4 prev = params.accum_buffer[pixel];
    const float n = static_cast<float>(params.sample_index);
    const float n1 = n + 1.0f;
    color = make_float3(prev.x, prev.y, prev.z) * (n / n1) + color * (1.0f / n1);
    if (params.albedo_buffer) {
      const float3 pa = params.albedo_buffer[pixel];
      albedo = pa * (n / n1) + albedo * (1.0f / n1);
    }
    if (params.normal_buffer) {
      const float3 pn = params.normal_buffer[pixel];
      normal = pn * (n / n1) + normal * (1.0f / n1);
    }
  }

  params.accum_buffer[pixel] = make_float4(color.x, color.y, color.z, 1.0f);
  if (params.albedo_buffer) {
    params.albedo_buffer[pixel] = albedo;
  }
  if (params.normal_buffer) {
    params.normal_buffer[pixel] = nrtx::normalize(normal);
  }
}

extern "C" __global__ void __miss__radiance() {
  RadiancePRD *prd = get_radiance_prd();
  prd->radiance += prd->throughput * env_color(prd->direction);
  if (prd->first_hit) {
    prd->albedo_aov = env_color(prd->direction);
    prd->normal_aov = -prd->direction;
    prd->first_hit = 0;
  }
  prd->done = 1;
}

extern "C" __global__ void __closesthit__radiance() {
  RadiancePRD *prd = get_radiance_prd();
  const nrtx::HitGroupData *hit_data =
      reinterpret_cast<nrtx::HitGroupData *>(optixGetSbtDataPointer());

  const int prim_idx = optixGetPrimitiveIndex();
  const int3 index = hit_data->indices[prim_idx];
  const float3 v0 = hit_data->vertices[index.x];
  const float3 v1 = hit_data->vertices[index.y];
  const float3 v2 = hit_data->vertices[index.z];

  const float2 bary = optixGetTriangleBarycentrics();
  const float3 p_obj = (1.0f - bary.x - bary.y) * v0 + bary.x * v1 + bary.y * v2;
  float3 n_obj = nrtx::normalize(nrtx::cross(v1 - v0, v2 - v0));

  const float3 p = optixTransformPointFromObjectToWorldSpace(p_obj);
  float3 n = nrtx::normalize(optixTransformNormalFromObjectToWorldSpace(n_obj));

  const float3 ray_dir = optixGetWorldRayDirection();
  if (nrtx::dot(n, ray_dir) > 0.0f) {
    n = -n;
  }

  const int mat_id = hit_data->material_ids[prim_idx];
  const nrtx::MaterialGPU mat = params.materials[mat_id];

  if (prd->first_hit) {
    prd->albedo_aov = mat.base_color;
    prd->normal_aov = n;
    prd->first_hit = 0;
  }

  prd->radiance += prd->throughput * mat.emission;

  // Next event estimation toward quad lights
  if (params.enable_nee && params.light_count > 0 && mat.transmission < 0.5f &&
      mat.metallic < 0.9f && nrtx::luminance(mat.emission) < 1e-6f) {
    const int light_idx = static_cast<int>(nrtx::rnd(prd->seed) * params.light_count) %
                          params.light_count;
    const nrtx::QuadLight &light = params.lights[light_idx];
    float3 lpos, lnormal;
    float pdf_area;
    const float3 Le = sample_quad_light(light, prd->seed, lpos, lnormal, pdf_area);
    float3 to_light = lpos - p;
    const float dist2 = nrtx::dot(to_light, to_light);
    const float dist = sqrtf(dist2);
    to_light = to_light / dist;
    const float cos_light = fabsf(nrtx::dot(lnormal, -to_light));
    const float cos_surf = nrtx::dot(n, to_light);
    if (cos_surf > 0.0f && cos_light > 0.0f && pdf_area > 0.0f) {
      if (!trace_shadow(p, to_light, dist)) {
        const float pdf = pdf_area * dist2 / (cos_light * params.light_count);
        const float3 brdf = mat.base_color * (1.0f - mat.metallic) * (1.0f / 3.14159265f);
        prd->radiance += prd->throughput * brdf * Le * (cos_surf / pdf);
      }
    }
  }

  // Sample BSDF: mix diffuse / metal specular / glass
  float3 wo = -ray_dir;
  float3 wi;
  float3 f = make_float3(0.0f, 0.0f, 0.0f);
  float pdf = 0.0f;

  const float r_mat = nrtx::rnd(prd->seed);
  if (mat.transmission > 0.5f) {
    const float entering = nrtx::dot(ray_dir, n) < 0.0f ? 1.0f : -1.0f;
    const float3 outward_n = entering > 0.0f ? n : -n;
    const float eta = entering > 0.0f ? (1.0f / mat.ior) : mat.ior;
    const float cos_theta = fminf(1.0f, fabsf(nrtx::dot(wo, outward_n)));
    const float f0 = powf((1.0f - mat.ior) / (1.0f + mat.ior), 2.0f);
    const float reflect_prob = fresnel_schlick(cos_theta, f0);
    float3 refracted;
    if (nrtx::rnd(prd->seed) < reflect_prob || !refract(ray_dir, outward_n, eta, refracted)) {
      wi = nrtx::reflect(ray_dir, outward_n);
    } else {
      wi = nrtx::normalize(refracted);
    }
    f = make_float3(1.0f, 1.0f, 1.0f);
    pdf = 1.0f;
  } else if (r_mat < mat.metallic) {
    const float3 reflected = nrtx::reflect(ray_dir, n);
    const float roughness = fmaxf(mat.roughness, 0.001f);
    wi = nrtx::normalize(reflected + roughness * nrtx::cosine_sample_hemisphere(prd->seed, n));
    if (nrtx::dot(wi, n) <= 0.0f) {
      prd->done = 1;
      return;
    }
    f = mat.base_color;
    pdf = 1.0f;
  } else {
    wi = nrtx::cosine_sample_hemisphere(prd->seed, n);
    const float cos_theta = nrtx::dot(wi, n);
    pdf = cos_theta / 3.14159265f;
    f = mat.base_color * (1.0f / 3.14159265f);
    if (pdf < 1e-6f) {
      prd->done = 1;
      return;
    }
  }

  prd->throughput = prd->throughput * f *
                    (mat.transmission > 0.5f || mat.metallic > 0.5f
                         ? 1.0f
                         : (nrtx::dot(wi, n) / pdf));

  // Russian roulette
  if (prd->depth > 3) {
    const float q = fmaxf(0.05f, 1.0f - nrtx::luminance(prd->throughput));
    if (nrtx::rnd(prd->seed) < q) {
      prd->done = 1;
      return;
    }
    prd->throughput = prd->throughput / (1.0f - q);
  }

  prd->origin = p;
  prd->direction = wi;
  prd->depth += 1;
}

extern "C" __global__ void __anyhit__shadow() {
  ShadowPRD *prd = get_shadow_prd();
  prd->occluded = 1;
  optixTerminateRay();
}

extern "C" __global__ void __miss__shadow() {
  // leave occluded = 0
}
