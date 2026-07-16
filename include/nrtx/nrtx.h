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
  std::vector<float2> texcoords; // parallel to vertices (may be empty → treated as 0,0)
  std::vector<int3> indices;
  std::vector<int> material_ids;
};

struct Texture2D {
  int width = 0;
  int height = 0;
  std::vector<unsigned char> rgba; // width * height * 4
};

struct Material {
  float3 base_color = make_float3(0.8f, 0.8f, 0.8f);
  float metallic = 0.0f;
  float roughness = 0.5f;
  float transmission = 0.0f;
  float ior = 1.5f;
  float3 emission = make_float3(0.0f, 0.0f, 0.0f);
  float3 absorption = make_float3(0.0f, 0.0f, 0.0f); // Beer-Lambert sigma_a
  int flags = MATERIAL_FLAG_NONE;
  int volume_index = -1;
  int albedo_tex = -1; // index into Scene::textures, -1 = solid base_color
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
  std::vector<Texture2D> textures;
  std::vector<QuadLight> lights;
  std::vector<SpotLight> spot_lights;
  std::vector<FlameVolume> volumes;
  float3 background_top = make_float3(0.6f, 0.7f, 0.9f);
  float3 background_bottom = make_float3(0.15f, 0.15f, 0.2f);

  int add_material(const Material &m) {
    materials.push_back(m);
    return static_cast<int>(materials.size() - 1);
  }

  int add_texture(const std::string &path);

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

  void add_spot_light(const float3 &position, const float3 &direction, const float3 &emission,
                      float angle_deg = 18.0f, float penumbra_deg = 10.0f) {
    SpotLight light;
    light.position = position;
    light.direction = normalize(direction);
    light.emission = emission;
    const float deg2rad = 3.14159265f / 180.0f;
    const float inner = fmaxf(0.0f, angle_deg) * deg2rad;
    const float outer = fmaxf(inner, (angle_deg + fmaxf(0.0f, penumbra_deg)) * deg2rad);
    light.cos_inner = cosf(inner);
    light.cos_outer = cosf(outer);
    light.pad = 0.0f;
    spot_lights.push_back(light);
  }

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

Mesh make_quad(const float3 &corner, const float3 &u, const float3 &v, int material_id);
Mesh make_box(const float3 &min_p, const float3 &max_p, int material_id);
Mesh make_uv_sphere(const float3 &center, float radius, int material_id, int slices = 48,
                    int stacks = 24);

Mesh load_obj(const std::string &path, int default_material_id);
Mesh load_obj(const std::string &path,
              const std::unordered_map<std::string, int> &materials_by_name,
              int fallback_material_id);

Mesh transform_mesh(const Mesh &input, const float3 &translate, const float3 &scale,
                    const float3 &rotate_xyz_radians = make_float3(0.0f, 0.0f, 0.0f));

Mesh apply_pose_to_mesh(const Mesh &input, const Pose &pose);
Mesh apply_pose_to_box_mesh(const float3 &half_extents, const Pose &pose, int material_id);
Mesh apply_pose_to_sphere_mesh(float radius, const Pose &pose, int material_id, int slices = 32,
                               int stacks = 16);

} // namespace nrtx
