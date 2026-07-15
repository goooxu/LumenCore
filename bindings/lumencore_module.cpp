#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "nrtx/nrtx.h"

#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace py = pybind11;
using namespace nrtx;

namespace {

float3 to_float3(const py::handle &obj) {
  if (py::isinstance<py::tuple>(obj) || py::isinstance<py::list>(obj)) {
    const py::sequence seq = py::reinterpret_borrow<py::sequence>(obj);
    if (seq.size() != 3) {
      throw std::invalid_argument("Vec3 expects 3 components");
    }
    return make_float3(py::cast<float>(seq[0]), py::cast<float>(seq[1]), py::cast<float>(seq[2]));
  }
  // Allow objects with x,y,z attributes (our Vec3)
  if (py::hasattr(obj, "x") && py::hasattr(obj, "y") && py::hasattr(obj, "z")) {
    return make_float3(py::cast<float>(obj.attr("x")), py::cast<float>(obj.attr("y")),
                       py::cast<float>(obj.attr("z")));
  }
  throw std::invalid_argument("Expected Vec3 or (x, y, z)");
}

py::tuple from_float3(const float3 &v) { return py::make_tuple(v.x, v.y, v.z); }

struct Vec3 {
  float x = 0, y = 0, z = 0;
  Vec3() = default;
  Vec3(float x_, float y_, float z_) : x(x_), y(y_), z(z_) {}
  explicit Vec3(const float3 &v) : x(v.x), y(v.y), z(v.z) {}
  float3 to_cuda() const { return make_float3(x, y, z); }
};

Material make_material(const py::object &base_color, float metallic, float roughness,
                       float transmission, float ior, const py::object &emission) {
  Material m;
  m.base_color = to_float3(base_color);
  m.metallic = metallic;
  m.roughness = roughness;
  m.transmission = transmission;
  m.ior = ior;
  m.emission = to_float3(emission);
  return m;
}

} // namespace

PYBIND11_MODULE(lumencore, m) {
  m.doc() = "LumenCore OptiX path tracer Python API";

  py::class_<Vec3>(m, "Vec3")
      .def(py::init<>())
      .def(py::init<float, float, float>(), py::arg("x"), py::arg("y"), py::arg("z"))
      .def(py::init([](const py::sequence &seq) {
             if (seq.size() != 3) {
               throw std::invalid_argument("Vec3 expects 3 components");
             }
             return Vec3(py::cast<float>(seq[0]), py::cast<float>(seq[1]), py::cast<float>(seq[2]));
           }),
           py::arg("xyz"))
      .def_readwrite("x", &Vec3::x)
      .def_readwrite("y", &Vec3::y)
      .def_readwrite("z", &Vec3::z)
      .def("__repr__",
           [](const Vec3 &v) {
             return "Vec3(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ", " +
                    std::to_string(v.z) + ")";
           })
      .def("__iter__", [](const Vec3 &v) { return py::iter(py::make_tuple(v.x, v.y, v.z)); });

  py::class_<Material>(m, "Material")
      .def(py::init([](const py::object &base_color, float metallic, float roughness,
                       float transmission, float ior, const py::object &emission) {
             return make_material(base_color, metallic, roughness, transmission, ior, emission);
           }),
           py::arg("base_color") = py::make_tuple(0.8f, 0.8f, 0.8f), py::arg("metallic") = 0.0f,
           py::arg("roughness") = 0.5f, py::arg("transmission") = 0.0f, py::arg("ior") = 1.5f,
           py::arg("emission") = py::make_tuple(0.0f, 0.0f, 0.0f))
      .def_property(
          "base_color", [](const Material &mat) { return from_float3(mat.base_color); },
          [](Material &mat, const py::object &v) { mat.base_color = to_float3(v); })
      .def_readwrite("metallic", &Material::metallic)
      .def_readwrite("roughness", &Material::roughness)
      .def_readwrite("transmission", &Material::transmission)
      .def_readwrite("ior", &Material::ior)
      .def_property(
          "emission", [](const Material &mat) { return from_float3(mat.emission); },
          [](Material &mat, const py::object &v) { mat.emission = to_float3(v); });

  py::class_<Camera>(m, "Camera")
      .def(py::init([](const py::object &eye, const py::object &lookat, const py::object &up,
                       float fov_y_deg, float aspect, float aperture, float focus_dist) {
             Camera c;
             c.eye = to_float3(eye);
             c.lookat = to_float3(lookat);
             c.up = to_float3(up);
             c.fov_y_deg = fov_y_deg;
             c.aspect = aspect;
             c.aperture = aperture;
             c.focus_dist = focus_dist;
             return c;
           }),
           py::arg("eye") = py::make_tuple(0.0f, 1.0f, 3.0f),
           py::arg("lookat") = py::make_tuple(0.0f, 1.0f, 0.0f),
           py::arg("up") = py::make_tuple(0.0f, 1.0f, 0.0f), py::arg("fov_y_deg") = 40.0f,
           py::arg("aspect") = 1.0f, py::arg("aperture") = 0.0f, py::arg("focus_dist") = 0.0f)
      .def_property(
          "eye", [](const Camera &c) { return from_float3(c.eye); },
          [](Camera &c, const py::object &v) { c.eye = to_float3(v); })
      .def_property(
          "lookat", [](const Camera &c) { return from_float3(c.lookat); },
          [](Camera &c, const py::object &v) { c.lookat = to_float3(v); })
      .def_property(
          "up", [](const Camera &c) { return from_float3(c.up); },
          [](Camera &c, const py::object &v) { c.up = to_float3(v); })
      .def_readwrite("fov_y_deg", &Camera::fov_y_deg)
      .def_readwrite("aspect", &Camera::aspect)
      .def_readwrite("aperture", &Camera::aperture)
      .def_readwrite("focus_dist", &Camera::focus_dist);

  py::class_<RenderConfig>(m, "RenderConfig")
      .def(py::init<>())
      .def(py::init([](int width, int height, int spp, int samples_per_launch, int max_depth,
                       bool denoise, bool enable_nee, const std::string &output_path) {
             RenderConfig c;
             c.width = width;
             c.height = height;
             c.spp = spp;
             c.samples_per_launch = samples_per_launch;
             c.max_depth = max_depth;
             c.denoise = denoise;
             c.enable_nee = enable_nee;
             c.output_path = output_path;
             return c;
           }),
           py::arg("width") = 1024, py::arg("height") = 1024, py::arg("spp") = 256,
           py::arg("samples_per_launch") = 1, py::arg("max_depth") = 16, py::arg("denoise") = true,
           py::arg("enable_nee") = true, py::arg("output_path") = "out.png")
      .def_readwrite("width", &RenderConfig::width)
      .def_readwrite("height", &RenderConfig::height)
      .def_readwrite("spp", &RenderConfig::spp)
      .def_readwrite("samples_per_launch", &RenderConfig::samples_per_launch)
      .def_readwrite("max_depth", &RenderConfig::max_depth)
      .def_readwrite("denoise", &RenderConfig::denoise)
      .def_readwrite("enable_nee", &RenderConfig::enable_nee)
      .def_readwrite("output_path", &RenderConfig::output_path);

  py::class_<Mesh>(m, "Mesh").def(py::init<>());

  py::class_<Scene>(m, "Scene")
      .def(py::init<>())
      .def("add_material", &Scene::add_material, py::arg("material"))
      .def("add_mesh", [](Scene &s, Mesh mesh) { s.add_mesh(std::move(mesh)); }, py::arg("mesh"))
      .def(
          "add_quad_light",
          [](Scene &s, const py::object &corner, const py::object &u, const py::object &v,
             const py::object &emission) {
            s.add_quad_light(to_float3(corner), to_float3(u), to_float3(v), to_float3(emission));
          },
          py::arg("corner"), py::arg("u"), py::arg("v"), py::arg("emission"))
      .def_property(
          "background_top", [](const Scene &s) { return from_float3(s.background_top); },
          [](Scene &s, const py::object &v) { s.background_top = to_float3(v); })
      .def_property(
          "background_bottom", [](const Scene &s) { return from_float3(s.background_bottom); },
          [](Scene &s, const py::object &v) { s.background_bottom = to_float3(v); });

  py::class_<Renderer>(m, "Renderer")
      .def(py::init<>())
      .def("render", &Renderer::render, py::arg("scene"), py::arg("camera"), py::arg("config"));

  m.def(
      "make_quad",
      [](const py::object &corner, const py::object &u, const py::object &v, int material_id) {
        return make_quad(to_float3(corner), to_float3(u), to_float3(v), material_id);
      },
      py::arg("corner"), py::arg("u"), py::arg("v"), py::arg("material_id"));

  m.def(
      "make_box",
      [](const py::object &min_p, const py::object &max_p, int material_id) {
        return make_box(to_float3(min_p), to_float3(max_p), material_id);
      },
      py::arg("min_p"), py::arg("max_p"), py::arg("material_id"));

  m.def(
      "make_uv_sphere",
      [](const py::object &center, float radius, int material_id, int slices, int stacks) {
        return make_uv_sphere(to_float3(center), radius, material_id, slices, stacks);
      },
      py::arg("center"), py::arg("radius"), py::arg("material_id"), py::arg("slices") = 48,
      py::arg("stacks") = 24);

  m.def(
      "load_obj",
      [](const std::string &path, int default_material_id) {
        return load_obj(path, default_material_id);
      },
      py::arg("path"), py::arg("default_material_id"));

  m.def(
      "load_obj",
      [](const std::string &path, const std::unordered_map<std::string, int> &materials_by_name,
         int fallback_material_id) {
        return load_obj(path, materials_by_name, fallback_material_id);
      },
      py::arg("path"), py::arg("materials_by_name"), py::arg("fallback_material_id"));

  m.def(
      "transform_mesh",
      [](const Mesh &input, const py::object &translate, const py::object &scale,
         const py::object &rotate_xyz_radians) {
        return transform_mesh(input, to_float3(translate), to_float3(scale),
                              to_float3(rotate_xyz_radians));
      },
      py::arg("input"), py::arg("translate"), py::arg("scale"),
      py::arg("rotate_xyz_radians") = py::make_tuple(0.0f, 0.0f, 0.0f));
}
