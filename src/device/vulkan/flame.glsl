// Procedural flame volume — algorithm aligned with src/device/shaders.cu
#ifndef LUMENCORE_VK_FLAME_GLSL
#define LUMENCORE_VK_FLAME_GLSL

#ifndef LUMENCORE_VK_COMMON_GLSL
#include "common.glsl"
#endif

float hash31(vec3 p) {
  p = fract(p * 0.1031);
  float d = dot(p, vec3(p.y + 33.33, p.z + 33.33, p.x + 33.33));
  p += d;
  return fract((p.x + p.y) * p.z);
}

float value_noise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  vec3 u = f * f * (3.0 - 2.0 * f);
  float n000 = hash31(i + vec3(0, 0, 0));
  float n100 = hash31(i + vec3(1, 0, 0));
  float n010 = hash31(i + vec3(0, 1, 0));
  float n110 = hash31(i + vec3(1, 1, 0));
  float n001 = hash31(i + vec3(0, 0, 1));
  float n101 = hash31(i + vec3(1, 0, 1));
  float n011 = hash31(i + vec3(0, 1, 1));
  float n111 = hash31(i + vec3(1, 1, 1));
  float nx00 = mix(n000, n100, u.x);
  float nx10 = mix(n010, n110, u.x);
  float nx01 = mix(n001, n101, u.x);
  float nx11 = mix(n011, n111, u.x);
  float nxy0 = mix(nx00, nx10, u.y);
  float nxy1 = mix(nx01, nx11, u.y);
  return mix(nxy0, nxy1, u.z);
}

float fbm(vec3 p) {
  float sum = 0.0;
  float amp = 0.5;
  float freq = 1.0;
  for (int i = 0; i < 4; ++i) {
    sum += amp * value_noise(p * freq);
    freq *= 2.02;
    amp *= 0.5;
  }
  return sum;
}

float smoothstep01(float edge0, float edge1, float x) {
  float t = clamp((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

bool intersect_aabb(vec3 ro, vec3 rd, vec3 bmin, vec3 bmax, out float t_near, out float t_far) {
  float t0 = -1e30;
  float t1 = 1e30;
  vec3 inv = 1.0 / max(abs(rd), vec3(1e-8)) * sign(rd + vec3(1e-20));
  // safer inv
  inv = vec3(1.0 / (abs(rd.x) > 1e-8 ? rd.x : (rd.x >= 0.0 ? 1e-8 : -1e-8)),
             1.0 / (abs(rd.y) > 1e-8 ? rd.y : (rd.y >= 0.0 ? 1e-8 : -1e-8)),
             1.0 / (abs(rd.z) > 1e-8 ? rd.z : (rd.z >= 0.0 ? 1e-8 : -1e-8)));
  vec3 t_a = (bmin - ro) * inv;
  vec3 t_b = (bmax - ro) * inv;
  vec3 t_small = min(t_a, t_b);
  vec3 t_big = max(t_a, t_b);
  t0 = max(t0, max(t_small.x, max(t_small.y, t_small.z)));
  t1 = min(t1, min(t_big.x, min(t_big.y, t_big.z)));
  if (t1 < t0 || t1 < 0.0) {
    return false;
  }
  t_near = max(t0, 0.0);
  t_far = t1;
  return t_far > t_near;
}

vec3 flame_emission_color(float height01, float density) {
  float core_boost = (1.0 - height01) * (1.0 - height01);
  float temp = clamp(density * (1.25 - 0.95 * height01) + 0.35 * core_boost, 0.0, 1.0);
  vec3 c_cool = vec3(0.95, 0.12, 0.02);
  vec3 c_mid = vec3(1.0, 0.45, 0.05);
  vec3 c_hot = vec3(1.15, 0.95, 0.55);
  vec3 c = mix(c_cool, c_mid, smoothstep01(0.15, 0.55, temp));
  c = mix(c, c_hot, smoothstep01(0.45, 0.95, temp));
  return c;
}

float flame_density(FlameVolume vol, vec3 p) {
  vec3 q = vec3((p.x - vol.center.x) / vol.half_extents.x,
                (p.y - vol.center.y) / vol.half_extents.y,
                (p.z - vol.center.z) / vol.half_extents.z);
  if (q.y < -1.12 || q.y > 1.15) {
    return 0.0;
  }
  float t = vol.time;
  float y01 = clamp(0.5 * (q.y + 1.0), 0.0, 1.0);

  vec3 sp0 = vec3(q.x * 1.6, (q.y - t * 0.35) * 1.2, q.z * 1.6);
  q.x += (value_noise(sp0) - 0.5) * 0.18 * (0.2 + y01);
  q.z += (value_noise(sp0 + vec3(3.1, 1.7, -2.4)) - 0.5) * 0.18 * (0.2 + y01);

  float ns = vol.noise_scale;
  vec3 sp = vec3(q.x * ns * 1.85, (q.y - t * 2.15) * ns * 0.85, q.z * ns * 1.85);

  float filament = 0.0;
  for (int i = 0; i < 5; ++i) {
    float fi = float(i);
    float phase = t * (1.55 + 0.33 * fi) + fi * 1.7;
    float sway = 0.12 + 0.55 * y01;
    float ox = sway * sin(phase) * (0.55 + 0.12 * fi);
    float oz = sway * cos(phase * 0.87 + 0.9) * (0.5 + 0.1 * fi);
    ox += 0.22 * (fbm(vec3(q.y * 2.5 + fi, t * 0.6, fi * 1.3)) - 0.5) * y01;
    oz += 0.22 * (fbm(vec3(fi * 2.1, q.y * 2.2 - t * 0.7, 4.0)) - 0.5) * y01;
    float lx = q.x - ox;
    float lz = q.z - oz;
    float width = (0.22 - 0.025 * fi) * (1.0 - y01) + 0.035 * y01;
    width *= 0.85 + 0.3 * value_noise(vec3(phase, y01 * 2.0, fi));
    float r2 = lx * lx + lz * lz;
    float tube = exp(-r2 / max(width * width, 1e-5));
    filament = max(filament, tube * (1.0 - 0.08 * fi));
  }

  float n = fbm(sp);
  float thresh = 0.38 + 0.42 * y01;
  float contrast = 4.5 + 3.0 * y01;
  float carve = clamp((n - thresh) * contrast, 0.0, 1.0);
  carve = pow(carve, 1.15);

  float base = smoothstep01(-1.1, -0.65, q.y);
  float tip = 1.0 - smoothstep01(0.55, 1.05, y01 + 0.25 * (n - 0.5));
  float height_env = base * tip;

  float bed = 0.0;
  if (y01 < 0.35) {
    float br = sqrt(q.x * q.x + q.z * q.z);
    bed = exp(-br * br / 0.12) * (1.0 - y01 / 0.35) * carve * 0.55;
  }

  float dens = filament * carve * height_env;
  dens = max(dens, bed);
  float holes = fbm(sp * 1.8 + vec3(2.2, t, -1.4));
  dens *= 1.0 - 0.65 * y01 * smoothstep01(0.5, 0.82, holes);
  return max(dens * vol.density_scale, 0.0);
}

// Integrate flame; returns Le and updates Tr, origin past volume.
void integrate_flame_volume(FlameVolume vol, vec3 ro, vec3 rd, float t_enter, inout uint seed,
                            out vec3 Le, out float Tr, out vec3 out_origin) {
  Le = vec3(0.0);
  Tr = 1.0;
  vec3 bmin = vol.center - vol.half_extents;
  vec3 bmax = vol.center + vol.half_extents;
  float t_near = 0.0;
  float t_far = 0.0;
  if (!intersect_aabb(ro, rd, bmin, bmax, t_near, t_far)) {
    out_origin = ro + rd * (t_enter + 1e-3);
    return;
  }
  t_near = max(t_near, t_enter);
  if (t_far <= t_near) {
    out_origin = ro + rd * (t_enter + 1e-3);
    return;
  }

  const int kSteps = 64;
  float span = t_far - t_near;
  float jitter = rnd(seed);
  float dt = span / float(kSteps);

  for (int i = 0; i < kSteps; ++i) {
    float t = t_near + (float(i) + jitter) * dt;
    if (t >= t_far) {
      break;
    }
    vec3 p = ro + rd * t;
    float dens = flame_density(vol, p);
    if (dens <= 1e-5) {
      continue;
    }
    float sigma_t = dens * vol.absorption;
    float height01 = clamp((p.y - (vol.center.y - vol.half_extents.y)) /
                               max(2.0 * vol.half_extents.y, 1e-3),
                           0.0, 1.0);
    vec3 emit = flame_emission_color(height01, dens) * vol.emission_scale * (dens * dens);
    Le += vec3(Tr) * emit * dt;
    Tr *= exp(-sigma_t * dt);
    if (Tr < 1e-3) {
      Tr = 0.0;
      break;
    }
  }
  out_origin = ro + rd * (t_far + 1e-3);
}

#endif // LUMENCORE_VK_FLAME_GLSL
