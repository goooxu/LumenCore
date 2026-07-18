#pragma once

#include <string>
#include <vector>

namespace nrtx {

/** Load an AVIF file as 8-bit RGBA (textures / LDR assets). */
void load_avif_rgba8(const std::string &path, int &width, int &height,
                     std::vector<unsigned char> &rgba);

/**
 * Write HDR AVIF (10-bit PQ / BT.2020) from linear scene-referred RGB float rows.
 * `rgb` is tightly packed RGB (no alpha), row-major, top-left origin, size width*height*3.
 * `nits_scale` maps linear 1.0 → that many nits before PQ encoding (default 100).
 */
void write_avif_hdr_pq(const std::string &path, int width, int height, const float *rgb,
                       float nits_scale = 100.0f);

} // namespace nrtx
