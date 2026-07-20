// Shared descriptor bindings + env/texture helpers for Vulkan RT shaders.
#ifndef LUMENCORE_VK_BINDINGS_GLSL
#define LUMENCORE_VK_BINDINGS_GLSL

#include "common.glsl"

layout(binding = 0, set = 0) uniform accelerationStructureEXT topLevelAS;
layout(binding = 1, set = 0, rgba32f) uniform image2D accumImage;

layout(binding = 2, set = 0, scalar) readonly buffer ParamsBuf {
  LaunchParams params;
};

layout(binding = 3, set = 0, scalar) readonly buffer Vertices {
  vec3 vertices[];
};

layout(binding = 4, set = 0, scalar) readonly buffer Indices {
  uvec3 indices[];
};

layout(binding = 5, set = 0, scalar) readonly buffer Materials {
  MaterialGPU materials[];
};

layout(binding = 6, set = 0, scalar) readonly buffer MaterialIds {
  int material_ids[];
};

layout(binding = 7, set = 0, scalar) readonly buffer Lights {
  QuadLight lights[];
};

layout(binding = 8, set = 0, scalar) readonly buffer Spots {
  SpotLight spots[];
};

layout(binding = 9, set = 0, scalar) readonly buffer Texcoords {
  vec2 texcoords[];
};

layout(binding = 10, set = 0, scalar) readonly buffer Normals {
  vec3 normals[];
};

layout(binding = 11, set = 0, scalar) readonly buffer Tangents {
  vec4 tangents[];
};

layout(binding = 12, set = 0, scalar) readonly buffer EnvPixels {
  vec3 env_pixels[];
};

layout(binding = 13, set = 0, scalar) readonly buffer EnvCdf {
  float env_cdf[];
};

layout(binding = 14, set = 0, scalar) readonly buffer EnvRowCdf {
  float env_row_cdf[];
};

layout(binding = 15, set = 0, scalar) readonly buffer TexDescs {
  TextureDesc tex_descs[];
};

// Packed RGBA8 as little-endian uint: R | G<<8 | B<<16 | A<<24
layout(binding = 16, set = 0, scalar) readonly buffer TexPixels {
  uint tex_pixels[];
};

layout(binding = 17, set = 0, scalar) readonly buffer MeshRanges {
  MeshRange mesh_ranges[];
};

layout(binding = 18, set = 0, scalar) readonly buffer Volumes {
  FlameVolume volumes[];
};

// ---- Texture sampling ----
vec3 unpack_rgba8(uint p) {
  return vec3(float(p & 255u), float((p >> 8) & 255u), float((p >> 16) & 255u)) * (1.0 / 255.0);
}

vec3 sample_albedo_tex(int tex_id, vec2 uv) {
  if (tex_id < 0 || tex_id >= params.texture_count) {
    return vec3(1.0);
  }
  TextureDesc tex = tex_descs[tex_id];
  if (tex.width <= 0 || tex.height <= 0) {
    return vec3(1.0);
  }
  float u = fract(uv.x);
  float v = fract(uv.y);
  if (u < 0.0) {
    u += 1.0;
  }
  if (v < 0.0) {
    v += 1.0;
  }
  // Match OptiX: V flip for bottom-up atlas sampling.
  float x = u * float(tex.width) - 0.5;
  float y = (1.0 - v) * float(tex.height) - 0.5;
  int x0 = int(floor(x));
  int y0 = int(floor(y));
  float fx = x - float(x0);
  float fy = y - float(y0);

  // Manual wrap for fetch
  int w = tex.width;
  int h = tex.height;
  int o = tex.offset;
  // fetch helper
  int ix0 = ((x0 % w) + w) % w;
  int iy0 = ((y0 % h) + h) % h;
  int ix1 = ((x0 + 1) % w + w) % w;
  int iy1 = ((y0 + 1) % h + h) % h;
  vec3 c00 = unpack_rgba8(tex_pixels[o + iy0 * w + ix0]);
  vec3 c10 = unpack_rgba8(tex_pixels[o + iy0 * w + ix1]);
  vec3 c01 = unpack_rgba8(tex_pixels[o + iy1 * w + ix0]);
  vec3 c11 = unpack_rgba8(tex_pixels[o + iy1 * w + ix1]);
  return mix(mix(c00, c10, fx), mix(c01, c11, fx), fy);
}

// ---- HDRI ----
int cdf_upper_bound_row(int row_off, int n, float u) {
  int lo = 0;
  int hi = n - 1;
  while (lo < hi) {
    int mid = (lo + hi) >> 1;
    if (env_cdf[row_off + mid] < u) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return lo;
}

int cdf_upper_bound_1d(int n, float u) {
  int lo = 0;
  int hi = n - 1;
  while (lo < hi) {
    int mid = (lo + hi) >> 1;
    if (env_row_cdf[mid] < u) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return lo;
}

vec3 fetch_env(int ix, int iy) {
  int w = params.env_width;
  int h = params.env_height;
  ix = ((ix % w) + w) % w;
  iy = clamp(iy, 0, h - 1);
  return env_pixels[iy * w + ix];
}

vec3 sample_env_equirect(vec3 dir) {
  if (params.has_env == 0 || params.env_width <= 0 || params.env_height <= 0) {
    float t = 0.5 * (normalize(dir).y + 1.0);
    return mix(params.background_bottom, params.background_top, t);
  }
  vec3 d = normalize(dir);
  float u = atan(d.z, d.x) * (0.5 / PI) + 0.5;
  float v = acos(clamp(d.y, -1.0, 1.0)) * (1.0 / PI);
  u = fract(u);
  v = clamp(v, 0.0, 0.99999);
  float x = u * float(params.env_width) - 0.5;
  float y = v * float(params.env_height) - 0.5;
  int x0 = int(floor(x));
  int y0 = int(floor(y));
  float fx = x - float(x0);
  float fy = y - float(y0);
  vec3 c00 = fetch_env(x0, y0);
  vec3 c10 = fetch_env(x0 + 1, y0);
  vec3 c01 = fetch_env(x0, y0 + 1);
  vec3 c11 = fetch_env(x0 + 1, y0 + 1);
  return mix(mix(c00, c10, fx), mix(c01, c11, fx), fy);
}

vec3 sample_env_map(inout uint seed, out vec3 wi, out float pdf) {
  pdf = 0.0;
  wi = vec3(0.0, 1.0, 0.0);
  if (params.has_env == 0 || params.env_total_lum <= 0.0 || params.env_width <= 0 ||
      params.env_height <= 0) {
    return vec3(0.0);
  }
  float r1 = rnd(seed);
  float r2 = rnd(seed);
  int y = cdf_upper_bound_1d(params.env_height, r1);
  int x = cdf_upper_bound_row(y * params.env_width, params.env_width, r2);

  float u = (float(x) + 0.5) / float(params.env_width);
  float v = (float(y) + 0.5) / float(params.env_height);
  float phi = (u - 0.5) * 2.0 * PI;
  float theta = v * PI;
  float sin_theta = max(sin(theta), 1e-6);
  wi = vec3(sin_theta * cos(phi), cos(theta), sin_theta * sin(phi));

  vec3 Le = env_pixels[y * params.env_width + x];
  float lum = luminance(Le);
  float map_pdf = (lum * sin_theta) / max(params.env_total_lum, 1e-8);
  float solid = map_pdf * float(params.env_width * params.env_height) / (2.0 * PI * PI * sin_theta);
  pdf = max(solid, 0.0);
  return Le;
}

float pdf_env_map(vec3 dir) {
  if (params.has_env == 0 || params.env_total_lum <= 0.0 || params.env_width <= 0) {
    return 0.0;
  }
  vec3 d = normalize(dir);
  float u = atan(d.z, d.x) * (0.5 / PI) + 0.5;
  float v = acos(clamp(d.y, -1.0, 1.0)) * (1.0 / PI);
  u = fract(u);
  int x = int(u * float(params.env_width)) % params.env_width;
  int y = clamp(int(v * float(params.env_height)), 0, params.env_height - 1);
  vec3 Le = env_pixels[y * params.env_width + x];
  float lum = luminance(Le);
  float sin_theta = max(sin(v * PI), 1e-6);
  float map_pdf = (lum * sin_theta) / max(params.env_total_lum, 1e-8);
  return map_pdf * float(params.env_width * params.env_height) / (2.0 * PI * PI * sin_theta);
}

#endif // LUMENCORE_VK_BINDINGS_GLSL
