#include "nrtx/heic_writer.h"

#include <libheif/heif.h>

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace nrtx {
namespace {

float clamp01(float x) { return std::min(1.0f, std::max(0.0f, x)); }

float luminance709(const float3 &c) {
  return 0.2126f * c.x + 0.7152f * c.y + 0.0722f * c.z;
}

float3 rec709_to_rec2020(const float3 &c) {
  // BT.2087 linear matrix (Rec.709 → Rec.2020).
  return make_float3(0.6274040f * c.x + 0.3292820f * c.y + 0.0433136f * c.z,
                     0.0690973f * c.x + 0.9195404f * c.y + 0.0113623f * c.z,
                     0.0163914f * c.x + 0.0880133f * c.y + 0.8955952f * c.z);
}

float pq_oetf(float L_nits) {
  // SMPTE ST 2084; L in cd/m^2, output in [0,1].
  const float m1 = 2610.0f / 16384.0f;
  const float m2 = 2523.0f / 4096.0f * 128.0f;
  const float c1 = 3424.0f / 4096.0f;
  const float c2 = 2413.0f / 4096.0f * 32.0f;
  const float c3 = 2392.0f / 4096.0f * 32.0f;
  const float Y = std::max(L_nits, 0.0f) / 10000.0f;
  const float Ym = std::pow(Y, m1);
  return std::pow((c1 + c2 * Ym) / (1.0f + c3 * Ym), m2);
}

float percentile(std::vector<float> values, float p) {
  if (values.empty()) {
    return 1.0f;
  }
  std::sort(values.begin(), values.end());
  const float t = clamp01(p) * static_cast<float>(values.size() - 1);
  const size_t i0 = static_cast<size_t>(t);
  const size_t i1 = std::min(i0 + 1, values.size() - 1);
  const float f = t - static_cast<float>(i0);
  return values[i0] * (1.0f - f) + values[i1] * f;
}

void check_heif(heif_error err, const char *what) {
  if (err.code != heif_error_Ok) {
    throw std::runtime_error(std::string(what) + ": " + (err.message ? err.message : "heif error"));
  }
}

} // namespace

void write_heic_hdr(const std::string &path, int width, int height,
                    const std::vector<float3> &linear_rgb) {
  if (width <= 0 || height <= 0) {
    throw std::runtime_error("write_heic_hdr: invalid dimensions");
  }
  const size_t n = static_cast<size_t>(width) * static_cast<size_t>(height);
  if (linear_rgb.size() < n) {
    throw std::runtime_error("write_heic_hdr: buffer too small");
  }

  // Auto-expose: map ~99th percentile luminance to 800 nits (peak 1000).
  std::vector<float> lum;
  lum.reserve(n / 16 + 1);
  for (size_t i = 0; i < n; i += 16) {
    lum.push_back(luminance709(linear_rgb[i]));
  }
  const float p99 = std::max(percentile(lum, 0.99f), 1e-4f);
  const float scale = 800.0f / p99;
  constexpr float kPeakNits = 1000.0f;

  heif_image *image = nullptr;
  check_heif(heif_image_create(width, height, heif_colorspace_RGB, heif_chroma_interleaved_RRGGBB_LE,
                               &image),
             "heif_image_create");

  check_heif(heif_image_add_plane(image, heif_channel_interleaved, width, height, 10),
             "heif_image_add_plane");

  int stride = 0;
  uint8_t *plane = heif_image_get_plane(image, heif_channel_interleaved, &stride);
  if (!plane || stride <= 0) {
    heif_image_release(image);
    throw std::runtime_error("heif_image_get_plane failed");
  }

  for (int y = 0; y < height; ++y) {
    auto *row = reinterpret_cast<uint16_t *>(plane + static_cast<size_t>(y) * stride);
    for (int x = 0; x < width; ++x) {
      const float3 c709 = linear_rgb[static_cast<size_t>(y) * width + x];
      float3 nits = make_float3(std::max(c709.x, 0.0f) * scale, std::max(c709.y, 0.0f) * scale,
                                std::max(c709.z, 0.0f) * scale);
      nits.x = std::min(nits.x, kPeakNits);
      nits.y = std::min(nits.y, kPeakNits);
      nits.z = std::min(nits.z, kPeakNits);
      const float3 c2020 = rec709_to_rec2020(nits);
      // PQ on each channel (common HDR stills practice).
      const float r = pq_oetf(std::max(c2020.x, 0.0f));
      const float g = pq_oetf(std::max(c2020.y, 0.0f));
      const float b = pq_oetf(std::max(c2020.z, 0.0f));
      // 10-bit codes in 16-bit little-endian interleaved RRGGBB.
      row[x * 3 + 0] = static_cast<uint16_t>(clamp01(r) * 1023.0f + 0.5f);
      row[x * 3 + 1] = static_cast<uint16_t>(clamp01(g) * 1023.0f + 0.5f);
      row[x * 3 + 2] = static_cast<uint16_t>(clamp01(b) * 1023.0f + 0.5f);
    }
  }

  heif_color_profile_nclx *nclx = heif_nclx_color_profile_alloc();
  if (!nclx) {
    heif_image_release(image);
    throw std::runtime_error("heif_nclx_color_profile_alloc failed");
  }
  nclx->color_primaries = heif_color_primaries_ITU_R_BT_2020_2_and_2100_0;
  nclx->transfer_characteristics = heif_transfer_characteristic_ITU_R_BT_2100_0_PQ;
  nclx->matrix_coefficients = heif_matrix_coefficients_ITU_R_BT_2020_2_non_constant_luminance;
  nclx->full_range_flag = true;
  check_heif(heif_image_set_nclx_color_profile(image, nclx), "heif_image_set_nclx_color_profile");
  heif_nclx_color_profile_free(nclx);

  heif_context *ctx = heif_context_alloc();
  if (!ctx) {
    heif_image_release(image);
    throw std::runtime_error("heif_context_alloc failed");
  }

  heif_encoder *encoder = nullptr;
  check_heif(heif_context_get_encoder_for_format(ctx, heif_compression_HEVC, &encoder),
             "heif_context_get_encoder_for_format(HEVC)");
  heif_encoder_set_lossy_quality(encoder, 90);
  // Prefer Main10 when the plugin exposes the option.
  heif_encoder_set_parameter(encoder, "bit-depth", "10");

  heif_encoding_options *opts = heif_encoding_options_alloc();
  opts->save_two_colr_boxes_when_ICC_and_nclx_available = false;

  heif_image_handle *handle = nullptr;
  const heif_error enc_err = heif_context_encode_image(ctx, image, encoder, opts, &handle);
  heif_encoding_options_free(opts);
  heif_encoder_release(encoder);
  heif_image_release(image);
  if (enc_err.code != heif_error_Ok) {
    heif_context_free(ctx);
    throw std::runtime_error(std::string("heif_context_encode_image: ") +
                             (enc_err.message ? enc_err.message : "encode failed"));
  }
  if (handle) {
    heif_image_handle_release(handle);
  }

  const heif_error wr = heif_context_write_to_file(ctx, path.c_str());
  heif_context_free(ctx);
  check_heif(wr, "heif_context_write_to_file");
}

} // namespace nrtx
