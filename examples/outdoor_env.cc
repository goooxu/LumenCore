#include "nrtx/nrtx.h"

#include <cstdlib>
#include <iostream>
#include <string>

using namespace nrtx;

int main(int argc, char **argv) {
  const std::string out = argc > 1 ? argv[1] : "outdoor_env.png";
  const int spp = argc > 2 ? std::atoi(argv[2]) : 256;
  const bool denoise = argc > 3 ? std::atoi(argv[3]) != 0 : true;

  Scene scene;
  const int grass = scene.add_material({make_float3(0.2f, 0.35f, 0.15f), 0, 0.95f, 0, 1.5f, {}});
  const int stone = scene.add_material({make_float3(0.45f, 0.45f, 0.48f), 0, 0.7f, 0, 1.5f, {}});
  const int chrome = scene.add_material({make_float3(0.95f, 0.95f, 0.98f), 1.0f, 0.02f, 0, 1.5f, {}});
  const int glass = scene.add_material({make_float3(1.0f, 1.0f, 1.0f), 0, 0.0f, 1.0f, 1.5f, {}});
  const int warm = scene.add_material({make_float3(0.85f, 0.45f, 0.2f), 0, 0.4f, 0, 1.5f, {}});

  scene.add_mesh(make_quad(make_float3(-20, 0, -20), make_float3(40, 0, 0), make_float3(0, 0, 40), grass));
  scene.add_mesh(make_box(make_float3(-1.2f, 0, -0.4f), make_float3(-0.3f, 1.6f, 0.5f), stone));
  scene.add_mesh(make_uv_sphere(make_float3(0.8f, 0.6f, 0.2f), 0.6f, chrome));
  scene.add_mesh(make_uv_sphere(make_float3(-0.1f, 0.4f, 1.4f), 0.4f, glass));
  scene.add_mesh(make_uv_sphere(make_float3(1.8f, 0.35f, 1.2f), 0.35f, warm));

  // Soft sun-like distant area light
  const float3 light_corner = make_float3(4.0f, 8.0f, -2.0f);
  const float3 light_u = make_float3(2.5f, 0, 0.5f);
  const float3 light_v = make_float3(0, 0, 2.5f);
  const int light_mat =
      scene.add_material({make_float3(0, 0, 0), 0, 1, 0, 1.5f, make_float3(40.0f, 36.0f, 28.0f)});
  scene.add_mesh(make_quad(light_corner, light_u, light_v, light_mat));
  scene.add_quad_light(light_corner, light_u, light_v, make_float3(40.0f, 36.0f, 28.0f));

  scene.background_top = make_float3(0.45f, 0.65f, 0.95f);
  scene.background_bottom = make_float3(0.75f, 0.8f, 0.85f);

  Camera camera;
  camera.eye = make_float3(-2.8f, 1.8f, 4.2f);
  camera.lookat = make_float3(0.3f, 0.5f, 0.4f);
  camera.fov_y_deg = 40.0f;
  camera.aspect = 16.0f / 9.0f;
  camera.aperture = 0.04f;
  camera.focus_dist = 4.5f;

  RenderConfig cfg;
  cfg.width = 2560;
  cfg.height = 1440;
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
