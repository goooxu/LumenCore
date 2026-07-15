#include "nrtx/nrtx.h"

#include <cstdlib>
#include <iostream>
#include <string>

using namespace nrtx;

int main(int argc, char **argv) {
  const std::string out = argc > 1 ? argv[1] : "materials_ball.png";
  const int spp = argc > 2 ? std::atoi(argv[2]) : 256;
  const bool denoise = argc > 3 ? std::atoi(argv[3]) != 0 : true;

  Scene scene;
  const int ground = scene.add_material({make_float3(0.25f, 0.25f, 0.28f), 0, 0.9f, 0, 1.5f, {}});
  scene.add_mesh(make_quad(make_float3(-4, 0, -4), make_float3(8, 0, 0), make_float3(0, 0, 8), ground));

  const float3 colors[] = {
      make_float3(0.9f, 0.2f, 0.2f), make_float3(0.2f, 0.8f, 0.3f), make_float3(0.2f, 0.4f, 0.95f),
      make_float3(0.95f, 0.85f, 0.2f), make_float3(0.9f, 0.9f, 0.95f), make_float3(0.8f, 0.5f, 0.2f)};

  int idx = 0;
  for (int row = 0; row < 3; ++row) {
    for (int col = 0; col < 4; ++col) {
      Material m;
      m.base_color = colors[idx % 6];
      if (row == 0) {
        m.metallic = 0.0f;
        m.roughness = 0.15f + 0.25f * col;
      } else if (row == 1) {
        m.metallic = 1.0f;
        m.roughness = 0.05f + 0.25f * col;
      } else {
        m.transmission = 1.0f;
        m.ior = 1.1f + 0.2f * col;
        m.roughness = 0.0f;
        m.base_color = make_float3(1.0f, 1.0f, 1.0f);
      }
      const int mid = scene.add_material(m);
      const float x = -1.5f + col * 1.0f;
      const float z = -0.5f + row * 1.0f;
      scene.add_mesh(make_uv_sphere(make_float3(x, 0.35f, z), 0.32f, mid));
      ++idx;
    }
  }

  const float3 light_corner = make_float3(-1.0f, 3.5f, -1.0f);
  const float3 light_u = make_float3(2.0f, 0, 0);
  const float3 light_v = make_float3(0, 0, 2.0f);
  const int light_mat =
      scene.add_material({make_float3(0, 0, 0), 0, 1, 0, 1.5f, make_float3(20.0f, 18.0f, 14.0f)});
  scene.add_mesh(make_quad(light_corner, light_u, light_v, light_mat));
  scene.add_quad_light(light_corner, light_u, light_v, make_float3(20.0f, 18.0f, 14.0f));

  scene.background_top = make_float3(0.55f, 0.65f, 0.85f);
  scene.background_bottom = make_float3(0.2f, 0.2f, 0.25f);

  Camera camera;
  camera.eye = make_float3(0.0f, 2.2f, 4.5f);
  camera.lookat = make_float3(0.0f, 0.4f, 0.3f);
  camera.fov_y_deg = 35.0f;
  camera.aspect = 16.0f / 9.0f;

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
