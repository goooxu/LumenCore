#include "nrtx/nrtx.h"
#include "nrtx/image_io.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(LUMENCORE_HAS_VULKAN)
#include <vulkan/vulkan.h>
#endif

namespace nrtx {

bool vulkan_backend_available() {
#if defined(LUMENCORE_HAS_VULKAN)
  return true;
#else
  return false;
#endif
}

#if defined(LUMENCORE_HAS_VULKAN)

namespace {

#define VK_CHECK(call)                                                                             \
  do {                                                                                             \
    const VkResult _vk_res = (call);                                                               \
    if (_vk_res != VK_SUCCESS) {                                                                   \
      throw std::runtime_error(std::string("Vulkan error ") +                                      \
                               std::to_string(static_cast<int>(_vk_res)) + " @ " + #call);         \
    }                                                                                              \
  } while (0)

// Must match GLSL LaunchParams / MaterialGPU / QuadLight with scalar layout.
struct CameraGPUHost {
  float eye[3];
  float pad0;
  float U[3];
  float pad1;
  float V[3];
  float pad2;
  float W[3];
  float lens_radius;
  float focus_dist;
  float pad3;
  float pad4;
  float pad5;
};

struct MaterialGPUHost {
  float base_color[3];
  float metallic;
  float roughness;
  float transmission;
  float ior;
  float pad0;
  float emission[3];
  float pad1;
  float absorption[3];
  int32_t flags;
};

struct QuadLightHost {
  float corner[3];
  float pad0;
  float u[3];
  float pad1;
  float v[3];
  float pad2;
  float emission[3];
  float inv_area;
  int32_t use_mis;
  int32_t pad3;
  int32_t pad4;
  int32_t pad5;
};

struct SpotLightHost {
  float position[3];
  float pad0;
  float direction[3];
  float cos_inner;
  float emission[3];
  float cos_outer;
};

struct VulkanLaunchParams {
  uint64_t tlas; // unused in shader; AS is a descriptor
  int32_t width;
  int32_t height;
  int32_t sample_index;
  int32_t samples_per_launch;
  int32_t max_depth;
  int32_t material_count;
  int32_t light_count;
  int32_t spot_count;
  int32_t enable_nee;
  int32_t pad_flags;
  float background_top[3];
  float pad0;
  float background_bottom[3];
  float pad1;
  CameraGPUHost camera;
};

static_assert(sizeof(MaterialGPUHost) == 64, "MaterialGPUHost layout");
static_assert(sizeof(QuadLightHost) == 80, "QuadLightHost layout");
static_assert(sizeof(SpotLightHost) == 48, "SpotLightHost layout");

void set3(float *d, const float3 &v) {
  d[0] = v.x;
  d[1] = v.y;
  d[2] = v.z;
}

std::vector<char> read_binary(const std::string &path) {
  std::ifstream in(path, std::ios::binary | std::ios::ate);
  if (!in) {
    throw std::runtime_error("Failed to open SPIR-V: " + path);
  }
  const std::streamsize size = in.tellg();
  in.seekg(0, std::ios::beg);
  std::vector<char> buf(static_cast<size_t>(size));
  if (!in.read(buf.data(), size)) {
    throw std::runtime_error("Failed to read SPIR-V: " + path);
  }
  return buf;
}

std::string find_spv(const char *name) {
  const char *env = std::getenv("NRTX_VK_SPV_DIR");
  std::vector<std::string> dirs;
  if (env && *env) {
    dirs.emplace_back(env);
  }
  dirs.push_back(".");
  dirs.push_back("build");
  for (const auto &d : dirs) {
    const std::string path = d + "/" + name;
    std::ifstream probe(path, std::ios::binary);
    if (probe) {
      return path;
    }
  }
  throw std::runtime_error(std::string("SPIR-V not found: ") + name +
                           " (set NRTX_VK_SPV_DIR to the CMake build directory)");
}

// Dynamic RT entry points
#define NRTX_VK_RT_FNS                                                                             \
  X(vkGetBufferDeviceAddress)                                                                      \
  X(vkCreateAccelerationStructureKHR)                                                              \
  X(vkDestroyAccelerationStructureKHR)                                                             \
  X(vkGetAccelerationStructureBuildSizesKHR)                                                       \
  X(vkCmdBuildAccelerationStructuresKHR)                                                           \
  X(vkGetAccelerationStructureDeviceAddressKHR)                                                    \
  X(vkCmdTraceRaysKHR)                                                                             \
  X(vkGetRayTracingShaderGroupHandlesKHR)                                                          \
  X(vkCreateRayTracingPipelinesKHR)

#define X(name) PFN_##name name = nullptr;
struct RtDispatch {
  NRTX_VK_RT_FNS
};
#undef X

void load_rt_dispatch(VkDevice device, VkInstance instance, RtDispatch &d) {
#define X(name)                                                                                    \
  d.name = reinterpret_cast<PFN_##name>(vkGetDeviceProcAddr(device, #name));                       \
  if (!d.name) {                                                                                   \
    d.name = reinterpret_cast<PFN_##name>(vkGetInstanceProcAddr(instance, #name));                 \
  }                                                                                                \
  if (!d.name) {                                                                                   \
    throw std::runtime_error("Missing Vulkan RT function: " #name);                                \
  }
  NRTX_VK_RT_FNS
#undef X
}

struct Buffer {
  VkBuffer buffer = VK_NULL_HANDLE;
  VkDeviceMemory memory = VK_NULL_HANDLE;
  VkDeviceAddress address = 0;
  VkDeviceSize size = 0;
  void *mapped = nullptr;
};

struct Image {
  VkImage image = VK_NULL_HANDLE;
  VkDeviceMemory memory = VK_NULL_HANDLE;
  VkImageView view = VK_NULL_HANDLE;
  uint32_t width = 0;
  uint32_t height = 0;
};

struct AccelerationStructure {
  VkAccelerationStructureKHR handle = VK_NULL_HANDLE;
  Buffer buffer;
  VkDeviceAddress address = 0;
};

struct VulkanRT {
  VkInstance instance = VK_NULL_HANDLE;
  VkPhysicalDevice physical = VK_NULL_HANDLE;
  VkDevice device = VK_NULL_HANDLE;
  uint32_t queue_family = 0;
  VkQueue queue = VK_NULL_HANDLE;
  RtDispatch rt{};
  VkPhysicalDeviceRayTracingPipelinePropertiesKHR rt_props{
      VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_RAY_TRACING_PIPELINE_PROPERTIES_KHR};
  VkPhysicalDeviceAccelerationStructurePropertiesKHR as_props{
      VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ACCELERATION_STRUCTURE_PROPERTIES_KHR};

  VkCommandPool cmd_pool = VK_NULL_HANDLE;
  VkDescriptorPool desc_pool = VK_NULL_HANDLE;
  VkDescriptorSetLayout desc_layout = VK_NULL_HANDLE;
  VkPipelineLayout pipeline_layout = VK_NULL_HANDLE;
  VkPipeline pipeline = VK_NULL_HANDLE;
  VkDescriptorSet desc_set = VK_NULL_HANDLE;

  Buffer sbt_buffer;
  VkStridedDeviceAddressRegionKHR sbt_rgen{};
  VkStridedDeviceAddressRegionKHR sbt_miss{};
  VkStridedDeviceAddressRegionKHR sbt_hit{};
  VkStridedDeviceAddressRegionKHR sbt_callable{};

  void init() {
    // Instance
    VkApplicationInfo app{};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "LumenCore";
    app.applicationVersion = VK_MAKE_VERSION(0, 1, 0);
    app.pEngineName = "LumenCore";
    app.engineVersion = VK_MAKE_VERSION(0, 1, 0);
    app.apiVersion = VK_API_VERSION_1_2;

    const char *inst_exts[] = {VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME};
    VkInstanceCreateInfo ici{};
    ici.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ici.pApplicationInfo = &app;
    ici.enabledExtensionCount = 1;
    ici.ppEnabledExtensionNames = inst_exts;
    VK_CHECK(vkCreateInstance(&ici, nullptr, &instance));

    uint32_t count = 0;
    VK_CHECK(vkEnumeratePhysicalDevices(instance, &count, nullptr));
    if (count == 0) {
      throw std::runtime_error("Vulkan: no physical devices");
    }
    std::vector<VkPhysicalDevice> devices(count);
    VK_CHECK(vkEnumeratePhysicalDevices(instance, &count, devices.data()));

    auto score_device = [](VkPhysicalDevice pd) -> int {
      VkPhysicalDeviceProperties props{};
      vkGetPhysicalDeviceProperties(pd, &props);
      int score = 0;
      if (props.vendorID == 0x10DE) {
        score += 1000;
      }
      if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
        score += 100;
      } else if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU) {
        score += 10;
      } else if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_CPU) {
        score -= 100;
      }
      // Prefer devices that expose RT pipeline extension.
      uint32_t ext_count = 0;
      vkEnumerateDeviceExtensionProperties(pd, nullptr, &ext_count, nullptr);
      std::vector<VkExtensionProperties> exts(ext_count);
      vkEnumerateDeviceExtensionProperties(pd, nullptr, &ext_count, exts.data());
      for (const auto &e : exts) {
        if (std::strcmp(e.extensionName, VK_KHR_RAY_TRACING_PIPELINE_EXTENSION_NAME) == 0) {
          score += 500;
        }
      }
      return score;
    };

    physical = devices[0];
    int best = score_device(physical);
    for (VkPhysicalDevice pd : devices) {
      const int s = score_device(pd);
      if (s > best) {
        best = s;
        physical = pd;
      }
    }

    {
      VkPhysicalDeviceProperties props{};
      vkGetPhysicalDeviceProperties(physical, &props);
      std::cout << "Vulkan device: " << props.deviceName << " (vendor=0x" << std::hex
                << props.vendorID << std::dec << ")\n";
      if (props.vendorID != 0x10DE) {
        throw std::runtime_error(
            "Vulkan Phase 1 requires an NVIDIA GPU with ray tracing (got non-NVIDIA device). "
            "Check Docker ICD mounts (libEGL, nvidia_icd.json, NVIDIA_DRIVER_CAPABILITIES).");
      }
    }

    // Features chain
    VkPhysicalDeviceBufferDeviceAddressFeatures bda{
        VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_BUFFER_DEVICE_ADDRESS_FEATURES};
    bda.bufferDeviceAddress = VK_TRUE;
    VkPhysicalDeviceAccelerationStructureFeaturesKHR as_feat{
        VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ACCELERATION_STRUCTURE_FEATURES_KHR};
    as_feat.accelerationStructure = VK_TRUE;
    as_feat.pNext = &bda;
    VkPhysicalDeviceRayTracingPipelineFeaturesKHR rt_feat{
        VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_RAY_TRACING_PIPELINE_FEATURES_KHR};
    rt_feat.rayTracingPipeline = VK_TRUE;
    rt_feat.pNext = &as_feat;
    VkPhysicalDeviceFeatures2 features2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};
    features2.pNext = &rt_feat;

    // Properties
    as_props.pNext = nullptr;
    rt_props.pNext = &as_props;
    VkPhysicalDeviceProperties2 props2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
    props2.pNext = &rt_props;
    vkGetPhysicalDeviceProperties2(physical, &props2);

    uint32_t qcount = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &qcount, nullptr);
    std::vector<VkQueueFamilyProperties> qprops(qcount);
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &qcount, qprops.data());
    queue_family = UINT32_MAX;
    for (uint32_t i = 0; i < qcount; ++i) {
      if (qprops[i].queueFlags & (VK_QUEUE_COMPUTE_BIT | VK_QUEUE_GRAPHICS_BIT)) {
        queue_family = i;
        break;
      }
    }
    if (queue_family == UINT32_MAX) {
      throw std::runtime_error("Vulkan: no compute/graphics queue family");
    }

    const float prio = 1.0f;
    VkDeviceQueueCreateInfo qci{};
    qci.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qci.queueFamilyIndex = queue_family;
    qci.queueCount = 1;
    qci.pQueuePriorities = &prio;

    const char *dev_exts[] = {
        VK_KHR_ACCELERATION_STRUCTURE_EXTENSION_NAME,
        VK_KHR_RAY_TRACING_PIPELINE_EXTENSION_NAME,
        VK_KHR_DEFERRED_HOST_OPERATIONS_EXTENSION_NAME,
        VK_KHR_BUFFER_DEVICE_ADDRESS_EXTENSION_NAME,
        VK_KHR_SPIRV_1_4_EXTENSION_NAME,
        VK_KHR_SHADER_FLOAT_CONTROLS_EXTENSION_NAME,
        VK_EXT_DESCRIPTOR_INDEXING_EXTENSION_NAME,
    };

    VkDeviceCreateInfo dci{};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    dci.pNext = &features2;
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &qci;
    dci.enabledExtensionCount = static_cast<uint32_t>(std::size(dev_exts));
    dci.ppEnabledExtensionNames = dev_exts;
    VK_CHECK(vkCreateDevice(physical, &dci, nullptr, &device));
    vkGetDeviceQueue(device, queue_family, 0, &queue);
    load_rt_dispatch(device, instance, rt);

    VkCommandPoolCreateInfo pci{};
    pci.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pci.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    pci.queueFamilyIndex = queue_family;
    VK_CHECK(vkCreateCommandPool(device, &pci, nullptr, &cmd_pool));
  }

  uint32_t find_memory_type(uint32_t type_bits, VkMemoryPropertyFlags props) const {
    VkPhysicalDeviceMemoryProperties mem{};
    vkGetPhysicalDeviceMemoryProperties(physical, &mem);
    for (uint32_t i = 0; i < mem.memoryTypeCount; ++i) {
      if ((type_bits & (1u << i)) && (mem.memoryTypes[i].propertyFlags & props) == props) {
        return i;
      }
    }
    throw std::runtime_error("Vulkan: no matching memory type");
  }

  Buffer create_buffer(VkDeviceSize size, VkBufferUsageFlags usage, VkMemoryPropertyFlags mem_props,
                       bool map = false) {
    Buffer b;
    b.size = size;
    VkBufferCreateInfo bi{};
    bi.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bi.size = size;
    bi.usage = usage;
    bi.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    VK_CHECK(vkCreateBuffer(device, &bi, nullptr, &b.buffer));

    VkMemoryRequirements req{};
    vkGetBufferMemoryRequirements(device, b.buffer, &req);

    VkMemoryAllocateFlagsInfo flags_info{};
    flags_info.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO;
    if (usage & VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT) {
      flags_info.flags = VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT;
    }

    VkMemoryAllocateInfo ai{};
    ai.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    ai.pNext = (flags_info.flags != 0) ? &flags_info : nullptr;
    ai.allocationSize = req.size;
    ai.memoryTypeIndex = find_memory_type(req.memoryTypeBits, mem_props);
    VK_CHECK(vkAllocateMemory(device, &ai, nullptr, &b.memory));
    VK_CHECK(vkBindBufferMemory(device, b.buffer, b.memory, 0));

    if (usage & VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT) {
      VkBufferDeviceAddressInfo dai{};
      dai.sType = VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO;
      dai.buffer = b.buffer;
      b.address = rt.vkGetBufferDeviceAddress(device, &dai);
    }
    if (map) {
      VK_CHECK(vkMapMemory(device, b.memory, 0, size, 0, &b.mapped));
    }
    return b;
  }

  void destroy_buffer(Buffer &b) {
    if (b.mapped) {
      vkUnmapMemory(device, b.memory);
      b.mapped = nullptr;
    }
    if (b.buffer) {
      vkDestroyBuffer(device, b.buffer, nullptr);
      b.buffer = VK_NULL_HANDLE;
    }
    if (b.memory) {
      vkFreeMemory(device, b.memory, nullptr);
      b.memory = VK_NULL_HANDLE;
    }
    b.address = 0;
    b.size = 0;
  }

  void upload(Buffer &dst, const void *src, size_t bytes) {
    Buffer staging = create_buffer(bytes, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                                   VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                       VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                                   true);
    std::memcpy(staging.mapped, src, bytes);
    with_commands([&](VkCommandBuffer cmd) {
      VkBufferCopy copy{};
      copy.size = bytes;
      vkCmdCopyBuffer(cmd, staging.buffer, dst.buffer, 1, &copy);
    });
    destroy_buffer(staging);
  }

  template <typename Fn> void with_commands(Fn &&fn) {
    VkCommandBufferAllocateInfo ai{};
    ai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    ai.commandPool = cmd_pool;
    ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    ai.commandBufferCount = 1;
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    VK_CHECK(vkAllocateCommandBuffers(device, &ai, &cmd));

    VkCommandBufferBeginInfo bi{};
    bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    VK_CHECK(vkBeginCommandBuffer(cmd, &bi));
    fn(cmd);
    VK_CHECK(vkEndCommandBuffer(cmd));

    VkSubmitInfo si{};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cmd;
    VK_CHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    VK_CHECK(vkQueueWaitIdle(queue));
    vkFreeCommandBuffers(device, cmd_pool, 1, &cmd);
  }

  Image create_storage_image(uint32_t w, uint32_t h) {
    Image img;
    img.width = w;
    img.height = h;
    VkImageCreateInfo ii{};
    ii.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    ii.imageType = VK_IMAGE_TYPE_2D;
    ii.format = VK_FORMAT_R32G32B32A32_SFLOAT;
    ii.extent = {w, h, 1};
    ii.mipLevels = 1;
    ii.arrayLayers = 1;
    ii.samples = VK_SAMPLE_COUNT_1_BIT;
    ii.tiling = VK_IMAGE_TILING_OPTIMAL;
    ii.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
               VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    ii.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    ii.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    VK_CHECK(vkCreateImage(device, &ii, nullptr, &img.image));

    VkMemoryRequirements req{};
    vkGetImageMemoryRequirements(device, img.image, &req);
    VkMemoryAllocateInfo ai{};
    ai.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    ai.allocationSize = req.size;
    ai.memoryTypeIndex = find_memory_type(req.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    VK_CHECK(vkAllocateMemory(device, &ai, nullptr, &img.memory));
    VK_CHECK(vkBindImageMemory(device, img.image, img.memory, 0));

    VkImageViewCreateInfo vi{};
    vi.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    vi.image = img.image;
    vi.viewType = VK_IMAGE_VIEW_TYPE_2D;
    vi.format = VK_FORMAT_R32G32B32A32_SFLOAT;
    vi.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    vi.subresourceRange.levelCount = 1;
    vi.subresourceRange.layerCount = 1;
    VK_CHECK(vkCreateImageView(device, &vi, nullptr, &img.view));

    with_commands([&](VkCommandBuffer cmd) {
      VkImageMemoryBarrier bar{};
      bar.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
      bar.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
      bar.newLayout = VK_IMAGE_LAYOUT_GENERAL;
      bar.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
      bar.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
      bar.image = img.image;
      bar.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
      bar.subresourceRange.levelCount = 1;
      bar.subresourceRange.layerCount = 1;
      bar.srcAccessMask = 0;
      bar.dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_SHADER_READ_BIT;
      vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                           VK_PIPELINE_STAGE_RAY_TRACING_SHADER_BIT_KHR, 0, 0, nullptr, 0, nullptr,
                           1, &bar);
    });
    return img;
  }

  void destroy_image(Image &img) {
    if (img.view) {
      vkDestroyImageView(device, img.view, nullptr);
      img.view = VK_NULL_HANDLE;
    }
    if (img.image) {
      vkDestroyImage(device, img.image, nullptr);
      img.image = VK_NULL_HANDLE;
    }
    if (img.memory) {
      vkFreeMemory(device, img.memory, nullptr);
      img.memory = VK_NULL_HANDLE;
    }
  }

  void destroy_as(AccelerationStructure &as) {
    if (as.handle) {
      rt.vkDestroyAccelerationStructureKHR(device, as.handle, nullptr);
      as.handle = VK_NULL_HANDLE;
    }
    destroy_buffer(as.buffer);
    as.address = 0;
  }

  AccelerationStructure build_blas(const Buffer &vertex_buf, uint32_t vertex_count,
                                   const Buffer &index_buf, uint32_t index_count) {
    const uint32_t prim_count = index_count / 3;

    VkAccelerationStructureGeometryTrianglesDataKHR tri{};
    tri.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_TRIANGLES_DATA_KHR;
    tri.vertexFormat = VK_FORMAT_R32G32B32_SFLOAT;
    tri.vertexData.deviceAddress = vertex_buf.address;
    tri.vertexStride = sizeof(float) * 3;
    tri.maxVertex = vertex_count - 1;
    tri.indexType = VK_INDEX_TYPE_UINT32;
    tri.indexData.deviceAddress = index_buf.address;

    VkAccelerationStructureGeometryKHR geometry{};
    geometry.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_KHR;
    geometry.geometryType = VK_GEOMETRY_TYPE_TRIANGLES_KHR;
    // Non-opaque so shadow anyhit can skip glass (radiance rays use Opaque flag).
    geometry.flags = 0;
    geometry.geometry.triangles = tri;

    VkAccelerationStructureBuildGeometryInfoKHR build_info{};
    build_info.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_GEOMETRY_INFO_KHR;
    build_info.type = VK_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL_KHR;
    build_info.flags = VK_BUILD_ACCELERATION_STRUCTURE_PREFER_FAST_TRACE_BIT_KHR;
    build_info.mode = VK_BUILD_ACCELERATION_STRUCTURE_MODE_BUILD_KHR;
    build_info.geometryCount = 1;
    build_info.pGeometries = &geometry;

    VkAccelerationStructureBuildSizesInfoKHR sizes{
        VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_SIZES_INFO_KHR};
    rt.vkGetAccelerationStructureBuildSizesKHR(device, VK_ACCELERATION_STRUCTURE_BUILD_TYPE_DEVICE_KHR,
                                               &build_info, &prim_count, &sizes);

    AccelerationStructure blas;
    blas.buffer = create_buffer(sizes.accelerationStructureSize,
                                VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_STORAGE_BIT_KHR |
                                    VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    VkAccelerationStructureCreateInfoKHR asci{};
    asci.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_CREATE_INFO_KHR;
    asci.buffer = blas.buffer.buffer;
    asci.size = sizes.accelerationStructureSize;
    asci.type = VK_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL_KHR;
    VK_CHECK(rt.vkCreateAccelerationStructureKHR(device, &asci, nullptr, &blas.handle));

    Buffer scratch = create_buffer(sizes.buildScratchSize,
                                   VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                       VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                   VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    build_info.dstAccelerationStructure = blas.handle;
    build_info.scratchData.deviceAddress = scratch.address;

    VkAccelerationStructureBuildRangeInfoKHR range{};
    range.primitiveCount = prim_count;
    const VkAccelerationStructureBuildRangeInfoKHR *ranges[] = {&range};

    with_commands([&](VkCommandBuffer cmd) {
      rt.vkCmdBuildAccelerationStructuresKHR(cmd, 1, &build_info, ranges);
    });
    destroy_buffer(scratch);

    VkAccelerationStructureDeviceAddressInfoKHR dai{};
    dai.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_DEVICE_ADDRESS_INFO_KHR;
    dai.accelerationStructure = blas.handle;
    blas.address = rt.vkGetAccelerationStructureDeviceAddressKHR(device, &dai);
    return blas;
  }

  AccelerationStructure build_tlas(const AccelerationStructure &blas) {
    VkTransformMatrixKHR transform{};
    // Identity 3x4 row-major
    transform.matrix[0][0] = 1.f;
    transform.matrix[1][1] = 1.f;
    transform.matrix[2][2] = 1.f;

    VkAccelerationStructureInstanceKHR inst{};
    inst.transform = transform;
    inst.instanceCustomIndex = 0;
    inst.mask = 0xFF;
    inst.instanceShaderBindingTableRecordOffset = 0;
    inst.flags = VK_GEOMETRY_INSTANCE_TRIANGLE_FACING_CULL_DISABLE_BIT_KHR;
    inst.accelerationStructureReference = blas.address;

    Buffer inst_buf = create_buffer(sizeof(inst),
                                    VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT_KHR |
                                        VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT |
                                        VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                                    VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    upload(inst_buf, &inst, sizeof(inst));

    VkAccelerationStructureGeometryInstancesDataKHR instances{};
    instances.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_INSTANCES_DATA_KHR;
    instances.arrayOfPointers = VK_FALSE;
    instances.data.deviceAddress = inst_buf.address;

    VkAccelerationStructureGeometryKHR geometry{};
    geometry.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_KHR;
    geometry.geometryType = VK_GEOMETRY_TYPE_INSTANCES_KHR;
    geometry.geometry.instances = instances;

    VkAccelerationStructureBuildGeometryInfoKHR build_info{};
    build_info.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_GEOMETRY_INFO_KHR;
    build_info.type = VK_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL_KHR;
    build_info.flags = VK_BUILD_ACCELERATION_STRUCTURE_PREFER_FAST_TRACE_BIT_KHR;
    build_info.mode = VK_BUILD_ACCELERATION_STRUCTURE_MODE_BUILD_KHR;
    build_info.geometryCount = 1;
    build_info.pGeometries = &geometry;

    const uint32_t prim_count = 1;
    VkAccelerationStructureBuildSizesInfoKHR sizes{
        VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_SIZES_INFO_KHR};
    rt.vkGetAccelerationStructureBuildSizesKHR(device, VK_ACCELERATION_STRUCTURE_BUILD_TYPE_DEVICE_KHR,
                                               &build_info, &prim_count, &sizes);

    AccelerationStructure tlas;
    tlas.buffer = create_buffer(sizes.accelerationStructureSize,
                                VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_STORAGE_BIT_KHR |
                                    VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    VkAccelerationStructureCreateInfoKHR asci{};
    asci.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_CREATE_INFO_KHR;
    asci.buffer = tlas.buffer.buffer;
    asci.size = sizes.accelerationStructureSize;
    asci.type = VK_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL_KHR;
    VK_CHECK(rt.vkCreateAccelerationStructureKHR(device, &asci, nullptr, &tlas.handle));

    Buffer scratch = create_buffer(sizes.buildScratchSize,
                                   VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                       VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                   VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    build_info.dstAccelerationStructure = tlas.handle;
    build_info.scratchData.deviceAddress = scratch.address;

    VkAccelerationStructureBuildRangeInfoKHR range{};
    range.primitiveCount = prim_count;
    const VkAccelerationStructureBuildRangeInfoKHR *ranges[] = {&range};
    with_commands([&](VkCommandBuffer cmd) {
      rt.vkCmdBuildAccelerationStructuresKHR(cmd, 1, &build_info, ranges);
    });
    destroy_buffer(scratch);
    destroy_buffer(inst_buf);

    VkAccelerationStructureDeviceAddressInfoKHR dai{};
    dai.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_DEVICE_ADDRESS_INFO_KHR;
    dai.accelerationStructure = tlas.handle;
    tlas.address = rt.vkGetAccelerationStructureDeviceAddressKHR(device, &dai);
    return tlas;
  }

  VkShaderModule load_shader(const std::string &path) {
    auto code = read_binary(path);
    VkShaderModuleCreateInfo ci{};
    ci.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
    ci.codeSize = code.size();
    ci.pCode = reinterpret_cast<const uint32_t *>(code.data());
    VkShaderModule mod = VK_NULL_HANDLE;
    VK_CHECK(vkCreateShaderModule(device, &ci, nullptr, &mod));
    return mod;
  }

  void create_pipeline() {
    // Descriptor set: AS, image, params, verts, idx, mats, mat_ids, lights, spots
    const VkShaderStageFlags rt_stages =
        VK_SHADER_STAGE_RAYGEN_BIT_KHR | VK_SHADER_STAGE_CLOSEST_HIT_BIT_KHR |
        VK_SHADER_STAGE_MISS_BIT_KHR | VK_SHADER_STAGE_ANY_HIT_BIT_KHR;
    std::array<VkDescriptorSetLayoutBinding, 9> bindings{};
    bindings[0].binding = 0;
    bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR;
    bindings[0].descriptorCount = 1;
    bindings[0].stageFlags = rt_stages;
    bindings[1].binding = 1;
    bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
    bindings[1].descriptorCount = 1;
    bindings[1].stageFlags = VK_SHADER_STAGE_RAYGEN_BIT_KHR;
    for (uint32_t i = 2; i < 9; ++i) {
      bindings[i].binding = i;
      bindings[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
      bindings[i].descriptorCount = 1;
      bindings[i].stageFlags = rt_stages;
    }

    VkDescriptorSetLayoutCreateInfo dslci{};
    dslci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    dslci.bindingCount = static_cast<uint32_t>(bindings.size());
    dslci.pBindings = bindings.data();
    VK_CHECK(vkCreateDescriptorSetLayout(device, &dslci, nullptr, &desc_layout));

    VkPipelineLayoutCreateInfo plci{};
    plci.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    plci.setLayoutCount = 1;
    plci.pSetLayouts = &desc_layout;
    VK_CHECK(vkCreatePipelineLayout(device, &plci, nullptr, &pipeline_layout));

    VkShaderModule rgen = load_shader(find_spv("path_trace.rgen.spv"));
    VkShaderModule rmiss = load_shader(find_spv("path_trace.rmiss.spv"));
    VkShaderModule rmiss_shadow = load_shader(find_spv("path_trace_shadow.rmiss.spv"));
    VkShaderModule rchit = load_shader(find_spv("path_trace.rchit.spv"));
    VkShaderModule rahit = load_shader(find_spv("path_trace.rahit.spv"));

    std::array<VkPipelineShaderStageCreateInfo, 5> stages{};
    stages[0].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_RAYGEN_BIT_KHR;
    stages[0].module = rgen;
    stages[0].pName = "main";
    stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[1].stage = VK_SHADER_STAGE_MISS_BIT_KHR;
    stages[1].module = rmiss;
    stages[1].pName = "main";
    stages[2].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[2].stage = VK_SHADER_STAGE_MISS_BIT_KHR;
    stages[2].module = rmiss_shadow;
    stages[2].pName = "main";
    stages[3].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[3].stage = VK_SHADER_STAGE_CLOSEST_HIT_BIT_KHR;
    stages[3].module = rchit;
    stages[3].pName = "main";
    stages[4].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[4].stage = VK_SHADER_STAGE_ANY_HIT_BIT_KHR;
    stages[4].module = rahit;
    stages[4].pName = "main";

    // Groups: 0=rgen, 1=miss radiance, 2=miss shadow, 3=hitgroup chit+ahit
    std::array<VkRayTracingShaderGroupCreateInfoKHR, 4> groups{};
    for (auto &g : groups) {
      g.sType = VK_STRUCTURE_TYPE_RAY_TRACING_SHADER_GROUP_CREATE_INFO_KHR;
      g.generalShader = VK_SHADER_UNUSED_KHR;
      g.closestHitShader = VK_SHADER_UNUSED_KHR;
      g.anyHitShader = VK_SHADER_UNUSED_KHR;
      g.intersectionShader = VK_SHADER_UNUSED_KHR;
    }
    groups[0].type = VK_RAY_TRACING_SHADER_GROUP_TYPE_GENERAL_KHR;
    groups[0].generalShader = 0;
    groups[1].type = VK_RAY_TRACING_SHADER_GROUP_TYPE_GENERAL_KHR;
    groups[1].generalShader = 1;
    groups[2].type = VK_RAY_TRACING_SHADER_GROUP_TYPE_GENERAL_KHR;
    groups[2].generalShader = 2;
    groups[3].type = VK_RAY_TRACING_SHADER_GROUP_TYPE_TRIANGLES_HIT_GROUP_KHR;
    groups[3].closestHitShader = 3;
    groups[3].anyHitShader = 4;

    VkRayTracingPipelineCreateInfoKHR pci{};
    pci.sType = VK_STRUCTURE_TYPE_RAY_TRACING_PIPELINE_CREATE_INFO_KHR;
    pci.stageCount = static_cast<uint32_t>(stages.size());
    pci.pStages = stages.data();
    pci.groupCount = static_cast<uint32_t>(groups.size());
    pci.pGroups = groups.data();
    pci.maxPipelineRayRecursionDepth = 2;
    pci.layout = pipeline_layout;
    VK_CHECK(rt.vkCreateRayTracingPipelinesKHR(device, VK_NULL_HANDLE, VK_NULL_HANDLE, 1, &pci,
                                               nullptr, &pipeline));

    vkDestroyShaderModule(device, rgen, nullptr);
    vkDestroyShaderModule(device, rmiss, nullptr);
    vkDestroyShaderModule(device, rmiss_shadow, nullptr);
    vkDestroyShaderModule(device, rchit, nullptr);
    vkDestroyShaderModule(device, rahit, nullptr);

    // SBT
    const uint32_t handle_size = rt_props.shaderGroupHandleSize;
    const uint32_t handle_align = rt_props.shaderGroupHandleAlignment;
    const uint32_t base_align = rt_props.shaderGroupBaseAlignment;
    auto align_up = [](uint32_t v, uint32_t a) { return (v + a - 1u) & ~(a - 1u); };
    const uint32_t handle_size_aligned = align_up(handle_size, handle_align);

    const uint32_t group_count = 4;
    std::vector<uint8_t> handles(group_count * handle_size);
    VK_CHECK(rt.vkGetRayTracingShaderGroupHandlesKHR(device, pipeline, 0, group_count,
                                                     handles.size(), handles.data()));

    const uint32_t rgen_stride = align_up(handle_size_aligned, base_align);
    const uint32_t miss_stride = handle_size_aligned;
    const uint32_t hit_stride = handle_size_aligned;
    const uint32_t miss_count = 2;
    const uint32_t hit_count = 1;
    const uint32_t rgen_size = rgen_stride;
    const uint32_t miss_size = miss_count * miss_stride;
    const uint32_t hit_size = hit_count * hit_stride;
    const uint32_t sbt_size = rgen_size + miss_size + hit_size;

    sbt_buffer =
        create_buffer(sbt_size,
                      VK_BUFFER_USAGE_SHADER_BINDING_TABLE_BIT_KHR |
                          VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                      VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                      true);
    auto *dst = static_cast<uint8_t *>(sbt_buffer.mapped);
    std::memset(dst, 0, sbt_size);
    // rgen group 0
    std::memcpy(dst, handles.data() + 0 * handle_size, handle_size);
    // miss groups 1,2
    std::memcpy(dst + rgen_size, handles.data() + 1 * handle_size, handle_size);
    std::memcpy(dst + rgen_size + miss_stride, handles.data() + 2 * handle_size, handle_size);
    // hit group 3
    std::memcpy(dst + rgen_size + miss_size, handles.data() + 3 * handle_size, handle_size);

    sbt_rgen.deviceAddress = sbt_buffer.address;
    sbt_rgen.stride = rgen_stride;
    sbt_rgen.size = rgen_size;
    sbt_miss.deviceAddress = sbt_buffer.address + rgen_size;
    sbt_miss.stride = miss_stride;
    sbt_miss.size = miss_size;
    sbt_hit.deviceAddress = sbt_buffer.address + rgen_size + miss_size;
    sbt_hit.stride = hit_stride;
    sbt_hit.size = hit_size;
    sbt_callable = {};

    // Descriptor pool
    std::array<VkDescriptorPoolSize, 3> pool_sizes{};
    pool_sizes[0] = {VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR, 1};
    pool_sizes[1] = {VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1};
    pool_sizes[2] = {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 7};
    VkDescriptorPoolCreateInfo dpci{};
    dpci.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    dpci.maxSets = 1;
    dpci.poolSizeCount = static_cast<uint32_t>(pool_sizes.size());
    dpci.pPoolSizes = pool_sizes.data();
    VK_CHECK(vkCreateDescriptorPool(device, &dpci, nullptr, &desc_pool));

    VkDescriptorSetAllocateInfo dsai{};
    dsai.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    dsai.descriptorPool = desc_pool;
    dsai.descriptorSetCount = 1;
    dsai.pSetLayouts = &desc_layout;
    VK_CHECK(vkAllocateDescriptorSets(device, &dsai, &desc_set));
  }

  void update_descriptors(const AccelerationStructure &tlas, const Image &accum,
                          const Buffer &params_buf, const Buffer &vertex_buf,
                          const Buffer &index_buf, const Buffer &mat_buf, const Buffer &mat_id_buf,
                          const Buffer &light_buf, const Buffer &spot_buf) {
    VkWriteDescriptorSetAccelerationStructureKHR as_info{};
    as_info.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET_ACCELERATION_STRUCTURE_KHR;
    as_info.accelerationStructureCount = 1;
    as_info.pAccelerationStructures = &tlas.handle;

    std::array<VkWriteDescriptorSet, 9> writes{};
    writes[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[0].pNext = &as_info;
    writes[0].dstSet = desc_set;
    writes[0].dstBinding = 0;
    writes[0].descriptorCount = 1;
    writes[0].descriptorType = VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR;

    VkDescriptorImageInfo img_info{};
    img_info.imageView = accum.view;
    img_info.imageLayout = VK_IMAGE_LAYOUT_GENERAL;
    writes[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[1].dstSet = desc_set;
    writes[1].dstBinding = 1;
    writes[1].descriptorCount = 1;
    writes[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
    writes[1].pImageInfo = &img_info;

    std::array<VkDescriptorBufferInfo, 7> bis{};
    const Buffer *bufs[7] = {&params_buf, &vertex_buf, &index_buf, &mat_buf,
                             &mat_id_buf, &light_buf,  &spot_buf};
    for (uint32_t i = 0; i < 7; ++i) {
      bis[i].buffer = bufs[i]->buffer;
      bis[i].offset = 0;
      bis[i].range = VK_WHOLE_SIZE;
      writes[i + 2].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
      writes[i + 2].dstSet = desc_set;
      writes[i + 2].dstBinding = i + 2;
      writes[i + 2].descriptorCount = 1;
      writes[i + 2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
      writes[i + 2].pBufferInfo = &bis[i];
    }
    vkUpdateDescriptorSets(device, static_cast<uint32_t>(writes.size()), writes.data(), 0, nullptr);
  }

  void clear_image(const Image &img) {
    with_commands([&](VkCommandBuffer cmd) {
      VkClearColorValue clear{};
      clear.float32[0] = clear.float32[1] = clear.float32[2] = clear.float32[3] = 0.f;
      VkImageSubresourceRange range{};
      range.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
      range.levelCount = 1;
      range.layerCount = 1;
      vkCmdClearColorImage(cmd, img.image, VK_IMAGE_LAYOUT_GENERAL, &clear, 1, &range);
    });
  }

  void trace(uint32_t width, uint32_t height) {
    with_commands([&](VkCommandBuffer cmd) {
      vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_RAY_TRACING_KHR, pipeline);
      vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_RAY_TRACING_KHR, pipeline_layout, 0, 1,
                              &desc_set, 0, nullptr);
      rt.vkCmdTraceRaysKHR(cmd, &sbt_rgen, &sbt_miss, &sbt_hit, &sbt_callable, width, height, 1);
    });
  }

  std::vector<float> download_rgb(const Image &img) {
    const VkDeviceSize row_bytes = static_cast<VkDeviceSize>(img.width) * 4 * sizeof(float);
    const VkDeviceSize size = row_bytes * img.height;
    Buffer staging =
        create_buffer(size, VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                      VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                      true);
    with_commands([&](VkCommandBuffer cmd) {
      VkBufferImageCopy region{};
      region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
      region.imageSubresource.layerCount = 1;
      region.imageExtent = {img.width, img.height, 1};
      vkCmdCopyImageToBuffer(cmd, img.image, VK_IMAGE_LAYOUT_GENERAL, staging.buffer, 1, &region);
    });
    std::vector<float> rgba(static_cast<size_t>(img.width) * img.height * 4);
    std::memcpy(rgba.data(), staging.mapped, static_cast<size_t>(size));
    destroy_buffer(staging);

    std::vector<float> rgb(static_cast<size_t>(img.width) * img.height * 3);
    for (uint32_t y = 0; y < img.height; ++y) {
      for (uint32_t x = 0; x < img.width; ++x) {
        const size_t i = (static_cast<size_t>(y) * img.width + x);
        rgb[i * 3 + 0] = rgba[i * 4 + 0];
        rgb[i * 3 + 1] = rgba[i * 4 + 1];
        rgb[i * 3 + 2] = rgba[i * 4 + 2];
      }
    }
    return rgb;
  }

  void destroy() {
    if (device) {
      vkDeviceWaitIdle(device);
    }
    destroy_buffer(sbt_buffer);
    if (pipeline) {
      vkDestroyPipeline(device, pipeline, nullptr);
      pipeline = VK_NULL_HANDLE;
    }
    if (pipeline_layout) {
      vkDestroyPipelineLayout(device, pipeline_layout, nullptr);
      pipeline_layout = VK_NULL_HANDLE;
    }
    if (desc_pool) {
      vkDestroyDescriptorPool(device, desc_pool, nullptr);
      desc_pool = VK_NULL_HANDLE;
    }
    if (desc_layout) {
      vkDestroyDescriptorSetLayout(device, desc_layout, nullptr);
      desc_layout = VK_NULL_HANDLE;
    }
    if (cmd_pool) {
      vkDestroyCommandPool(device, cmd_pool, nullptr);
      cmd_pool = VK_NULL_HANDLE;
    }
    if (device) {
      vkDestroyDevice(device, nullptr);
      device = VK_NULL_HANDLE;
    }
    if (instance) {
      vkDestroyInstance(instance, nullptr);
      instance = VK_NULL_HANDLE;
    }
  }

  ~VulkanRT() { destroy(); }
};

CameraGPUHost make_camera_gpu(const Camera &cam) {
  float3 w = normalize(cam.lookat - cam.eye);
  float3 u = normalize(cross(w, cam.up));
  float3 v = cross(u, w);
  const float tan_half = std::tan(cam.fov_y_deg * 0.5f * static_cast<float>(M_PI) / 180.0f);
  v = v * tan_half;
  u = u * tan_half * cam.aspect;

  CameraGPUHost g{};
  set3(g.eye, cam.eye);
  set3(g.U, u);
  set3(g.V, v);
  set3(g.W, w);
  g.lens_radius = cam.aperture * 0.5f;
  g.focus_dist = cam.focus_dist > 0.0f ? cam.focus_dist : length(cam.lookat - cam.eye);
  return g;
}

void merge_scene_geometry(const Scene &scene, std::vector<float> &vertices,
                          std::vector<uint32_t> &indices, std::vector<int32_t> &mat_ids) {
  vertices.clear();
  indices.clear();
  mat_ids.clear();

  auto append_mesh = [&](const Mesh &mesh_in, const Pose *pose) {
    Mesh mesh = mesh_in;
    if (pose) {
      mesh = apply_pose_to_mesh(mesh, *pose);
    }
    const uint32_t base = static_cast<uint32_t>(vertices.size() / 3);
    for (const float3 &p : mesh.vertices) {
      vertices.push_back(p.x);
      vertices.push_back(p.y);
      vertices.push_back(p.z);
    }
    for (size_t t = 0; t < mesh.indices.size(); ++t) {
      const int3 &tri = mesh.indices[t];
      indices.push_back(base + static_cast<uint32_t>(tri.x));
      indices.push_back(base + static_cast<uint32_t>(tri.y));
      indices.push_back(base + static_cast<uint32_t>(tri.z));
      int mid = 0;
      if (!mesh.material_ids.empty()) {
        mid = mesh.material_ids[std::min(t, mesh.material_ids.size() - 1)];
      }
      mat_ids.push_back(mid);
    }
  };

  if (!scene.instances.empty()) {
    for (const SceneInstance &inst : scene.instances) {
      if (inst.mesh_index < 0 || inst.mesh_index >= static_cast<int>(scene.meshes.size())) {
        continue;
      }
      append_mesh(scene.meshes[static_cast<size_t>(inst.mesh_index)], &inst.pose);
    }
  } else {
    for (const Mesh &m : scene.meshes) {
      append_mesh(m, nullptr);
    }
  }
}

} // namespace

void render_vulkan(const Scene &scene, const Camera &camera, const RenderConfig &config) {
  if (config.width <= 0 || config.height <= 0) {
    throw std::runtime_error("Vulkan backend: invalid resolution");
  }
  if (scene.meshes.empty()) {
    throw std::runtime_error("Vulkan backend: scene has no meshes");
  }
  if (scene.materials.empty()) {
    throw std::runtime_error("Vulkan backend: scene has no materials");
  }

  std::cout << "Backend: vulkan (Phase 2a path tracer: GGX + spot NEE + glass shadow skip)\n";
  VulkanRT ctx;
  ctx.init();
  ctx.create_pipeline();

  // Geometry
  std::vector<float> vertices;
  std::vector<uint32_t> indices;
  std::vector<int32_t> mat_ids;
  merge_scene_geometry(scene, vertices, indices, mat_ids);
  if (indices.empty()) {
    throw std::runtime_error("Vulkan backend: no triangles after merge");
  }

  const uint32_t vertex_count = static_cast<uint32_t>(vertices.size() / 3);
  const uint32_t index_count = static_cast<uint32_t>(indices.size());
  std::cout << "Geometry: " << vertex_count << " verts, " << (index_count / 3) << " tris, "
            << scene.materials.size() << " materials, " << scene.lights.size() << " lights\n";

  auto usage_storage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                       VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT |
                       VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT_KHR;

  Buffer vertex_buf = ctx.create_buffer(vertices.size() * sizeof(float), usage_storage,
                                        VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
  ctx.upload(vertex_buf, vertices.data(), vertices.size() * sizeof(float));

  Buffer index_buf = ctx.create_buffer(indices.size() * sizeof(uint32_t), usage_storage,
                                       VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
  ctx.upload(index_buf, indices.data(), indices.size() * sizeof(uint32_t));

  Buffer mat_id_buf = ctx.create_buffer(mat_ids.size() * sizeof(int32_t),
                                        VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                            VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                                            VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                        VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
  ctx.upload(mat_id_buf, mat_ids.data(), mat_ids.size() * sizeof(int32_t));

  std::vector<MaterialGPUHost> mats(scene.materials.size());
  for (size_t i = 0; i < scene.materials.size(); ++i) {
    const Material &m = scene.materials[i];
    set3(mats[i].base_color, m.base_color);
    mats[i].metallic = m.metallic;
    mats[i].roughness = m.roughness;
    mats[i].transmission = m.transmission;
    mats[i].ior = m.ior;
    set3(mats[i].emission, m.emission);
    set3(mats[i].absorption, m.absorption);
    mats[i].flags = m.flags;
  }
  Buffer mat_buf = ctx.create_buffer(mats.size() * sizeof(MaterialGPUHost),
                                     VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                         VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                                         VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                     VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
  ctx.upload(mat_buf, mats.data(), mats.size() * sizeof(MaterialGPUHost));

  std::vector<QuadLightHost> lights(std::max<size_t>(scene.lights.size(), 1));
  if (scene.lights.empty()) {
    std::memset(lights.data(), 0, sizeof(QuadLightHost));
  } else {
    lights.resize(scene.lights.size());
    for (size_t i = 0; i < scene.lights.size(); ++i) {
      const QuadLight &L = scene.lights[i];
      set3(lights[i].corner, L.corner);
      set3(lights[i].u, L.u);
      set3(lights[i].v, L.v);
      set3(lights[i].emission, L.emission);
      lights[i].inv_area = L.inv_area;
      lights[i].use_mis = L.use_mis;
    }
  }
  Buffer light_buf = ctx.create_buffer(lights.size() * sizeof(QuadLightHost),
                                       VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                           VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                                           VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                       VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
  ctx.upload(light_buf, lights.data(), lights.size() * sizeof(QuadLightHost));

  std::vector<SpotLightHost> spots(std::max<size_t>(scene.spot_lights.size(), 1));
  if (scene.spot_lights.empty()) {
    std::memset(spots.data(), 0, sizeof(SpotLightHost));
  } else {
    spots.resize(scene.spot_lights.size());
    for (size_t i = 0; i < scene.spot_lights.size(); ++i) {
      const SpotLight &S = scene.spot_lights[i];
      set3(spots[i].position, S.position);
      set3(spots[i].direction, S.direction);
      set3(spots[i].emission, S.emission);
      spots[i].cos_inner = S.cos_inner;
      spots[i].cos_outer = S.cos_outer;
    }
  }
  Buffer spot_buf = ctx.create_buffer(spots.size() * sizeof(SpotLightHost),
                                      VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                          VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                                          VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                      VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
  ctx.upload(spot_buf, spots.data(), spots.size() * sizeof(SpotLightHost));

  AccelerationStructure blas = ctx.build_blas(vertex_buf, vertex_count, index_buf, index_count);
  AccelerationStructure tlas = ctx.build_tlas(blas);

  Image accum = ctx.create_storage_image(static_cast<uint32_t>(config.width),
                                         static_cast<uint32_t>(config.height));
  ctx.clear_image(accum);

  Buffer params_buf = ctx.create_buffer(sizeof(VulkanLaunchParams),
                                        VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                                            VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                                            VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
                                        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                            VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                                        true);

  VulkanLaunchParams lp{};
  lp.tlas = tlas.address;
  lp.width = config.width;
  lp.height = config.height;
  lp.samples_per_launch = std::max(1, config.samples_per_launch);
  lp.max_depth = std::max(1, config.max_depth);
  lp.material_count = static_cast<int32_t>(scene.materials.size());
  lp.light_count = static_cast<int32_t>(scene.lights.size());
  lp.spot_count = static_cast<int32_t>(scene.spot_lights.size());
  lp.enable_nee = config.enable_nee ? 1 : 0;
  set3(lp.background_top, scene.background_top);
  set3(lp.background_bottom, scene.background_bottom);
  lp.camera = make_camera_gpu(camera);

  ctx.update_descriptors(tlas, accum, params_buf, vertex_buf, index_buf, mat_buf, mat_id_buf,
                         light_buf, spot_buf);

  const int spp = std::max(1, config.spp);
  const int spl = lp.samples_per_launch;
  const auto t0 = std::chrono::steady_clock::now();
  for (int sample = 0; sample < spp; sample += spl) {
    const int batch = std::min(spl, spp - sample);
    lp.sample_index = sample;
    lp.samples_per_launch = batch;
    std::memcpy(params_buf.mapped, &lp, sizeof(lp));
    ctx.trace(static_cast<uint32_t>(config.width), static_cast<uint32_t>(config.height));
    if ((sample / spl) % 16 == 0 || sample + batch >= spp) {
      std::cout << "  spp " << (sample + batch) << "/" << spp << "\r" << std::flush;
    }
  }
  std::cout << "\n";
  const auto t1 = std::chrono::steady_clock::now();
  const double sec = std::chrono::duration<double>(t1 - t0).count();
  std::cout << "Trace time: " << sec << " s (" << (spp / sec) << " spp/s)\n";

  std::vector<float> rgb = ctx.download_rgb(accum);
  write_avif_hdr_pq(config.output_path, config.width, config.height, rgb.data(), 100.0f);
  std::cout << "Wrote " << config.output_path << " (HDR AVIF PQ, vulkan path tracer)\n";

  ctx.destroy_as(tlas);
  ctx.destroy_as(blas);
  ctx.destroy_image(accum);
  ctx.destroy_buffer(params_buf);
  ctx.destroy_buffer(vertex_buf);
  ctx.destroy_buffer(index_buf);
  ctx.destroy_buffer(mat_buf);
  ctx.destroy_buffer(mat_id_buf);
  ctx.destroy_buffer(light_buf);
  ctx.destroy_buffer(spot_buf);
}

#else // !LUMENCORE_HAS_VULKAN

void render_vulkan(const Scene &, const Camera &, const RenderConfig &) {
  throw std::runtime_error(
      "Vulkan backend not available in this build. "
      "Configure with -DLUMENCORE_ENABLE_VULKAN=ON and install Vulkan headers/loader.");
}

#endif

} // namespace nrtx
