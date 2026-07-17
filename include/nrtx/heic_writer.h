#pragma once

#include "vec.h"

#include <string>
#include <vector>

namespace nrtx {

/** Write HDR HEIC (PQ / Rec.2020, 10-bit HEVC). `linear_rgb` is top-left origin, one float3 per pixel. */
void write_heic_hdr(const std::string &path, int width, int height,
                    const std::vector<float3> &linear_rgb);

} // namespace nrtx
