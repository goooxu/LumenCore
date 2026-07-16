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

__forceinline__ __device__ float3 sample_albedo_tex(const nrtx::TextureGPU &tex, float2 uv) {
  if (!tex.pixels || tex.width <= 0 || tex.height <= 0) {
    return make_float3(1.0f, 1.0f, 1.0f);
  }
  // Wrap
  float u = uv.x - floorf(uv.x);
  float v = uv.y - floorf(uv.y);
  if (u < 0.0f) {
    u += 1.0f;
  }
  if (v < 0.0f) {
    v += 1.0f;
  }
  // OBJ/PNG often use top-left V; our atlas is authored bottom-up friendly — sample as-is.
  const float x = u * static_cast<float>(tex.width) - 0.5f;
  const float y = (1.0f - v) * static_cast<float>(tex.height) - 0.5f;
  const int x0 = static_cast<int>(floorf(x));
  const int y0 = static_cast<int>(floorf(y));
  const float fx = x - static_cast<float>(x0);
  const float fy = y - static_cast<float>(y0);

  auto fetch = [&](int ix, int iy) -> float3 {
    ix = (ix % tex.width + tex.width) % tex.width;
    iy = (iy % tex.height + tex.height) % tex.height;
    const uchar4 p = tex.pixels[iy * tex.width + ix];
    return make_float3(p.x, p.y, p.z) * (1.0f / 255.0f);
  };

  const float3 c00 = fetch(x0, y0);
  const float3 c10 = fetch(x0 + 1, y0);
  const float3 c01 = fetch(x0, y0 + 1);
  const float3 c11 = fetch(x0 + 1, y0 + 1);
  const float3 c0 = nrtx::lerp(c00, c10, fx);
  const float3 c1 = nrtx::lerp(c01, c11, fx);
  return nrtx::lerp(c0, c1, fy);
}

__forceinline__ __device__ float3 shaded_base_color(const nrtx::MaterialGPU &mat,
                                                   const nrtx::HitGroupData *hit_data,
                                                   const int3 &index, const float2 &bary) {
  float3 color = mat.base_color;
  if (mat.albedo_tex >= 0 && mat.albedo_tex < params.texture_count && hit_data->texcoords) {
    const float2 uv0 = hit_data->texcoords[index.x];
    const float2 uv1 = hit_data->texcoords[index.y];
    const float2 uv2 = hit_data->texcoords[index.z];
    const float2 uv = (1.0f - bary.x - bary.y) * uv0 + bary.x * uv1 + bary.y * uv2;
    color = color * sample_albedo_tex(params.textures[mat.albedo_tex], uv);
  }
  return color;
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

__forceinline__ __device__ float fractf(float x) { return x - floorf(x); }

__forceinline__ __device__ float hash31(float3 p) {
  p = make_float3(fractf(p.x * 0.1031f), fractf(p.y * 0.1031f), fractf(p.z * 0.1031f));
  const float d = nrtx::dot(p, make_float3(p.y + 33.33f, p.z + 33.33f, p.x + 33.33f));
  p = p + make_float3(d, d, d);
  return fractf((p.x + p.y) * p.z);
}

__forceinline__ __device__ float value_noise(float3 p) {
  const float3 i = make_float3(floorf(p.x), floorf(p.y), floorf(p.z));
  const float3 f = make_float3(p.x - i.x, p.y - i.y, p.z - i.z);
  const float3 u = f * f * (make_float3(3.0f, 3.0f, 3.0f) - 2.0f * f);

  const float n000 = hash31(i + make_float3(0, 0, 0));
  const float n100 = hash31(i + make_float3(1, 0, 0));
  const float n010 = hash31(i + make_float3(0, 1, 0));
  const float n110 = hash31(i + make_float3(1, 1, 0));
  const float n001 = hash31(i + make_float3(0, 0, 1));
  const float n101 = hash31(i + make_float3(1, 0, 1));
  const float n011 = hash31(i + make_float3(0, 1, 1));
  const float n111 = hash31(i + make_float3(1, 1, 1));

  const float nx00 = n000 * (1.0f - u.x) + n100 * u.x;
  const float nx10 = n010 * (1.0f - u.x) + n110 * u.x;
  const float nx01 = n001 * (1.0f - u.x) + n101 * u.x;
  const float nx11 = n011 * (1.0f - u.x) + n111 * u.x;
  const float nxy0 = nx00 * (1.0f - u.y) + nx10 * u.y;
  const float nxy1 = nx01 * (1.0f - u.y) + nx11 * u.y;
  return nxy0 * (1.0f - u.z) + nxy1 * u.z;
}

__forceinline__ __device__ float fbm(float3 p) {
  float sum = 0.0f;
  float amp = 0.5f;
  float freq = 1.0f;
  for (int i = 0; i < 4; ++i) {
    sum += amp * value_noise(p * freq);
    freq *= 2.02f;
    amp *= 0.5f;
  }
  return sum;
}

// Ray vs AABB slab. Returns true if segment [tmin,tmax] overlaps the box.
__forceinline__ __device__ bool intersect_aabb(const float3 &ro, const float3 &rd, const float3 &bmin,
                                              const float3 &bmax, float &t_near, float &t_far) {
  float t0 = -1e30f;
  float t1 = 1e30f;
  const float3 inv = make_float3(1.0f / (fabsf(rd.x) > 1e-8f ? rd.x : copysignf(1e-8f, rd.x)),
                                 1.0f / (fabsf(rd.y) > 1e-8f ? rd.y : copysignf(1e-8f, rd.y)),
                                 1.0f / (fabsf(rd.z) > 1e-8f ? rd.z : copysignf(1e-8f, rd.z)));
  const float3 t_a = (bmin - ro) * inv;
  const float3 t_b = (bmax - ro) * inv;
  const float3 t_small = make_float3(fminf(t_a.x, t_b.x), fminf(t_a.y, t_b.y), fminf(t_a.z, t_b.z));
  const float3 t_big = make_float3(fmaxf(t_a.x, t_b.x), fmaxf(t_a.y, t_b.y), fmaxf(t_a.z, t_b.z));
  t0 = fmaxf(t0, fmaxf(t_small.x, fmaxf(t_small.y, t_small.z)));
  t1 = fminf(t1, fminf(t_big.x, fminf(t_big.y, t_big.z)));
  if (t1 < t0 || t1 < 0.0f) {
    return false;
  }
  t_near = fmaxf(t0, 0.0f);
  t_far = t1;
  return t_far > t_near;
}

__forceinline__ __device__ float smoothstep(float edge0, float edge1, float x) {
  const float t = nrtx::clamp((x - edge0) / (edge1 - edge0), 0.0f, 1.0f);
  return t * t * (3.0f - 2.0f * t);
}

__forceinline__ __device__ float3 flame_emission_color(float height01, float density) {
  // Blackbody-ish palette from local temperature (0 cool tip → 1 hot core).
  const float core_boost = (1.0f - height01) * (1.0f - height01);
  const float temp =
      nrtx::clamp(density * (1.25f - 0.95f * height01) + 0.35f * core_boost, 0.0f, 1.0f);
  const float3 c_cool = make_float3(0.95f, 0.12f, 0.02f);
  const float3 c_mid = make_float3(1.0f, 0.45f, 0.05f);
  const float3 c_hot = make_float3(1.15f, 0.95f, 0.55f);
  float3 c = nrtx::lerp(c_cool, c_mid, smoothstep(0.15f, 0.55f, temp));
  c = nrtx::lerp(c, c_hot, smoothstep(0.45f, 0.95f, temp));
  return c;
}

__forceinline__ __device__ float flame_density(const nrtx::FlameVolume &vol, const float3 &p) {
  // Local coords: y in [-1,1] bottom → tip.
  float3 q = make_float3((p.x - vol.center.x) / vol.half_extents.x,
                         (p.y - vol.center.y) / vol.half_extents.y,
                         (p.z - vol.center.z) / vol.half_extents.z);
  if (q.y < -1.12f || q.y > 1.15f) {
    return 0.0f;
  }

  const float t = vol.time;
  const float y01 = nrtx::clamp(0.5f * (q.y + 1.0f), 0.0f, 1.0f);

  // Mild domain warp only (keep filaments readable).
  float3 sp0 = make_float3(q.x * 1.6f, (q.y - t * 0.35f) * 1.2f, q.z * 1.6f);
  q.x += (value_noise(sp0) - 0.5f) * 0.18f * (0.2f + y01);
  q.z += (value_noise(sp0 + make_float3(3.1f, 1.7f, -2.4f)) - 0.5f) * 0.18f * (0.2f + y01);

  // Rising anisotropic sample space: denser horizontally, stretched vertically.
  const float ns = vol.noise_scale;
  float3 sp = make_float3(q.x * ns * 1.85f, (q.y - t * 2.15f) * ns * 0.85f, q.z * ns * 1.85f);

  // 5 sparse filaments with independent swaying centers.
  float filament = 0.0f;
  for (int i = 0; i < 5; ++i) {
    const float fi = static_cast<float>(i);
    const float phase = t * (1.55f + 0.33f * fi) + fi * 1.7f;
    const float sway = 0.12f + 0.55f * y01;
    float ox = sway * sinf(phase) * (0.55f + 0.12f * fi);
    float oz = sway * cosf(phase * 0.87f + 0.9f) * (0.5f + 0.1f * fi);
    // Extra curl so tongues lean/fold instead of perfect vertical streaks
    ox += 0.22f * (fbm(make_float3(q.y * 2.5f + fi, t * 0.6f, fi * 1.3f)) - 0.5f) * y01;
    oz += 0.22f * (fbm(make_float3(fi * 2.1f, q.y * 2.2f - t * 0.7f, 4.0f)) - 0.5f) * y01;
    const float lx = q.x - ox;
    const float lz = q.z - oz;
    // Tube width: wider near fuel bed, hair-thin at tip.
    float width = (0.22f - 0.025f * fi) * (1.0f - y01) + 0.035f * y01;
    width *= 0.85f + 0.3f * value_noise(make_float3(phase, y01 * 2.0f, fi));
    const float r2 = lx * lx + lz * lz;
    const float tube = expf(-r2 / fmaxf(width * width, 1e-5f));
    filament = fmaxf(filament, tube * (1.0f - 0.08f * fi));
  }

  // High-contrast carving along the rising column (most voxels empty).
  float n = fbm(sp);
  const float thresh = 0.38f + 0.42f * y01;
  const float contrast = 4.5f + 3.0f * y01;
  float carve = nrtx::clamp((n - thresh) * contrast, 0.0f, 1.0f);
  carve = powf(carve, 1.15f);

  const float base = smoothstep(-1.1f, -0.65f, q.y);
  const float tip = 1.0f - smoothstep(0.55f, 1.05f, y01 + 0.25f * (n - 0.5f));
  const float height_env = base * tip;

  float bed = 0.0f;
  if (y01 < 0.35f) {
    const float br = sqrtf(q.x * q.x + q.z * q.z);
    bed = expf(-br * br / 0.12f) * (1.0f - y01 / 0.35f) * carve * 0.55f;
  }

  float dens = filament * carve * height_env;
  dens = fmaxf(dens, bed);
  const float holes = fbm(sp * 1.8f + make_float3(2.2f, t, -1.4f));
  dens *= 1.0f - 0.65f * y01 * smoothstep(0.5f, 0.82f, holes);

  return fmaxf(dens * vol.density_scale, 0.0f);
}

__forceinline__ __device__ void integrate_flame_volume(RadiancePRD *prd, const nrtx::FlameVolume &vol,
                                                      const float3 &ro, const float3 &rd, float t_enter) {
  const float3 bmin = vol.center - vol.half_extents;
  const float3 bmax = vol.center + vol.half_extents;
  float t_near = 0.0f;
  float t_far = 0.0f;
  if (!intersect_aabb(ro, rd, bmin, bmax, t_near, t_far)) {
    // Should not happen on a proxy hit; skip past the surface.
    prd->origin = ro + rd * (t_enter + 1e-3f);
    prd->depth += 1;
    return;
  }
  t_near = fmaxf(t_near, t_enter);
  if (t_far <= t_near) {
    prd->origin = ro + rd * (t_enter + 1e-3f);
    prd->depth += 1;
    return;
  }

  constexpr int kSteps = 64;
  const float span = t_far - t_near;
  const float jitter = nrtx::rnd(prd->seed);
  const float dt = span / static_cast<float>(kSteps);

  float3 Le = make_float3(0.0f, 0.0f, 0.0f);
  float Tr = 1.0f;

  for (int i = 0; i < kSteps; ++i) {
    const float t = t_near + (static_cast<float>(i) + jitter) * dt;
    if (t >= t_far) {
      break;
    }
    const float3 p = ro + rd * t;
    const float dens = flame_density(vol, p);
    if (dens <= 1e-5f) {
      continue;
    }
    const float sigma_t = dens * vol.absorption;
    const float height01 =
        nrtx::clamp((p.y - (vol.center.y - vol.half_extents.y)) / fmaxf(2.0f * vol.half_extents.y, 1e-3f), 0.0f,
                    1.0f);
    // dens^2: bright filament cores, transparent edges
    const float3 emit = flame_emission_color(height01, dens) * vol.emission_scale * (dens * dens);
    Le += make_float3(Tr, Tr, Tr) * emit * dt;
    Tr *= expf(-sigma_t * dt);
    if (Tr < 1e-3f) {
      Tr = 0.0f;
      break;
    }
  }

  prd->radiance += prd->throughput * Le;
  prd->throughput = prd->throughput * Tr;

  // Continue just past the far face so we do not re-hit the proxy box.
  prd->origin = ro + rd * (t_far + 1e-3f);
  prd->direction = rd;
  prd->depth += 1;

  if (nrtx::luminance(prd->throughput) < 1e-4f) {
    prd->done = 1;
  }
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
  const float3 ray_origin = optixGetWorldRayOrigin();
  if (nrtx::dot(n, ray_dir) > 0.0f) {
    n = -n;
  }

  const int mat_id = hit_data->material_ids[prim_idx];
  const nrtx::MaterialGPU mat = params.materials[mat_id];
  const float3 base = shaded_base_color(mat, hit_data, index, bary);

  // Procedural flame volume: ray-march through the AABB proxy.
  if ((mat.flags & nrtx::MATERIAL_FLAG_VOLUME_FLAME) && mat.volume_index >= 0 &&
      mat.volume_index < params.volume_count) {
    if (prd->first_hit) {
      prd->albedo_aov = make_float3(1.0f, 0.45f, 0.08f);
      prd->normal_aov = n;
      prd->first_hit = 0;
    }
    const float t_hit = optixGetRayTmax();
    integrate_flame_volume(prd, params.volumes[mat.volume_index], ray_origin, ray_dir, t_hit);
    return;
  }

  if (prd->first_hit) {
    prd->albedo_aov = base;
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
        const float3 brdf = base * (1.0f - mat.metallic) * (1.0f / 3.14159265f);
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
    f = base;
    pdf = 1.0f;
  } else {
    wi = nrtx::cosine_sample_hemisphere(prd->seed, n);
    const float cos_theta = nrtx::dot(wi, n);
    pdf = cos_theta / 3.14159265f;
    f = base * (1.0f / 3.14159265f);
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
  const nrtx::HitGroupData *hit_data =
      reinterpret_cast<nrtx::HitGroupData *>(optixGetSbtDataPointer());
  const int prim_idx = optixGetPrimitiveIndex();
  const int mat_id = hit_data->material_ids[prim_idx];
  if (mat_id >= 0 && mat_id < params.material_count) {
    const nrtx::MaterialGPU mat = params.materials[mat_id];
    // Flame proxy boxes are transparent to shadow rays (illumination uses NEE proxy lights).
    if (mat.flags & nrtx::MATERIAL_FLAG_VOLUME_FLAME) {
      optixIgnoreIntersection();
      return;
    }
  }
  prd->occluded = 1;
  optixTerminateRay();
}

extern "C" __global__ void __miss__shadow() {
  // leave occluded = 0
}
