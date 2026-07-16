#include "nrtx/nrtx.h"

#include <cmath>
#include <stdexcept>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

namespace nrtx {

int Scene::add_texture(const std::string &path) {
  int w = 0, h = 0, comp = 0;
  unsigned char *data = stbi_load(path.c_str(), &w, &h, &comp, 4);
  if (!data || w <= 0 || h <= 0) {
    throw std::runtime_error("Failed to load texture: " + path);
  }
  Texture2D tex;
  tex.width = w;
  tex.height = h;
  tex.rgba.assign(data, data + static_cast<size_t>(w) * h * 4);
  stbi_image_free(data);
  textures.push_back(std::move(tex));
  return static_cast<int>(textures.size() - 1);
}

namespace {

void ensure_texcoords(Mesh &mesh) {
  if (mesh.texcoords.size() == mesh.vertices.size()) {
    return;
  }
  mesh.texcoords.assign(mesh.vertices.size(), make_float2(0.0f, 0.0f));
}

} // namespace

Mesh make_quad(const float3 &corner, const float3 &u, const float3 &v, int material_id) {
  Mesh mesh;
  mesh.vertices = {corner, corner + u, corner + u + v, corner + v};
  mesh.texcoords = {make_float2(0, 0), make_float2(1, 0), make_float2(1, 1), make_float2(0, 1)};
  mesh.indices = {make_int3(0, 1, 2), make_int3(0, 2, 3)};
  mesh.material_ids = {material_id, material_id};
  return mesh;
}

Mesh make_box(const float3 &min_p, const float3 &max_p, int material_id) {
  const float3 p000 = make_float3(min_p.x, min_p.y, min_p.z);
  const float3 p001 = make_float3(min_p.x, min_p.y, max_p.z);
  const float3 p010 = make_float3(min_p.x, max_p.y, min_p.z);
  const float3 p011 = make_float3(min_p.x, max_p.y, max_p.z);
  const float3 p100 = make_float3(max_p.x, min_p.y, min_p.z);
  const float3 p101 = make_float3(max_p.x, min_p.y, max_p.z);
  const float3 p110 = make_float3(max_p.x, max_p.y, min_p.z);
  const float3 p111 = make_float3(max_p.x, max_p.y, max_p.z);

  Mesh mesh;
  auto add = [&](const float3 &a, const float3 &b, const float3 &c, const float3 &d) {
    const int base = static_cast<int>(mesh.vertices.size());
    mesh.vertices.push_back(a);
    mesh.vertices.push_back(b);
    mesh.vertices.push_back(c);
    mesh.vertices.push_back(d);
    mesh.texcoords.push_back(make_float2(0, 0));
    mesh.texcoords.push_back(make_float2(1, 0));
    mesh.texcoords.push_back(make_float2(1, 1));
    mesh.texcoords.push_back(make_float2(0, 1));
    mesh.indices.push_back(make_int3(base, base + 1, base + 2));
    mesh.indices.push_back(make_int3(base, base + 2, base + 3));
    mesh.material_ids.push_back(material_id);
    mesh.material_ids.push_back(material_id);
  };

  add(p000, p100, p110, p010); // -Z
  add(p001, p011, p111, p101); // +Z
  add(p000, p010, p011, p001); // -X
  add(p100, p101, p111, p110); // +X
  add(p000, p001, p101, p100); // -Y
  add(p010, p110, p111, p011); // +Y
  return mesh;
}

Mesh make_uv_sphere(const float3 &center, float radius, int material_id, int slices, int stacks) {
  Mesh mesh;
  for (int i = 0; i <= stacks; ++i) {
    const float v = static_cast<float>(i) / stacks;
    const float phi = v * 3.14159265f;
    for (int j = 0; j <= slices; ++j) {
      const float u = static_cast<float>(j) / slices;
      const float theta = u * 2.0f * 3.14159265f;
      const float x = std::sin(phi) * std::cos(theta);
      const float y = std::cos(phi);
      const float z = std::sin(phi) * std::sin(theta);
      mesh.vertices.push_back(center + make_float3(x, y, z) * radius);
      mesh.texcoords.push_back(make_float2(u, v));
    }
  }
  for (int i = 0; i < stacks; ++i) {
    for (int j = 0; j < slices; ++j) {
      const int i0 = i * (slices + 1) + j;
      const int i1 = i0 + 1;
      const int i2 = i0 + (slices + 1);
      const int i3 = i2 + 1;
      mesh.indices.push_back(make_int3(i0, i2, i1));
      mesh.indices.push_back(make_int3(i1, i2, i3));
      mesh.material_ids.push_back(material_id);
      mesh.material_ids.push_back(material_id);
    }
  }
  return mesh;
}

namespace {

float3 rotate_by_quat(const float3 &v, const float4 &q) {
  const float3 u = make_float3(q.x, q.y, q.z);
  const float s = q.w;
  const float3 t = cross(u, v) * 2.0f;
  return v + t * s + cross(u, t);
}

} // namespace

Mesh apply_pose_to_mesh(const Mesh &input, const Pose &pose) {
  Mesh out = input;
  ensure_texcoords(out);
  for (float3 &v : out.vertices) {
    v = rotate_by_quat(v, pose.quat) + pose.position;
  }
  return out;
}

Mesh apply_pose_to_box_mesh(const float3 &half_extents, const Pose &pose, int material_id) {
  const float3 min_p = make_float3(-half_extents.x, -half_extents.y, -half_extents.z);
  const float3 max_p = make_float3(half_extents.x, half_extents.y, half_extents.z);
  return apply_pose_to_mesh(make_box(min_p, max_p, material_id), pose);
}

Mesh apply_pose_to_sphere_mesh(float radius, const Pose &pose, int material_id, int slices,
                               int stacks) {
  return apply_pose_to_mesh(make_uv_sphere(make_float3(0.0f, 0.0f, 0.0f), radius, material_id, slices, stacks),
                            pose);
}

int Scene::add_flame_volume(const float3 &center, const float3 &half_extents,
                            const float3 &emission_scale, float density_scale, float absorption,
                            float noise_scale, float time, bool add_proxy_light) {
  FlameVolume vol;
  vol.center = center;
  vol.half_extents = half_extents;
  vol.emission_scale = emission_scale;
  vol.density_scale = density_scale;
  vol.absorption = absorption;
  vol.noise_scale = noise_scale;
  vol.time = time;
  vol.pad = 0;
  const int volume_index = static_cast<int>(volumes.size());
  volumes.push_back(vol);

  Material mat;
  mat.base_color = make_float3(0.0f, 0.0f, 0.0f);
  mat.roughness = 1.0f;
  mat.flags = MATERIAL_FLAG_VOLUME_FLAME;
  mat.volume_index = volume_index;
  const int mat_id = add_material(mat);

  const float3 min_p = center - half_extents;
  const float3 max_p = center + half_extents;
  add_mesh(make_box(min_p, max_p, mat_id));

  if (add_proxy_light) {
    const float3 light_center = make_float3(center.x, center.y - half_extents.y * 0.15f, center.z);
    const float3 u = make_float3(half_extents.x * 0.95f, 0.0f, 0.0f);
    const float3 v = make_float3(0.0f, 0.0f, half_extents.z * 0.95f);
    const float3 corner = light_center - u * 0.5f - v * 0.5f;
    const float flicker = 0.85f + 0.15f * std::sin(time * 7.3f);
    const float3 proxy_emission = emission_scale * (4.5f * flicker);
    add_quad_light(corner, u, v, proxy_emission);
  }
  return volume_index;
}

} // namespace nrtx
