#version 460
#extension GL_GOOGLE_include_directive : enable
#extension GL_EXT_ray_tracing : require
#extension GL_EXT_scalar_block_layout : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require

#include "common.glsl"

layout(binding = 2, set = 0, scalar) readonly buffer ParamsBuf {
  LaunchParams params;
};

layout(location = 0) rayPayloadInEXT HitPayload payload;

void main() {
  float t = 0.5 * (normalize(gl_WorldRayDirectionEXT).y + 1.0);
  payload.radiance = mix(params.background_bottom, params.background_top, t);
  payload.emission = vec3(0.0);
  payload.hit = 0;
  payload.t_hit = -1.0;
}
