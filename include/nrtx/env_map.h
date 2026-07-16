#pragma once

#include "vec.h"

#include <string>
#include <vector>

namespace nrtx {

struct EnvMap {
  int width = 0;
  int height = 0;
  std::vector<float3> pixels;     // row-major RGB float
  std::vector<float> cdf;         // flattened row CDFs, size width*height
  std::vector<float> row_cdf;     // size height
  float total_luminance = 0.0f;

  bool empty() const { return pixels.empty() || width <= 0 || height <= 0; }

  void clear() {
    width = height = 0;
    pixels.clear();
    cdf.clear();
    row_cdf.clear();
    total_luminance = 0.0f;
  }

  void build_cdfs();
};

// Load Radiance HDR (.hdr) via stb_image float loader. Throws on failure.
EnvMap load_env_map_hdr(const std::string &path);

} // namespace nrtx
