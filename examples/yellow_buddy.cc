#include "nrtx/nrtx.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace nrtx;

static bool file_exists(const std::string &path) {
  std::ifstream in(path);
  return static_cast<bool>(in);
}

static std::string resolve_asset(const std::string &relative) {
  std::vector<std::string> candidates;
  if (const char *env = std::getenv("LUMENCORE_ROOT")) {
    candidates.push_back(std::string(env) + "/" + relative);
  }
  candidates.push_back(relative);
  candidates.push_back("../" + relative);
  candidates.push_back("../../" + relative);
  candidates.push_back("/work/" + relative);
  for (const std::string &path : candidates) {
    if (file_exists(path)) {
      return path;
    }
  }
  return candidates.front();
}

int main(int argc, char **argv) {
  const std::string out = argc > 1 ? argv[1] : "yellow_buddy.png";
  const int spp = argc > 2 ? std::atoi(argv[2]) : 256;
  const bool denoise = argc > 3 ? std::atoi(argv[3]) != 0 : true;

  Scene scene;

  const int yellow =
      scene.add_material({make_float3(0.95f, 0.82f, 0.12f), 0, 0.45f, 0, 1.5f, make_float3(0, 0, 0)});
  const int overalls =
      scene.add_material({make_float3(0.15f, 0.35f, 0.75f), 0, 0.55f, 0, 1.5f, make_float3(0, 0, 0)});
  const int strap =
      scene.add_material({make_float3(0.08f, 0.08f, 0.08f), 0, 0.7f, 0, 1.5f, make_float3(0, 0, 0)});
  const int goggle =
      scene.add_material({make_float3(0.7f, 0.7f, 0.75f), 0.85f, 0.15f, 0, 1.5f, make_float3(0, 0, 0)});
  const int lens =
      scene.add_material({make_float3(0.75f, 0.88f, 0.98f), 0, 0.05f, 0.85f, 1.5f, make_float3(0, 0, 0)});
  const int eye_white =
      scene.add_material({make_float3(0.95f, 0.95f, 0.95f), 0, 0.4f, 0, 1.5f, make_float3(0, 0, 0)});
  const int pupil =
      scene.add_material({make_float3(0.05f, 0.05f, 0.05f), 0, 0.6f, 0, 1.5f, make_float3(0, 0, 0)});
  const int boot =
      scene.add_material({make_float3(0.18f, 0.1f, 0.06f), 0, 0.75f, 0, 1.5f, make_float3(0, 0, 0)});
  const int floor_mat =
      scene.add_material({make_float3(0.55f, 0.55f, 0.58f), 0, 0.85f, 0, 1.5f, make_float3(0, 0, 0)});
  const int wall =
      scene.add_material({make_float3(0.82f, 0.8f, 0.78f), 0, 0.9f, 0, 1.5f, make_float3(0, 0, 0)});
  const int chrome =
      scene.add_material({make_float3(0.95f, 0.95f, 0.98f), 1.0f, 0.05f, 0, 1.5f, make_float3(0, 0, 0)});

  std::unordered_map<std::string, int> mtl_map = {
      {"Yellow", yellow},   {"Overalls", overalls}, {"Strap", strap}, {"Goggle", goggle},
      {"Lens", lens},       {"EyeWhite", eye_white}, {"Pupil", pupil}, {"Boot", boot},
  };

  const std::string obj_path = resolve_asset("assets/models/yellow_buddy.obj");
  try {
    Mesh buddy = load_obj(obj_path, mtl_map, yellow);
    buddy = transform_mesh(buddy, make_float3(0.0f, 0.0f, 0.0f), make_float3(1.0f, 1.0f, 1.0f),
                           make_float3(0.0f, 0.35f, 0.0f));
    scene.add_mesh(std::move(buddy));
    std::cout << "Loaded " << obj_path << "\n";
  } catch (const std::exception &ex) {
    std::cerr << "Failed to load character OBJ (" << obj_path << "): " << ex.what() << "\n";
    return 1;
  }

  scene.add_mesh(make_quad(make_float3(-4, 0, -4), make_float3(8, 0, 0), make_float3(0, 0, 8), floor_mat));
  scene.add_mesh(make_quad(make_float3(-4, 0, -2.2f), make_float3(8, 0, 0), make_float3(0, 4, 0), wall));
  scene.add_mesh(make_uv_sphere(make_float3(-1.35f, 0.35f, 0.8f), 0.35f, chrome));
  scene.add_mesh(make_box(make_float3(1.1f, 0.0f, 0.4f), make_float3(1.7f, 0.7f, 1.0f), overalls));

  const float3 light_corner = make_float3(-1.2f, 3.6f, -0.5f);
  const float3 light_u = make_float3(2.4f, 0, 0);
  const float3 light_v = make_float3(0, 0, 2.0f);
  const int light_mat =
      scene.add_material({make_float3(0, 0, 0), 0, 1, 0, 1.5f, make_float3(18.0f, 17.0f, 15.0f)});
  scene.add_mesh(make_quad(light_corner, light_u, light_v, light_mat));
  scene.add_quad_light(light_corner, light_u, light_v, make_float3(18.0f, 17.0f, 15.0f));

  scene.background_top = make_float3(0.55f, 0.68f, 0.88f);
  scene.background_bottom = make_float3(0.35f, 0.35f, 0.4f);

  Camera camera;
  camera.eye = make_float3(2.6f, 1.55f, 3.4f);
  camera.lookat = make_float3(0.0f, 1.0f, 0.15f);
  camera.fov_y_deg = 35.0f;
  camera.aspect = 16.0f / 9.0f;

  RenderConfig cfg;
  cfg.width = 1280;
  cfg.height = 720;
  cfg.spp = spp;
  cfg.denoise = denoise;
  cfg.output_path = out;

  try {
    Renderer renderer;
    renderer.render(scene, camera, cfg);
  } catch (const std::exception &ex) {
    std::cerr << "Error: " << ex.what() << "\n";
    return 1;
  }
  return 0;
}
