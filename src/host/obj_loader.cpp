#include "nrtx/nrtx.h"

#include <cmath>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace nrtx {
namespace {

std::string trim(const std::string &s) {
  size_t b = 0;
  while (b < s.size() && std::isspace(static_cast<unsigned char>(s[b]))) {
    ++b;
  }
  size_t e = s.size();
  while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1]))) {
    --e;
  }
  return s.substr(b, e - b);
}

int parse_face_index(const std::string &token, int vertex_count) {
  // Formats: i | i/j | i//k | i/j/k  (1-based, negative relative)
  const size_t slash = token.find('/');
  const std::string index_str = slash == std::string::npos ? token : token.substr(0, slash);
  int idx = std::stoi(index_str);
  if (idx < 0) {
    idx = vertex_count + idx + 1;
  }
  if (idx <= 0) {
    throw std::runtime_error("Invalid OBJ face index: " + token);
  }
  return idx - 1;
}

} // namespace

Mesh load_obj(const std::string &path, int default_material_id) {
  return load_obj(path, {}, default_material_id);
}

Mesh load_obj(const std::string &path,
              const std::unordered_map<std::string, int> &materials_by_name,
              int fallback_material_id) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error("Failed to open OBJ: " + path);
  }

  Mesh mesh;
  int current_mat = fallback_material_id;
  std::string line;
  while (std::getline(in, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#') {
      continue;
    }

    std::istringstream ss(line);
    std::string tag;
    ss >> tag;
    if (tag == "v") {
      float x = 0, y = 0, z = 0;
      ss >> x >> y >> z;
      mesh.vertices.push_back(make_float3(x, y, z));
    } else if (tag == "usemtl") {
      std::string name;
      ss >> name;
      const auto it = materials_by_name.find(name);
      current_mat = it != materials_by_name.end() ? it->second : fallback_material_id;
    } else if (tag == "f") {
      std::vector<int> face;
      std::string tok;
      while (ss >> tok) {
        face.push_back(parse_face_index(tok, static_cast<int>(mesh.vertices.size())));
      }
      if (face.size() < 3) {
        continue;
      }
      for (size_t i = 1; i + 1 < face.size(); ++i) {
        mesh.indices.push_back(make_int3(face[0], face[i], face[i + 1]));
        mesh.material_ids.push_back(current_mat);
      }
    }
  }

  if (mesh.vertices.empty() || mesh.indices.empty()) {
    throw std::runtime_error("OBJ contained no triangles: " + path);
  }
  return mesh;
}

Mesh transform_mesh(const Mesh &input, const float3 &translate, const float3 &scale,
                    const float3 &rotate_xyz_radians) {
  Mesh out = input;
  const float cx = std::cos(rotate_xyz_radians.x);
  const float sx = std::sin(rotate_xyz_radians.x);
  const float cy = std::cos(rotate_xyz_radians.y);
  const float sy = std::sin(rotate_xyz_radians.y);
  const float cz = std::cos(rotate_xyz_radians.z);
  const float sz = std::sin(rotate_xyz_radians.z);

  auto rotate = [&](float3 p) {
    // Z * Y * X
    float3 r = p;
    {
      const float y = r.y * cx - r.z * sx;
      const float z = r.y * sx + r.z * cx;
      r.y = y;
      r.z = z;
    }
    {
      const float x = r.x * cy + r.z * sy;
      const float z = -r.x * sy + r.z * cy;
      r.x = x;
      r.z = z;
    }
    {
      const float x = r.x * cz - r.y * sz;
      const float y = r.x * sz + r.y * cz;
      r.x = x;
      r.y = y;
    }
    return r;
  };

  for (float3 &v : out.vertices) {
    v = make_float3(v.x * scale.x, v.y * scale.y, v.z * scale.z);
    v = rotate(v);
    v = v + translate;
  }
  return out;
}

} // namespace nrtx
