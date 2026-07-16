#include "nrtx/nrtx.h"

#include "LaunchParams.h"
#include "vec.h"

#include <optix.h>
#include <optix_function_table_definition.h>
#include <optix_stack_size.h>
#include <optix_stubs.h>

#include <cuda_runtime.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

namespace nrtx {
namespace {

#define CUDA_CHECK(call)                                                                           \
  do {                                                                                             \
    const cudaError_t err = call;                                                                  \
    if (err != cudaSuccess) {                                                                      \
      throw std::runtime_error(std::string("CUDA error: ") + cudaGetErrorString(err) + " @ " +     \
                               #call);                                                             \
    }                                                                                              \
  } while (0)

#define OPTIX_CHECK(call)                                                                          \
  do {                                                                                             \
    const OptixResult res = call;                                                                  \
    if (res != OPTIX_SUCCESS) {                                                                    \
      throw std::runtime_error(std::string("OptiX error ") + std::to_string(static_cast<int>(res)) + \
                               " @ " + #call);                                                     \
    }                                                                                              \
  } while (0)

void context_log_cb(unsigned int level, const char *tag, const char *message, void *) {
  std::cerr << "[OptiX][" << level << "][" << tag << "]: " << message << "\n";
}

std::string read_file(const std::string &path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("Failed to open file: " + path);
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

template <typename T> struct CudaBuffer {
  T *ptr = nullptr;
  size_t count = 0;

  void alloc(size_t n) {
    free();
    count = n;
    if (n) {
      CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&ptr), n * sizeof(T)));
    }
  }

  void free() {
    if (ptr) {
      cudaFree(ptr);
      ptr = nullptr;
      count = 0;
    }
  }

  void upload(const T *host, size_t n) {
    alloc(n);
    if (n) {
      CUDA_CHECK(cudaMemcpy(ptr, host, n * sizeof(T), cudaMemcpyHostToDevice));
    }
  }

  void upload(const std::vector<T> &host) { upload(host.data(), host.size()); }

  ~CudaBuffer() { free(); }
};

float3 aces_tonemap(const float3 &x) {
  const float a = 2.51f;
  const float b = 0.03f;
  const float c = 2.43f;
  const float d = 0.59f;
  const float e = 0.14f;
  auto tone = [&](float v) {
    return clamp((v * (a * v + b)) / (v * (c * v + d) + e), 0.0f, 1.0f);
  };
  return make_float3(tone(x.x), tone(x.y), tone(x.z));
}

CameraGPU make_camera_gpu(const Camera &cam) {
  float3 w = normalize(cam.lookat - cam.eye);
  float3 u = normalize(cross(w, cam.up));
  float3 v = cross(u, w);
  const float tan_half = std::tan(cam.fov_y_deg * 0.5f * static_cast<float>(M_PI) / 180.0f);
  v = v * tan_half;
  u = u * tan_half * cam.aspect;

  CameraGPU g;
  g.eye = cam.eye;
  g.U = u;
  g.V = v;
  g.W = w;
  g.lens_radius = cam.aperture * 0.5f;
  g.focus_dist = cam.focus_dist > 0.0f ? cam.focus_dist : length(cam.lookat - cam.eye);
  return g;
}

} // namespace

struct Renderer::Impl {
  OptixDeviceContext context = nullptr;
  OptixModule module = nullptr;
  OptixPipeline pipeline = nullptr;
  OptixProgramGroup raygen_pg = nullptr;
  OptixProgramGroup miss_radiance_pg = nullptr;
  OptixProgramGroup miss_shadow_pg = nullptr;
  OptixProgramGroup hit_radiance_pg = nullptr;
  OptixProgramGroup hit_shadow_pg = nullptr;
  OptixShaderBindingTable sbt = {};
  CUstream stream = nullptr;
  std::string ptx_path;
  OptixDenoiser denoiser = nullptr;
  OptixDenoiserSizes denoiser_sizes = {};
  CudaBuffer<unsigned char> denoiser_state;
  CudaBuffer<unsigned char> denoiser_scratch;

  Impl() {
    CUDA_CHECK(cudaFree(nullptr));
    CUDA_CHECK(cudaStreamCreate(&stream));

    OPTIX_CHECK(optixInit());
    OptixDeviceContextOptions options = {};
    options.logCallbackFunction = &context_log_cb;
    options.logCallbackLevel = 3;
    CUcontext cu_ctx = nullptr;
    OPTIX_CHECK(optixDeviceContextCreate(cu_ctx, &options, &context));
  }

  ~Impl() {
    if (denoiser) {
      optixDenoiserDestroy(denoiser);
    }
    if (sbt.raygenRecord) {
      cudaFree(reinterpret_cast<void *>(sbt.raygenRecord));
    }
    if (sbt.missRecordBase) {
      cudaFree(reinterpret_cast<void *>(sbt.missRecordBase));
    }
    if (sbt.hitgroupRecordBase) {
      cudaFree(reinterpret_cast<void *>(sbt.hitgroupRecordBase));
    }
    if (pipeline) {
      optixPipelineDestroy(pipeline);
    }
    if (raygen_pg) {
      optixProgramGroupDestroy(raygen_pg);
    }
    if (miss_radiance_pg) {
      optixProgramGroupDestroy(miss_radiance_pg);
    }
    if (miss_shadow_pg) {
      optixProgramGroupDestroy(miss_shadow_pg);
    }
    if (hit_radiance_pg) {
      optixProgramGroupDestroy(hit_radiance_pg);
    }
    if (hit_shadow_pg) {
      optixProgramGroupDestroy(hit_shadow_pg);
    }
    if (module) {
      optixModuleDestroy(module);
    }
    if (context) {
      optixDeviceContextDestroy(context);
    }
    if (stream) {
      cudaStreamDestroy(stream);
    }
  }

  void create_pipeline(const std::string &ptx_file) {
    ptx_path = ptx_file;
    char log[2048];
    size_t log_size = sizeof(log);

    const std::string ptx = read_file(ptx_file);

    OptixModuleCompileOptions module_options = {};
    module_options.maxRegisterCount = OPTIX_COMPILE_DEFAULT_MAX_REGISTER_COUNT;
    module_options.optLevel = OPTIX_COMPILE_OPTIMIZATION_DEFAULT;
    module_options.debugLevel = OPTIX_COMPILE_DEBUG_LEVEL_MINIMAL;

    OptixPipelineCompileOptions pipeline_options = {};
    pipeline_options.usesMotionBlur = false;
    pipeline_options.traversableGraphFlags = OPTIX_TRAVERSABLE_GRAPH_FLAG_ALLOW_SINGLE_GAS;
    pipeline_options.numPayloadValues = 2;
    pipeline_options.numAttributeValues = 2;
    pipeline_options.exceptionFlags = OPTIX_EXCEPTION_FLAG_NONE;
    pipeline_options.pipelineLaunchParamsVariableName = "params";
    pipeline_options.usesPrimitiveTypeFlags = OPTIX_PRIMITIVE_TYPE_FLAGS_TRIANGLE;

    OPTIX_CHECK(optixModuleCreate(context, &module_options, &pipeline_options, ptx.data(),
                                  ptx.size(), log, &log_size, &module));

    OptixProgramGroupOptions pg_options = {};
    OptixProgramGroupDesc pg_desc = {};

    pg_desc.kind = OPTIX_PROGRAM_GROUP_KIND_RAYGEN;
    pg_desc.raygen.module = module;
    pg_desc.raygen.entryFunctionName = "__raygen__rg";
    log_size = sizeof(log);
    OPTIX_CHECK(optixProgramGroupCreate(context, &pg_desc, 1, &pg_options, log, &log_size,
                                        &raygen_pg));

    pg_desc = {};
    pg_desc.kind = OPTIX_PROGRAM_GROUP_KIND_MISS;
    pg_desc.miss.module = module;
    pg_desc.miss.entryFunctionName = "__miss__radiance";
    log_size = sizeof(log);
    OPTIX_CHECK(optixProgramGroupCreate(context, &pg_desc, 1, &pg_options, log, &log_size,
                                        &miss_radiance_pg));

    pg_desc = {};
    pg_desc.kind = OPTIX_PROGRAM_GROUP_KIND_MISS;
    pg_desc.miss.module = module;
    pg_desc.miss.entryFunctionName = "__miss__shadow";
    log_size = sizeof(log);
    OPTIX_CHECK(optixProgramGroupCreate(context, &pg_desc, 1, &pg_options, log, &log_size,
                                        &miss_shadow_pg));

    pg_desc = {};
    pg_desc.kind = OPTIX_PROGRAM_GROUP_KIND_HITGROUP;
    pg_desc.hitgroup.moduleCH = module;
    pg_desc.hitgroup.entryFunctionNameCH = "__closesthit__radiance";
    log_size = sizeof(log);
    OPTIX_CHECK(optixProgramGroupCreate(context, &pg_desc, 1, &pg_options, log, &log_size,
                                        &hit_radiance_pg));

    pg_desc = {};
    pg_desc.kind = OPTIX_PROGRAM_GROUP_KIND_HITGROUP;
    pg_desc.hitgroup.moduleAH = module;
    pg_desc.hitgroup.entryFunctionNameAH = "__anyhit__shadow";
    log_size = sizeof(log);
    OPTIX_CHECK(optixProgramGroupCreate(context, &pg_desc, 1, &pg_options, log, &log_size,
                                        &hit_shadow_pg));

    OptixProgramGroup program_groups[] = {raygen_pg, miss_radiance_pg, miss_shadow_pg,
                                          hit_radiance_pg, hit_shadow_pg};

    OptixPipelineLinkOptions link_options = {};
    link_options.maxTraceDepth = 2;
    log_size = sizeof(log);
    OPTIX_CHECK(optixPipelineCreate(context, &pipeline_options, &link_options, program_groups,
                                    sizeof(program_groups) / sizeof(program_groups[0]), log,
                                    &log_size, &pipeline));

    OptixStackSizes stack_sizes = {};
    for (auto pg : program_groups) {
      OPTIX_CHECK(optixUtilAccumulateStackSizes(pg, &stack_sizes, pipeline));
    }
    unsigned direct = 0, continuable = 0, state = 0;
    OPTIX_CHECK(optixUtilComputeStackSizes(&stack_sizes, 2, 0, 0, &direct, &continuable, &state));
    OPTIX_CHECK(optixPipelineSetStackSize(pipeline, direct, continuable, state, 1));
  }

  OptixTraversableHandle build_gas(const std::vector<float3> &vertices,
                                   const std::vector<int3> &indices,
                                   CudaBuffer<float3> &d_vertices, CudaBuffer<int3> &d_indices) {
    d_vertices.upload(vertices);
    d_indices.upload(indices);

    OptixBuildInput build_input = {};
    build_input.type = OPTIX_BUILD_INPUT_TYPE_TRIANGLES;

    CUdeviceptr v_ptr = reinterpret_cast<CUdeviceptr>(d_vertices.ptr);
    CUdeviceptr i_ptr = reinterpret_cast<CUdeviceptr>(d_indices.ptr);
    build_input.triangleArray.vertexFormat = OPTIX_VERTEX_FORMAT_FLOAT3;
    build_input.triangleArray.numVertices = static_cast<unsigned>(vertices.size());
    build_input.triangleArray.vertexBuffers = &v_ptr;
    build_input.triangleArray.indexFormat = OPTIX_INDICES_FORMAT_UNSIGNED_INT3;
    build_input.triangleArray.numIndexTriplets = static_cast<unsigned>(indices.size());
    build_input.triangleArray.indexBuffer = i_ptr;

    unsigned flags[1] = {OPTIX_GEOMETRY_FLAG_NONE};
    build_input.triangleArray.flags = flags;
    build_input.triangleArray.numSbtRecords = 1;

    OptixAccelBuildOptions accel_options = {};
    accel_options.buildFlags = OPTIX_BUILD_FLAG_ALLOW_COMPACTION | OPTIX_BUILD_FLAG_PREFER_FAST_TRACE;
    accel_options.operation = OPTIX_BUILD_OPERATION_BUILD;

    OptixAccelBufferSizes gas_sizes;
    OPTIX_CHECK(optixAccelComputeMemoryUsage(context, &accel_options, &build_input, 1, &gas_sizes));

    CudaBuffer<char> temp;
    temp.alloc(gas_sizes.tempSizeInBytes);
    CudaBuffer<char> output;
    output.alloc(gas_sizes.outputSizeInBytes);

    OptixAccelEmitDesc emit = {};
    CudaBuffer<uint64_t> compact_size_buf;
    compact_size_buf.alloc(1);
    emit.type = OPTIX_PROPERTY_TYPE_COMPACTED_SIZE;
    emit.result = reinterpret_cast<CUdeviceptr>(compact_size_buf.ptr);

    OptixTraversableHandle handle = 0;
    OPTIX_CHECK(optixAccelBuild(context, stream, &accel_options, &build_input, 1,
                                reinterpret_cast<CUdeviceptr>(temp.ptr), gas_sizes.tempSizeInBytes,
                                reinterpret_cast<CUdeviceptr>(output.ptr),
                                gas_sizes.outputSizeInBytes, &handle, &emit, 1));
    CUDA_CHECK(cudaStreamSynchronize(stream));

    uint64_t compact_size = 0;
    CUDA_CHECK(cudaMemcpy(&compact_size, compact_size_buf.ptr, sizeof(uint64_t),
                          cudaMemcpyDeviceToHost));

    CudaBuffer<char> *gas_buffer = new CudaBuffer<char>();
    gas_buffer->alloc(compact_size);
    OPTIX_CHECK(optixAccelCompact(context, stream, handle, reinterpret_cast<CUdeviceptr>(gas_buffer->ptr),
                                  compact_size, &handle));
    CUDA_CHECK(cudaStreamSynchronize(stream));

    // Leak gas_buffer intentionally until process exit (lifetime of GAS).
    // Keep pointer in a static list to avoid dangling.
    static std::vector<CudaBuffer<char> *> gas_keepalives;
    gas_keepalives.push_back(gas_buffer);
    return handle;
  }

  void build_sbt(const HitGroupData &hit_data) {
    struct alignas(OPTIX_SBT_RECORD_ALIGNMENT) RaygenRecord {
      char header[OPTIX_SBT_RECORD_HEADER_SIZE];
    };
    struct alignas(OPTIX_SBT_RECORD_ALIGNMENT) MissRecord {
      char header[OPTIX_SBT_RECORD_HEADER_SIZE];
    };
    struct alignas(OPTIX_SBT_RECORD_ALIGNMENT) HitgroupRecord {
      char header[OPTIX_SBT_RECORD_HEADER_SIZE];
      HitGroupData data;
    };

    RaygenRecord rg = {};
    OPTIX_CHECK(optixSbtRecordPackHeader(raygen_pg, &rg));
    CUdeviceptr d_rg = 0;
    CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_rg), sizeof(RaygenRecord)));
    CUDA_CHECK(cudaMemcpy(reinterpret_cast<void *>(d_rg), &rg, sizeof(RaygenRecord),
                          cudaMemcpyHostToDevice));

    MissRecord ms[RAY_TYPE_COUNT] = {};
    OPTIX_CHECK(optixSbtRecordPackHeader(miss_radiance_pg, &ms[RAY_TYPE_RADIANCE]));
    OPTIX_CHECK(optixSbtRecordPackHeader(miss_shadow_pg, &ms[RAY_TYPE_SHADOW]));
    CUdeviceptr d_ms = 0;
    CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_ms), sizeof(ms)));
    CUDA_CHECK(cudaMemcpy(reinterpret_cast<void *>(d_ms), ms, sizeof(ms), cudaMemcpyHostToDevice));

    HitgroupRecord hg[RAY_TYPE_COUNT] = {};
    OPTIX_CHECK(optixSbtRecordPackHeader(hit_radiance_pg, &hg[RAY_TYPE_RADIANCE]));
    OPTIX_CHECK(optixSbtRecordPackHeader(hit_shadow_pg, &hg[RAY_TYPE_SHADOW]));
    hg[RAY_TYPE_RADIANCE].data = hit_data;
    hg[RAY_TYPE_SHADOW].data = hit_data;
    CUdeviceptr d_hg = 0;
    CUDA_CHECK(cudaMalloc(reinterpret_cast<void **>(&d_hg), sizeof(hg)));
    CUDA_CHECK(cudaMemcpy(reinterpret_cast<void *>(d_hg), hg, sizeof(hg), cudaMemcpyHostToDevice));

    sbt.raygenRecord = d_rg;
    sbt.missRecordBase = d_ms;
    sbt.missRecordStrideInBytes = static_cast<unsigned>(sizeof(MissRecord));
    sbt.missRecordCount = RAY_TYPE_COUNT;
    sbt.hitgroupRecordBase = d_hg;
    sbt.hitgroupRecordStrideInBytes = static_cast<unsigned>(sizeof(HitgroupRecord));
    sbt.hitgroupRecordCount = RAY_TYPE_COUNT;
  }

  void setup_denoiser(int width, int height) {
    if (denoiser) {
      optixDenoiserDestroy(denoiser);
      denoiser = nullptr;
    }
    OptixDenoiserOptions options = {};
    options.guideAlbedo = 1;
    options.guideNormal = 1;
    OPTIX_CHECK(optixDenoiserCreate(context, OPTIX_DENOISER_MODEL_KIND_HDR, &options, &denoiser));
    OPTIX_CHECK(optixDenoiserComputeMemoryResources(denoiser, width, height, &denoiser_sizes));
    denoiser_state.alloc(denoiser_sizes.stateSizeInBytes);
    denoiser_scratch.alloc(denoiser_sizes.withoutOverlapScratchSizeInBytes);
    OPTIX_CHECK(optixDenoiserSetup(denoiser, stream, width, height,
                                   reinterpret_cast<CUdeviceptr>(denoiser_state.ptr),
                                   denoiser_sizes.stateSizeInBytes,
                                   reinterpret_cast<CUdeviceptr>(denoiser_scratch.ptr),
                                   denoiser_sizes.withoutOverlapScratchSizeInBytes));
  }

  void denoise_image(int width, int height, float4 *beauty, float3 *albedo, float3 *normal,
                     float4 *output) {
  OptixDenoiserParams dparams = {};
  dparams.hdrIntensity = 0;
  dparams.blendFactor = 0.0f;
  dparams.hdrAverageColor = 0;
  dparams.temporalModeUsePreviousLayers = 0;

    OptixImage2D input_beauty = {};
    input_beauty.data = reinterpret_cast<CUdeviceptr>(beauty);
    input_beauty.width = width;
    input_beauty.height = height;
    input_beauty.rowStrideInBytes = width * sizeof(float4);
    input_beauty.pixelStrideInBytes = sizeof(float4);
    input_beauty.format = OPTIX_PIXEL_FORMAT_FLOAT4;

    OptixImage2D input_albedo = {};
    input_albedo.data = reinterpret_cast<CUdeviceptr>(albedo);
    input_albedo.width = width;
    input_albedo.height = height;
    input_albedo.rowStrideInBytes = width * sizeof(float3);
    input_albedo.pixelStrideInBytes = sizeof(float3);
    input_albedo.format = OPTIX_PIXEL_FORMAT_FLOAT3;

    OptixImage2D input_normal = {};
    input_normal.data = reinterpret_cast<CUdeviceptr>(normal);
    input_normal.width = width;
    input_normal.height = height;
    input_normal.rowStrideInBytes = width * sizeof(float3);
    input_normal.pixelStrideInBytes = sizeof(float3);
    input_normal.format = OPTIX_PIXEL_FORMAT_FLOAT3;

    OptixImage2D output_image = {};
    output_image.data = reinterpret_cast<CUdeviceptr>(output);
    output_image.width = width;
    output_image.height = height;
    output_image.rowStrideInBytes = width * sizeof(float4);
    output_image.pixelStrideInBytes = sizeof(float4);
    output_image.format = OPTIX_PIXEL_FORMAT_FLOAT4;

    OptixDenoiserGuideLayer guide = {};
    guide.albedo = input_albedo;
    guide.normal = input_normal;

    OptixDenoiserLayer layer = {};
    layer.input = input_beauty;
    layer.output = output_image;

    OPTIX_CHECK(optixDenoiserInvoke(denoiser, stream, &dparams,
                                    reinterpret_cast<CUdeviceptr>(denoiser_state.ptr),
                                    denoiser_sizes.stateSizeInBytes, &guide, &layer, 1, 0, 0,
                                    reinterpret_cast<CUdeviceptr>(denoiser_scratch.ptr),
                                    denoiser_sizes.withoutOverlapScratchSizeInBytes));
    CUDA_CHECK(cudaStreamSynchronize(stream));
  }
};

Renderer::Renderer() : impl_(std::make_unique<Impl>()) {}
Renderer::~Renderer() = default;

void Renderer::render(const Scene &scene, const Camera &camera, const RenderConfig &config) {
  if (scene.meshes.empty()) {
    throw std::runtime_error("Scene has no meshes");
  }
  if (scene.materials.empty()) {
    throw std::runtime_error("Scene has no materials");
  }

  const char *ptx_env = std::getenv("NRTX_PTX");
  std::string ptx_path = ptx_env ? ptx_env : "";
  if (ptx_path.empty()) {
    // Prefer OptiX-IR next to the binary's build dir, then PTX cwd fallbacks.
    const char *candidates[] = {"shaders.optixir", "build/shaders.optixir", "shaders.ptx",
                                "build/shaders.ptx"};
    for (const char *c : candidates) {
      std::ifstream probe(c, std::ios::binary);
      if (probe) {
        ptx_path = c;
        break;
      }
    }
  }
  if (ptx_path.empty()) {
    throw std::runtime_error("Set NRTX_PTX to shaders.optixir/ptx path");
  }
  std::cout << "Loading device module: " << ptx_path << "\n";
  if (!impl_->pipeline) {
    impl_->create_pipeline(ptx_path);
  }

  // Merge meshes into one GAS
  std::vector<float3> vertices;
  std::vector<float2> texcoords;
  std::vector<float3> normals;
  std::vector<int3> indices;
  std::vector<int> material_ids;
  bool any_normals = false;
  for (const Mesh &mesh : scene.meshes) {
    const int base = static_cast<int>(vertices.size());
    vertices.insert(vertices.end(), mesh.vertices.begin(), mesh.vertices.end());
    if (mesh.texcoords.size() == mesh.vertices.size()) {
      texcoords.insert(texcoords.end(), mesh.texcoords.begin(), mesh.texcoords.end());
    } else {
      texcoords.insert(texcoords.end(), mesh.vertices.size(), make_float2(0.0f, 0.0f));
    }
    if (mesh.normals.size() == mesh.vertices.size()) {
      any_normals = true;
      normals.insert(normals.end(), mesh.normals.begin(), mesh.normals.end());
    } else {
      normals.insert(normals.end(), mesh.vertices.size(), make_float3(0.0f, 0.0f, 0.0f));
    }
    for (size_t i = 0; i < mesh.indices.size(); ++i) {
      const int3 idx = mesh.indices[i];
      indices.push_back(make_int3(idx.x + base, idx.y + base, idx.z + base));
      material_ids.push_back(mesh.material_ids[i]);
    }
  }

  CudaBuffer<float3> d_vertices;
  CudaBuffer<float2> d_texcoords;
  CudaBuffer<float3> d_normals;
  CudaBuffer<int3> d_indices;
  CudaBuffer<int> d_mat_ids;
  d_texcoords.upload(texcoords);
  d_mat_ids.upload(material_ids);
  if (any_normals) {
    d_normals.upload(normals);
  }

  OptixTraversableHandle gas = impl_->build_gas(vertices, indices, d_vertices, d_indices);

  HitGroupData hit_data;
  hit_data.vertices = d_vertices.ptr;
  hit_data.texcoords = d_texcoords.ptr;
  hit_data.normals = any_normals ? d_normals.ptr : nullptr;
  hit_data.indices = d_indices.ptr;
  hit_data.material_ids = d_mat_ids.ptr;
  impl_->build_sbt(hit_data);

  std::vector<MaterialGPU> materials_gpu(scene.materials.size());
  for (size_t i = 0; i < scene.materials.size(); ++i) {
    const Material &m = scene.materials[i];
    materials_gpu[i].base_color = m.base_color;
    materials_gpu[i].metallic = m.metallic;
    materials_gpu[i].roughness = m.roughness;
    materials_gpu[i].transmission = m.transmission;
    materials_gpu[i].ior = m.ior;
    materials_gpu[i].emission = m.emission;
    materials_gpu[i].absorption = m.absorption;
    materials_gpu[i].flags = m.flags;
    materials_gpu[i].volume_index = m.volume_index;
    materials_gpu[i].albedo_tex = m.albedo_tex;
    materials_gpu[i].pad = 0;
  }
  CudaBuffer<MaterialGPU> d_materials;
  d_materials.upload(materials_gpu);

  // Upload albedo textures (RGBA8 → uchar4)
  std::vector<CudaBuffer<uchar4>> d_tex_pixels(scene.textures.size());
  std::vector<TextureGPU> textures_gpu(scene.textures.size());
  for (size_t i = 0; i < scene.textures.size(); ++i) {
    const Texture2D &tex = scene.textures[i];
    std::vector<uchar4> pixels(static_cast<size_t>(tex.width) * tex.height);
    for (size_t p = 0; p < pixels.size(); ++p) {
      pixels[p] = make_uchar4(tex.rgba[p * 4 + 0], tex.rgba[p * 4 + 1], tex.rgba[p * 4 + 2],
                              tex.rgba[p * 4 + 3]);
    }
    d_tex_pixels[i].upload(pixels);
    textures_gpu[i].pixels = d_tex_pixels[i].ptr;
    textures_gpu[i].width = tex.width;
    textures_gpu[i].height = tex.height;
    textures_gpu[i].pad = 0;
  }
  CudaBuffer<TextureGPU> d_textures;
  if (!textures_gpu.empty()) {
    d_textures.upload(textures_gpu);
  }

  CudaBuffer<QuadLight> d_lights;
  if (!scene.lights.empty()) {
    d_lights.upload(scene.lights);
  }

  CudaBuffer<SpotLight> d_spots;
  if (!scene.spot_lights.empty()) {
    d_spots.upload(scene.spot_lights);
  }

  CudaBuffer<FlameVolume> d_volumes;
  if (!scene.volumes.empty()) {
    d_volumes.upload(scene.volumes);
  }

  const int width = config.width;
  const int height = config.height;
  const size_t pixel_count = static_cast<size_t>(width) * height;

  CudaBuffer<float4> d_accum;
  CudaBuffer<float3> d_albedo;
  CudaBuffer<float3> d_normal;
  CudaBuffer<float4> d_denoised;
  d_accum.alloc(pixel_count);
  d_albedo.alloc(pixel_count);
  d_normal.alloc(pixel_count);
  d_denoised.alloc(pixel_count);
  CUDA_CHECK(cudaMemset(d_accum.ptr, 0, pixel_count * sizeof(float4)));
  CUDA_CHECK(cudaMemset(d_albedo.ptr, 0, pixel_count * sizeof(float3)));
  CUDA_CHECK(cudaMemset(d_normal.ptr, 0, pixel_count * sizeof(float3)));

  CudaBuffer<LaunchParams> d_params;
  d_params.alloc(1);

  LaunchParams lp = {};
  lp.handle = gas;
  lp.accum_buffer = d_accum.ptr;
  lp.albedo_buffer = d_albedo.ptr;
  lp.normal_buffer = d_normal.ptr;
  lp.width = width;
  lp.height = height;
  lp.samples_per_launch = config.samples_per_launch;
  lp.max_depth = config.max_depth;
  lp.camera = make_camera_gpu(camera);
  lp.materials = d_materials.ptr;
  lp.material_count = static_cast<int>(materials_gpu.size());
  lp.lights = d_lights.ptr;
  lp.light_count = static_cast<int>(scene.lights.size());
  lp.spots = d_spots.ptr;
  lp.spot_count = static_cast<int>(scene.spot_lights.size());
  lp.volumes = d_volumes.ptr;
  lp.volume_count = static_cast<int>(scene.volumes.size());
  lp.textures = d_textures.ptr;
  lp.texture_count = static_cast<int>(textures_gpu.size());
  lp.background_top = scene.background_top;
  lp.background_bottom = scene.background_bottom;
  lp.enable_nee = config.enable_nee ? 1 : 0;

  CudaBuffer<float3> d_env_pixels;
  CudaBuffer<float> d_env_cdf;
  CudaBuffer<float> d_env_row_cdf;
  lp.env_pixels = nullptr;
  lp.env_cdf = nullptr;
  lp.env_row_cdf = nullptr;
  lp.env_width = 0;
  lp.env_height = 0;
  lp.env_total_lum = 0.0f;
  lp.has_env = 0;
  if (!scene.env_map.empty()) {
    d_env_pixels.upload(scene.env_map.pixels);
    d_env_cdf.upload(scene.env_map.cdf);
    d_env_row_cdf.upload(scene.env_map.row_cdf);
    lp.env_pixels = d_env_pixels.ptr;
    lp.env_cdf = d_env_cdf.ptr;
    lp.env_row_cdf = d_env_row_cdf.ptr;
    lp.env_width = scene.env_map.width;
    lp.env_height = scene.env_map.height;
    lp.env_total_lum = scene.env_map.total_luminance;
    lp.has_env = 1;
    std::cout << "Env map: " << scene.env_map.width << "x" << scene.env_map.height << "\n";
  }

  const int launches = (config.spp + config.samples_per_launch - 1) / config.samples_per_launch;
  std::cout << "Rendering " << width << "x" << height << " @ " << config.spp << " spp (" << launches
            << " launches)\n";

  const auto t0 = std::chrono::steady_clock::now();
  for (int i = 0; i < launches; ++i) {
    lp.sample_index = i;
    CUDA_CHECK(cudaMemcpy(d_params.ptr, &lp, sizeof(LaunchParams), cudaMemcpyHostToDevice));
    OPTIX_CHECK(optixLaunch(impl_->pipeline, impl_->stream, reinterpret_cast<CUdeviceptr>(d_params.ptr),
                            sizeof(LaunchParams), &impl_->sbt, width, height, 1));
    CUDA_CHECK(cudaStreamSynchronize(impl_->stream));
    if ((i + 1) % 16 == 0 || i + 1 == launches) {
      std::cout << "\r" << (100 * (i + 1) / launches) << "%" << std::flush;
    }
  }
  std::cout << "\n";
  const auto t1 = std::chrono::steady_clock::now();
  const float seconds = std::chrono::duration<float>(t1 - t0).count();
  std::cout << "Path tracing: " << seconds << " s\n";

  float4 *final_device = d_accum.ptr;
  if (config.denoise) {
    try {
      std::cout << "Denoising...\n";
      impl_->setup_denoiser(width, height);
      impl_->denoise_image(width, height, d_accum.ptr, d_albedo.ptr, d_normal.ptr, d_denoised.ptr);
      final_device = d_denoised.ptr;
    } catch (const std::exception &ex) {
      std::cerr << "Denoiser unavailable, writing noisy image: " << ex.what() << "\n";
      final_device = d_accum.ptr;
    }
  }

  std::vector<float4> host(pixel_count);
  CUDA_CHECK(cudaMemcpy(host.data(), final_device, pixel_count * sizeof(float4),
                        cudaMemcpyDeviceToHost));

  std::vector<unsigned char> rgba(pixel_count * 4);
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      const size_t dst = static_cast<size_t>(y) * width + x;
      const size_t src = static_cast<size_t>(height - 1 - y) * width + x;
      float3 c = make_float3(host[src].x, host[src].y, host[src].z);
      c = aces_tonemap(c);
      c = make_float3(std::pow(c.x, 1.0f / 2.2f), std::pow(c.y, 1.0f / 2.2f),
                      std::pow(c.z, 1.0f / 2.2f));
      rgba[dst * 4 + 0] = static_cast<unsigned char>(clamp(c.x, 0.0f, 1.0f) * 255.0f + 0.5f);
      rgba[dst * 4 + 1] = static_cast<unsigned char>(clamp(c.y, 0.0f, 1.0f) * 255.0f + 0.5f);
      rgba[dst * 4 + 2] = static_cast<unsigned char>(clamp(c.z, 0.0f, 1.0f) * 255.0f + 0.5f);
      rgba[dst * 4 + 3] = 255;
    }
  }

  if (!stbi_write_png(config.output_path.c_str(), width, height, 4, rgba.data(), width * 4)) {
    throw std::runtime_error("Failed to write PNG: " + config.output_path);
  }
  std::cout << "Wrote " << config.output_path << "\n";
}

} // namespace nrtx
