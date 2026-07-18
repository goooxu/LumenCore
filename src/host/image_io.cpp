#include "nrtx/image_io.h"

#include <avif/avif.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace nrtx {
namespace {

float linear_to_pq(float y) {
  // SMPTE ST 2084 (PQ); input is relative to 10000 nits display peak.
  y = std::clamp(y, 0.0f, 1.0f);
  constexpr float m1 = 2610.0f / 16384.0f;
  constexpr float m2 = 2523.0f / 32.0f;
  constexpr float c1 = 3424.0f / 4096.0f;
  constexpr float c2 = 2413.0f / 128.0f;
  constexpr float c3 = 2392.0f / 128.0f;
  const float ym = std::pow(y, m1);
  return std::pow((c1 + c2 * ym) / (1.0f + c3 * ym), m2);
}

void rgb_to_bt2020_yuv(float r, float g, float b, float &y, float &u, float &v) {
  y = 0.2627f * r + 0.6780f * g + 0.0593f * b;
  u = (b - y) / 1.8814f;
  v = (r - y) / 1.4746f;
}

uint16_t to_10bit(float x) {
  const float v = std::clamp(x, 0.0f, 1.0f) * 1023.0f + 0.5f;
  return static_cast<uint16_t>(std::clamp(v, 0.0f, 1023.0f));
}

uint16_t chroma_to_10bit(float c) {
  return to_10bit(c * 0.5f + 0.5f);
}

[[noreturn]] void throw_avif(const std::string &what, avifResult res) {
  throw std::runtime_error(what + ": " + avifResultToString(res));
}

void write_file(const std::string &path, const uint8_t *data, size_t size) {
  FILE *f = std::fopen(path.c_str(), "wb");
  if (!f) {
    throw std::runtime_error("Failed to open for write: " + path);
  }
  const size_t written = std::fwrite(data, 1, size, f);
  std::fclose(f);
  if (written != size) {
    throw std::runtime_error("Failed to write AVIF: " + path);
  }
}

} // namespace

void load_avif_rgba8(const std::string &path, int &width, int &height,
                     std::vector<unsigned char> &rgba) {
  avifDecoder *decoder = avifDecoderCreate();
  if (!decoder) {
    throw std::runtime_error("avifDecoderCreate failed");
  }
  avifResult res = avifDecoderSetIOFile(decoder, path.c_str());
  if (res != AVIF_RESULT_OK) {
    avifDecoderDestroy(decoder);
    throw_avif("Failed to open AVIF " + path, res);
  }
  res = avifDecoderParse(decoder);
  if (res != AVIF_RESULT_OK) {
    avifDecoderDestroy(decoder);
    throw_avif("Failed to parse AVIF " + path, res);
  }
  res = avifDecoderNextImage(decoder);
  if (res != AVIF_RESULT_OK) {
    avifDecoderDestroy(decoder);
    throw_avif("Failed to decode AVIF " + path, res);
  }

  avifRGBImage rgb;
  avifRGBImageSetDefaults(&rgb, decoder->image);
  rgb.format = AVIF_RGB_FORMAT_RGBA;
  rgb.depth = 8;
  res = avifRGBImageAllocatePixels(&rgb);
  if (res != AVIF_RESULT_OK) {
    avifDecoderDestroy(decoder);
    throw_avif("avifRGBImageAllocatePixels", res);
  }
  res = avifImageYUVToRGB(decoder->image, &rgb);
  if (res != AVIF_RESULT_OK) {
    avifRGBImageFreePixels(&rgb);
    avifDecoderDestroy(decoder);
    throw_avif("avifImageYUVToRGB", res);
  }

  width = static_cast<int>(rgb.width);
  height = static_cast<int>(rgb.height);
  const size_t n = static_cast<size_t>(width) * static_cast<size_t>(height) * 4;
  rgba.resize(n);
  if (rgb.rowBytes == static_cast<uint32_t>(width * 4)) {
    std::memcpy(rgba.data(), rgb.pixels, n);
  } else {
    for (int y = 0; y < height; ++y) {
      std::memcpy(rgba.data() + static_cast<size_t>(y) * width * 4,
                  rgb.pixels + static_cast<size_t>(y) * rgb.rowBytes,
                  static_cast<size_t>(width) * 4);
    }
  }

  avifRGBImageFreePixels(&rgb);
  avifDecoderDestroy(decoder);
}

void write_avif_hdr_pq(const std::string &path, int width, int height, const float *rgb,
                       float nits_scale) {
  if (width <= 0 || height <= 0 || !rgb) {
    throw std::runtime_error("write_avif_hdr_pq: invalid image");
  }

  avifImage *image = avifImageCreate(static_cast<uint32_t>(width), static_cast<uint32_t>(height),
                                     10, AVIF_PIXEL_FORMAT_YUV444);
  if (!image) {
    throw std::runtime_error("avifImageCreate failed");
  }
  image->colorPrimaries = AVIF_COLOR_PRIMARIES_BT2020;
  image->transferCharacteristics = AVIF_TRANSFER_CHARACTERISTICS_SMPTE2084;
  image->matrixCoefficients = AVIF_MATRIX_COEFFICIENTS_BT2020_NCL;
  image->yuvRange = AVIF_RANGE_FULL;

  if (avifImageAllocatePlanes(image, AVIF_PLANES_YUV) != AVIF_RESULT_OK) {
    avifImageDestroy(image);
    throw std::runtime_error("avifImageAllocatePlanes failed");
  }

  constexpr float kPqPeakNits = 10000.0f;
  constexpr float kMaxNits = 1000.0f;
  const float scale = nits_scale / kPqPeakNits;
  const float max_rel = kMaxNits / kPqPeakNits;

  for (int y = 0; y < height; ++y) {
    auto *yp = reinterpret_cast<uint16_t *>(image->yuvPlanes[AVIF_CHAN_Y] +
                                            y * image->yuvRowBytes[AVIF_CHAN_Y]);
    auto *up = reinterpret_cast<uint16_t *>(image->yuvPlanes[AVIF_CHAN_U] +
                                            y * image->yuvRowBytes[AVIF_CHAN_U]);
    auto *vp = reinterpret_cast<uint16_t *>(image->yuvPlanes[AVIF_CHAN_V] +
                                            y * image->yuvRowBytes[AVIF_CHAN_V]);
    for (int x = 0; x < width; ++x) {
      const size_t i = (static_cast<size_t>(y) * width + x) * 3;
      float r = std::min(std::max(0.0f, rgb[i + 0]) * scale, max_rel);
      float g = std::min(std::max(0.0f, rgb[i + 1]) * scale, max_rel);
      float b = std::min(std::max(0.0f, rgb[i + 2]) * scale, max_rel);

      // PQ encode each channel, then BT.2020 YUV (common HDR still path).
      const float rp = linear_to_pq(r);
      const float gp = linear_to_pq(g);
      const float bp = linear_to_pq(b);
      float Y, U, V;
      rgb_to_bt2020_yuv(rp, gp, bp, Y, U, V);
      yp[x] = to_10bit(Y);
      up[x] = chroma_to_10bit(U);
      vp[x] = chroma_to_10bit(V);
    }
  }

  avifEncoder *encoder = avifEncoderCreate();
  if (!encoder) {
    avifImageDestroy(image);
    throw std::runtime_error("avifEncoderCreate failed");
  }
  encoder->quality = 85;
  encoder->speed = 6;

  avifRWData output = AVIF_DATA_EMPTY;
  const avifResult res = avifEncoderWrite(encoder, image, &output);
  avifEncoderDestroy(encoder);
  avifImageDestroy(image);
  if (res != AVIF_RESULT_OK) {
    avifRWDataFree(&output);
    throw_avif("avifEncoderWrite", res);
  }
  try {
    write_file(path, output.data, output.size);
  } catch (...) {
    avifRWDataFree(&output);
    throw;
  }
  avifRWDataFree(&output);
}

void write_avif_rgba8(const std::string &path, int width, int height,
                      const unsigned char *rgba) {
  if (width <= 0 || height <= 0 || !rgba) {
    throw std::runtime_error("write_avif_rgba8: invalid image");
  }

  avifImage *image = avifImageCreate(static_cast<uint32_t>(width), static_cast<uint32_t>(height), 8,
                                     AVIF_PIXEL_FORMAT_YUV444);
  if (!image) {
    throw std::runtime_error("avifImageCreate failed");
  }
  image->colorPrimaries = AVIF_COLOR_PRIMARIES_BT709;
  image->transferCharacteristics = AVIF_TRANSFER_CHARACTERISTICS_SRGB;
  image->matrixCoefficients = AVIF_MATRIX_COEFFICIENTS_BT709;
  image->yuvRange = AVIF_RANGE_FULL;

  avifRGBImage rgb;
  avifRGBImageSetDefaults(&rgb, image);
  rgb.format = AVIF_RGB_FORMAT_RGBA;
  rgb.depth = 8;
  rgb.pixels = const_cast<uint8_t *>(rgba);
  rgb.rowBytes = static_cast<uint32_t>(width * 4);

  avifResult res = avifImageRGBToYUV(image, &rgb);
  if (res != AVIF_RESULT_OK) {
    avifImageDestroy(image);
    throw_avif("avifImageRGBToYUV", res);
  }

  avifEncoder *encoder = avifEncoderCreate();
  if (!encoder) {
    avifImageDestroy(image);
    throw std::runtime_error("avifEncoderCreate failed");
  }
  encoder->quality = 80;
  encoder->qualityAlpha = 80;
  encoder->speed = 6;

  avifRWData output = AVIF_DATA_EMPTY;
  res = avifEncoderWrite(encoder, image, &output);
  avifEncoderDestroy(encoder);
  avifImageDestroy(image);
  if (res != AVIF_RESULT_OK) {
    avifRWDataFree(&output);
    throw_avif("avifEncoderWrite", res);
  }
  try {
    write_file(path, output.data, output.size);
  } catch (...) {
    avifRWDataFree(&output);
    throw;
  }
  avifRWDataFree(&output);
}

} // namespace nrtx
