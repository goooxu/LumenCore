#pragma once

#include "vec.h"

#include <memory>
#include <string>

namespace nrtx {

struct Pose {
  float3 position = make_float3(0.0f, 0.0f, 0.0f);
  // Quaternion as (x, y, z, w)
  float4 quat = make_float4(0.0f, 0.0f, 0.0f, 1.0f);
};

class PhysXWorld {
public:
  PhysXWorld();
  ~PhysXWorld();

  PhysXWorld(const PhysXWorld &) = delete;
  PhysXWorld &operator=(const PhysXWorld &) = delete;

  // prefer_gpu: attempt GPU rigid bodies + GPU broadphase; falls back to CPU if unavailable.
  void init(bool prefer_gpu = true);

  bool using_gpu() const;
  const std::string &backend() const;

  int add_static_box(const float3 &half_extents, const Pose &pose = Pose{});
  int add_dynamic_box(const float3 &half_extents, float density, const Pose &pose = Pose{});
  int add_dynamic_sphere(float radius, float density, const Pose &pose = Pose{});

  void set_linear_velocity(int actor_id, const float3 &velocity);
  void set_angular_velocity(int actor_id, const float3 &velocity);

  void step(float dt, int substeps = 1);
  Pose get_pose(int actor_id) const;

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace nrtx
