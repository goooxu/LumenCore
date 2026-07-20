#version 460
#extension GL_GOOGLE_include_directive : enable
#extension GL_EXT_ray_tracing : require
#extension GL_EXT_scalar_block_layout : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require

#include "common.glsl"

layout(binding = 2, set = 0, scalar) readonly buffer ParamsBuf {
  LaunchParams params;
};

layout(binding = 3, set = 0, scalar) readonly buffer Vertices {
  vec3 vertices[];
};

layout(binding = 4, set = 0, scalar) readonly buffer Indices {
  uvec3 indices[];
};

layout(binding = 5, set = 0, scalar) readonly buffer Materials {
  MaterialGPU materials[];
};

layout(binding = 6, set = 0, scalar) readonly buffer MaterialIds {
  int material_ids[];
};

layout(location = 0) rayPayloadInEXT HitPayload payload;
hitAttributeEXT vec2 baryCoord;

void main() {
  const int prim = gl_PrimitiveID;
  uvec3 idx = indices[prim];
  vec3 v0 = vertices[idx.x];
  vec3 v1 = vertices[idx.y];
  vec3 v2 = vertices[idx.z];

  float b1 = baryCoord.x;
  float b2 = baryCoord.y;
  float b0 = 1.0 - b1 - b2;
  vec3 obj_pos = b0 * v0 + b1 * v1 + b2 * v2;
  vec3 obj_n = normalize(cross(v1 - v0, v2 - v0));

  // Object → world (identity instances for Phase 1 merged GAS; still apply gl_ObjectToWorld)
  vec3 world_pos = (gl_ObjectToWorldEXT * vec4(obj_pos, 1.0)).xyz;
  vec3 world_n = normalize((gl_ObjectToWorldEXT * vec4(obj_n, 0.0)).xyz);

  int mid = material_ids[prim];
  if (mid < 0 || mid >= params.material_count) {
    mid = 0;
  }
  MaterialGPU mat = materials[mid];

  payload.hit = 1;
  payload.hit_pos = world_pos;
  payload.hit_normal = world_n;
  payload.base_color = mat.base_color;
  payload.emission = mat.emission;
  payload.metallic = mat.metallic;
  payload.roughness = mat.roughness;
  payload.transmission = mat.transmission;
  payload.ior = mat.ior;
  payload.t_hit = gl_HitTEXT;
  payload.radiance = vec3(0.0);
}
