#version 460
#extension GL_GOOGLE_include_directive : enable
#extension GL_EXT_ray_tracing : require
#extension GL_EXT_scalar_block_layout : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require

#include "bindings.glsl"

layout(location = 0) rayPayloadInEXT HitPayload payload;

void main() {
  payload.radiance = sample_env_equirect(gl_WorldRayDirectionEXT);
  payload.emission = vec3(0.0);
  payload.hit = 0;
  payload.t_hit = -1.0;
}
