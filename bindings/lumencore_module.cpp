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
                       float transmission, float ior, const py::object &emission, int albedo_tex,
                       const py::object &absorption, int normal_tex) {
  Material m;
  m.base_color = to_float3(base_color);
  m.metallic = metallic;
  m.roughness = roughness;
  m.transmission = transmission;
  m.ior = ior;
  m.emission = to_float3(emission);
  m.albedo_tex = albedo_tex;
  m.normal_tex = normal_tex;
  m.absorption = to_float3(absorption);
  return m;
}

} // namespace

PYBIND11_MODULE(lumencore, m) {
  m.doc() = "LumenCore OptiX path tracer + PhysX rigid body Python API";

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
                       float transmission, float ior, const py::object &emission, int albedo_tex,
                       const py::object &absorption, int normal_tex) {
             return make_material(base_color, metallic, roughness, transmission, ior, emission,
                                  albedo_tex, absorption, normal_tex);
           }),
           py::arg("base_color") = py::make_tuple(0.8f, 0.8f, 0.8f), py::arg("metallic") = 0.0f,
           py::arg("roughness") = 0.5f, py::arg("transmission") = 0.0f, py::arg("ior") = 1.5f,
           py::arg("emission") = py::make_tuple(0.0f, 0.0f, 0.0f), py::arg("albedo_tex") = -1,
           py::arg("absorption") = py::make_tuple(0.0f, 0.0f, 0.0f), py::arg("normal_tex") = -1)
      .def_property(
          "base_color", [](const Material &mat) { return from_float3(mat.base_color); },
          [](Material &mat, const py::object &v) { mat.base_color = to_float3(v); })
      .def_readwrite("metallic", &Material::metallic)
      .def_readwrite("roughness", &Material::roughness)
      .def_readwrite("transmission", &Material::transmission)
      .def_readwrite("ior", &Material::ior)
      .def_property(
          "emission", [](const Material &mat) { return from_float3(mat.emission); },
          [](Material &mat, const py::object &v) { mat.emission = to_float3(v); })
      .def_readwrite("albedo_tex", &Material::albedo_tex)
      .def_readwrite("normal_tex", &Material::normal_tex)
      .def_property(
          "absorption", [](const Material &mat) { return from_float3(mat.absorption); },
          [](Material &mat, const py::object &v) { mat.absorption = to_float3(v); });

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
           py::arg("enable_nee") = true, py::arg("output_path") = "out.avif")
      .def_readwrite("width", &RenderConfig::width)
      .def_readwrite("height", &RenderConfig::height)
      .def_readwrite("spp", &RenderConfig::spp)
      .def_readwrite("samples_per_launch", &RenderConfig::samples_per_launch)
      .def_readwrite("max_depth", &RenderConfig::max_depth)
      .def_readwrite("denoise", &RenderConfig::denoise)
      .def_readwrite("enable_nee", &RenderConfig::enable_nee)
      .def_readwrite("output_path", &RenderConfig::output_path);

  py::class_<Mesh>(m, "Mesh").def(py::init<>());

  py::class_<Pose>(m, "Pose")
      .def(py::init<>())
      .def(py::init([](const py::object &position, const py::object &quat) {
             Pose p;
             p.position = to_float3(position);
             const py::sequence q = py::reinterpret_borrow<py::sequence>(quat);
             if (q.size() != 4) {
               throw std::invalid_argument("Pose.quat expects 4 components (x,y,z,w)");
             }
             p.quat = make_float4(py::cast<float>(q[0]), py::cast<float>(q[1]), py::cast<float>(q[2]),
                                  py::cast<float>(q[3]));
             return p;
           }),
           py::arg("position") = py::make_tuple(0.0f, 0.0f, 0.0f),
           py::arg("quat") = py::make_tuple(0.0f, 0.0f, 0.0f, 1.0f))
      .def_property(
          "position", [](const Pose &p) { return from_float3(p.position); },
          [](Pose &p, const py::object &v) { p.position = to_float3(v); })
      .def_property(
          "quat",
          [](const Pose &p) { return py::make_tuple(p.quat.x, p.quat.y, p.quat.z, p.quat.w); },
          [](Pose &p, const py::object &v) {
            const py::sequence q = py::reinterpret_borrow<py::sequence>(v);
            if (q.size() != 4) {
              throw std::invalid_argument("Pose.quat expects 4 components (x,y,z,w)");
            }
            p.quat = make_float4(py::cast<float>(q[0]), py::cast<float>(q[1]), py::cast<float>(q[2]),
                                 py::cast<float>(q[3]));
          });

  py::class_<Scene>(m, "Scene")
      .def(py::init<>())
      .def("add_material", &Scene::add_material, py::arg("material"))
      .def("add_texture", &Scene::add_texture, py::arg("path"))
      .def("load_env_map", &Scene::load_env_map, py::arg("path"))
      .def("clear_env_map", &Scene::clear_env_map)
      .def("add_mesh",
           [](Scene &s, Mesh mesh) { return s.add_mesh(std::move(mesh)); }, py::arg("mesh"),
           "Add a mesh prototype; returns mesh index for add_instance")
      .def("add_instance",
           [](Scene &s, int mesh_index, const Pose &pose) { s.add_instance(mesh_index, pose); },
           py::arg("mesh_index"), py::arg("pose") = Pose{},
           "Instance a prototype mesh with a rigid pose (enables OptiX IAS path)")
      .def(
          "add_quad_light",
          [](Scene &s, const py::object &corner, const py::object &u, const py::object &v,
             const py::object &emission, bool use_mis) {
            s.add_quad_light(to_float3(corner), to_float3(u), to_float3(v), to_float3(emission),
                             use_mis);
          },
          py::arg("corner"), py::arg("u"), py::arg("v"), py::arg("emission"),
          py::arg("use_mis") = false,
          "Area light. use_mis=True when paired with an emissive mesh at the same pose.")
      .def(
          "add_spot_light",
          [](Scene &s, const py::object &position, const py::object &direction,
             const py::object &emission, float angle_deg, float penumbra_deg) {
            s.add_spot_light(to_float3(position), to_float3(direction), to_float3(emission),
                             angle_deg, penumbra_deg);
          },
          py::arg("position"), py::arg("direction"), py::arg("emission"),
          py::arg("angle_deg") = 18.0f, py::arg("penumbra_deg") = 10.0f)
      .def(
          "add_flame_volume",
          [](Scene &s, const py::object &center, const py::object &half_extents,
             const py::object &emission_scale, float density_scale, float absorption,
             float noise_scale, float time, bool add_proxy_light) {
            return s.add_flame_volume(to_float3(center), to_float3(half_extents),
                                      to_float3(emission_scale), density_scale, absorption,
                                      noise_scale, time, add_proxy_light);
          },
          py::arg("center"), py::arg("half_extents"),
          py::arg("emission_scale") = py::make_tuple(120.0f, 48.0f, 8.0f),
          py::arg("density_scale") = 2.8f, py::arg("absorption") = 2.0f,
          py::arg("noise_scale") = 2.4f, py::arg("time") = 0.0f, py::arg("add_proxy_light") = true)
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
      "make_water_surface",
      [](const py::object &center, const py::object &half_extents_xz, float y_base, int material_id,
         int nx, int nz, float time) {
        return make_water_surface(to_float3(center), to_float3(half_extents_xz), y_base, material_id,
                                  nx, nz, time);
      },
      py::arg("center"), py::arg("half_extents_xz"), py::arg("y_base"), py::arg("material_id"),
      py::arg("nx") = 64, py::arg("nz") = 48, py::arg("time") = 0.0f);

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

  py::class_<PhysXWorld>(m, "PhysXWorld")
      .def(py::init<>())
      .def("init", &PhysXWorld::init)
      .def("using_gpu", &PhysXWorld::using_gpu)
      .def("backend", &PhysXWorld::backend)
      .def(
          "add_static_box",
          [](PhysXWorld &w, const py::object &half_extents, const Pose &pose) {
            return w.add_static_box(to_float3(half_extents), pose);
          },
          py::arg("half_extents"), py::arg("pose") = Pose{})
      .def(
          "add_dynamic_box",
          [](PhysXWorld &w, const py::object &half_extents, float density, const Pose &pose) {
            return w.add_dynamic_box(to_float3(half_extents), density, pose);
          },
          py::arg("half_extents"), py::arg("density"), py::arg("pose") = Pose{})
      .def(
          "add_dynamic_sphere",
          [](PhysXWorld &w, float radius, float density, const Pose &pose) {
            return w.add_dynamic_sphere(radius, density, pose);
          },
          py::arg("radius"), py::arg("density"), py::arg("pose") = Pose{})
      .def(
          "set_linear_velocity",
          [](PhysXWorld &w, int actor_id, const py::object &velocity) {
            w.set_linear_velocity(actor_id, to_float3(velocity));
          },
          py::arg("actor_id"), py::arg("velocity"))
      .def(
          "set_angular_velocity",
          [](PhysXWorld &w, int actor_id, const py::object &velocity) {
            w.set_angular_velocity(actor_id, to_float3(velocity));
          },
          py::arg("actor_id"), py::arg("velocity"))
      .def("step", &PhysXWorld::step, py::arg("dt"), py::arg("substeps") = 1)
      .def("get_pose", &PhysXWorld::get_pose, py::arg("actor_id"));

  m.def(
      "apply_pose_to_mesh",
      [](const Mesh &input, const Pose &pose) { return apply_pose_to_mesh(input, pose); },
      py::arg("input"), py::arg("pose"));

  m.def(
      "apply_pose_to_box_mesh",
      [](const py::object &half_extents, const Pose &pose, int material_id) {
        return apply_pose_to_box_mesh(to_float3(half_extents), pose, material_id);
      },
      py::arg("half_extents"), py::arg("pose"), py::arg("material_id"));

  m.def(
      "apply_pose_to_sphere_mesh",
      [](float radius, const Pose &pose, int material_id, int slices, int stacks) {
        return apply_pose_to_sphere_mesh(radius, pose, material_id, slices, stacks);
      },
      py::arg("radius"), py::arg("pose"), py::arg("material_id"), py::arg("slices") = 32,
      py::arg("stacks") = 16);
}
