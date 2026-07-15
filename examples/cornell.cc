#include "nrtx/nrtx.h"

#include <cstdlib>
#include <iostream>
#include <string>

using namespace nrtx;

int main(int argc, char **argv) {
  const std::string out = argc > 1 ? argv[1] : "cornell.png";
  const int spp = argc > 2 ? std::atoi(argv[2]) : 256;
  const bool denoise = argc > 3 ? std::atoi(argv[3]) != 0 : true;

  Scene scene;
  const int white = scene.add_material({make_float3(0.73f, 0.73f, 0.73f), 0, 0.8f, 0, 1.5f, {}});
  const int red = scene.add_material({make_float3(0.65f, 0.05f, 0.05f), 0, 0.8f, 0, 1.5f, {}});
  const int green = scene.add_material({make_float3(0.12f, 0.45f, 0.15f), 0, 0.8f, 0, 1.5f, {}});
  const int light_mat = scene.add_material(
      {make_float3(0.0f, 0.0f, 0.0f), 0, 1.0f, 0, 1.5f, make_float3(15.0f, 15.0f, 12.0f)});
  const int glass = scene.add_material({make_float3(1.0f, 1.0f, 1.0f), 0, 0.0f, 1.0f, 1.5f, {}});
  const int metal = scene.add_material({make_float3(0.95f, 0.85f, 0.55f), 1.0f, 0.05f, 0, 1.5f, {}});

  // Room
  scene.add_mesh(make_quad(make_float3(0, 0, 0), make_float3(1, 0, 0), make_float3(0, 0, 1), white)); // floor
  scene.add_mesh(make_quad(make_float3(0, 1, 0), make_float3(1, 0, 0), make_float3(0, 0, 1), white)); // ceiling
  scene.add_mesh(make_quad(make_float3(0, 0, 1), make_float3(1, 0, 0), make_float3(0, 1, 0), white)); // back
  scene.add_mesh(make_quad(make_float3(0, 0, 0), make_float3(0, 0, 1), make_float3(0, 1, 0), red));   // left
  scene.add_mesh(make_quad(make_float3(1, 0, 0), make_float3(0, 0, 1), make_float3(0, 1, 0), green)); // right

  // Ceiling light (geometry + NEE)
  const float3 light_corner = make_float3(0.35f, 0.999f, 0.35f);
  const float3 light_u = make_float3(0.3f, 0, 0);
  const float3 light_v = make_float3(0, 0, 0.3f);
  scene.add_mesh(make_quad(light_corner, light_u, light_v, light_mat));
  scene.add_quad_light(light_corner, light_u, light_v, make_float3(15.0f, 15.0f, 12.0f));

  scene.add_mesh(make_box(make_float3(0.15f, 0.0f, 0.55f), make_float3(0.4f, 0.4f, 0.8f), white));
  scene.add_mesh(make_uv_sphere(make_float3(0.7f, 0.2f, 0.35f), 0.2f, glass));
  scene.add_mesh(make_uv_sphere(make_float3(0.35f, 0.15f, 0.3f), 0.15f, metal));

  scene.background_top = make_float3(0.0f, 0.0f, 0.0f);
  scene.background_bottom = make_float3(0.0f, 0.0f, 0.0f);

  Camera camera;
  camera.eye = make_float3(0.5f, 0.5f, -1.35f);
  camera.lookat = make_float3(0.5f, 0.5f, 0.5f);
  camera.fov_y_deg = 40.0f;
  camera.aspect = 1.0f;

  RenderConfig cfg;
  cfg.width = 800;
  cfg.height = 800;
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
