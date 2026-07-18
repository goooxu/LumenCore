#include "nrtx/env_map.h"

#include <cmath>
#include <stdexcept>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

namespace nrtx {

void EnvMap::build_cdfs() {
  cdf.assign(static_cast<size_t>(width) * height, 0.0f);
  row_cdf.assign(height, 0.0f);
  total_luminance = 0.0f;

  for (int y = 0; y < height; ++y) {
    float row_sum = 0.0f;
    for (int x = 0; x < width; ++x) {
      const float3 &c = pixels[static_cast<size_t>(y) * width + x];
      // Solid-angle weight ~ sin(theta); v=0 is +Y top of equirect.
      const float v = (static_cast<float>(y) + 0.5f) / static_cast<float>(height);
      const float theta = v * 3.14159265f;
      const float sin_theta = fmaxf(sinf(theta), 0.0f);
      const float lum = (0.2126f * c.x + 0.7152f * c.y + 0.0722f * c.z) * sin_theta;
      row_sum += fmaxf(lum, 0.0f);
      cdf[static_cast<size_t>(y) * width + x] = row_sum;
    }
    row_cdf[y] = (y == 0 ? 0.0f : row_cdf[y - 1]) + row_sum;
    // Normalize row CDF
    if (row_sum > 0.0f) {
      for (int x = 0; x < width; ++x) {
        cdf[static_cast<size_t>(y) * width + x] /= row_sum;
      }
    }
  }
  total_luminance = row_cdf.empty() ? 0.0f : row_cdf.back();
  if (total_luminance > 0.0f) {
    for (int y = 0; y < height; ++y) {
      row_cdf[y] /= total_luminance;
    }
  }
}

EnvMap load_env_map_hdr(const std::string &path) {
  int w = 0, h = 0, comp = 0;
  float *data = stbi_loadf(path.c_str(), &w, &h, &comp, 3);
  if (!data || w <= 0 || h <= 0) {
    throw std::runtime_error("Failed to load HDR env map: " + path);
  }
  EnvMap env;
  env.width = w;
  env.height = h;
  env.pixels.resize(static_cast<size_t>(w) * h);
  for (int i = 0; i < w * h; ++i) {
    env.pixels[i] = make_float3(data[i * 3 + 0], data[i * 3 + 1], data[i * 3 + 2]);
  }
  stbi_image_free(data);
  env.build_cdfs();
  return env;
}

} // namespace nrtx
