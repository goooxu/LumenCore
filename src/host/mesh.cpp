#include "nrtx/nrtx.h"

#include <cmath>
#include <stdexcept>

namespace nrtx {

Mesh make_quad(const float3 &corner, const float3 &u, const float3 &v, int material_id) {
  Mesh mesh;
  mesh.vertices = {corner, corner + u, corner + u + v, corner + v};
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

} // namespace nrtx
