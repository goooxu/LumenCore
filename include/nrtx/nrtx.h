#pragma once

#include "LaunchParams.h"
#include "nrtx/physx_world.h"
#include "vec.h"

#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace nrtx {

struct Mesh {
  std::vector<float3> vertices;
  std::vector<int3> indices;
  std::vector<int> material_ids;
};

struct Material {
  float3 base_color = make_float3(0.8f, 0.8f, 0.8f);
  float metallic = 0.0f;
  float roughness = 0.5f;
  float transmission = 0.0f;
  float ior = 1.5f;
  float3 emission = make_float3(0.0f, 0.0f, 0.0f);
  int flags = MATERIAL_FLAG_NONE;
  int volume_index = -1;
};

struct Camera {
  float3 eye = make_float3(0.0f, 1.0f, 3.0f);
  float3 lookat = make_float3(0.0f, 1.0f, 0.0f);
  float3 up = make_float3(0.0f, 1.0f, 0.0f);
  float fov_y_deg = 40.0f;
  float aspect = 1.0f;
  float aperture = 0.0f;
  float focus_dist = 0.0f;
};

struct Scene {
  std::vector<Mesh> meshes;
  std::vector<Material> materials;
  std::vector<QuadLight> lights;
  std::vector<FlameVolume> volumes;
  float3 background_top = make_float3(0.6f, 0.7f, 0.9f);
  float3 background_bottom = make_float3(0.15f, 0.15f, 0.2f);

  int add_material(const Material &m) {
    materials.push_back(m);
    return static_cast<int>(materials.size() - 1);
  }

  void add_mesh(Mesh mesh) { meshes.push_back(std::move(mesh)); }

  void add_quad_light(const float3 &corner, const float3 &u, const float3 &v,
                      const float3 &emission) {
    QuadLight light;
    light.corner = corner;
    light.u = u;
    light.v = v;
    light.emission = emission;
    const float area = length(cross(u, v));
    light.inv_area = area > 0.0f ? 1.0f / area : 0.0f;
    light.pad = 0;
    lights.push_back(light);
  }

  // Procedural flame volume: proxy AABB mesh + optional NEE face light at the fire core.
  int add_flame_volume(const float3 &center, const float3 &half_extents,
                       const float3 &emission_scale = make_float3(120.0f, 48.0f, 8.0f),
                       float density_scale = 2.8f, float absorption = 2.0f,
                       float noise_scale = 2.4f, float time = 0.0f, bool add_proxy_light = true);
};

struct RenderConfig {
  int width = 1024;
  int height = 1024;
  int spp = 256;
  int samples_per_launch = 1;
  int max_depth = 16;
  bool denoise = true;
  bool enable_nee = true;
  std::string output_path = "out.png";
};

class Renderer {
public:
  Renderer();
  ~Renderer();

  Renderer(const Renderer &) = delete;
  Renderer &operator=(const Renderer &) = delete;

  void render(const Scene &scene, const Camera &camera, const RenderConfig &config);

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

// Procedural mesh helpers
Mesh make_quad(const float3 &corner, const float3 &u, const float3 &v, int material_id);
Mesh make_box(const float3 &min_p, const float3 &max_p, int material_id);
Mesh make_uv_sphere(const float3 &center, float radius, int material_id, int slices = 48,
                    int stacks = 24);

// Wavefront OBJ loader (triangles / fan-tessellated polygons; optional usemtl)
Mesh load_obj(const std::string &path, int default_material_id);
Mesh load_obj(const std::string &path,
              const std::unordered_map<std::string, int> &materials_by_name,
              int fallback_material_id);

Mesh transform_mesh(const Mesh &input, const float3 &translate, const float3 &scale,
                    const float3 &rotate_xyz_radians = make_float3(0.0f, 0.0f, 0.0f));

// Apply a rigid Pose (quaternion + translation) to mesh vertices (local → world).
Mesh apply_pose_to_mesh(const Mesh &input, const Pose &pose);

// Axis-aligned box centered at origin with the given half-extents, then posed.
Mesh apply_pose_to_box_mesh(const float3 &half_extents, const Pose &pose, int material_id);

// UV sphere centered at origin, then posed.
Mesh apply_pose_to_sphere_mesh(float radius, const Pose &pose, int material_id, int slices = 32,
                               int stacks = 16);

} // namespace nrtx
