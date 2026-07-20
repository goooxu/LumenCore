#version 460
#extension GL_GOOGLE_include_directive : enable
#extension GL_EXT_ray_tracing : require
#extension GL_EXT_scalar_block_layout : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require

#include "bindings.glsl"

layout(location = 0) rayPayloadInEXT HitPayload payload;
hitAttributeEXT vec2 baryCoord;

void main() {
  int mesh_id = int(gl_InstanceCustomIndexEXT);
  MeshRange range = mesh_ranges[mesh_id];

  const int prim = range.prim_base + gl_PrimitiveID;
  uvec3 li = indices[prim];
  uint i0 = uint(range.vertex_base) + li.x;
  uint i1 = uint(range.vertex_base) + li.y;
  uint i2 = uint(range.vertex_base) + li.z;

  vec3 v0 = vertices[i0];
  vec3 v1 = vertices[i1];
  vec3 v2 = vertices[i2];

  float b1 = baryCoord.x;
  float b2 = baryCoord.y;
  float b0 = 1.0 - b1 - b2;

  vec3 obj_pos = b0 * v0 + b1 * v1 + b2 * v2;
  vec3 ng_obj = normalize(cross(v1 - v0, v2 - v0));

  vec3 n_obj = ng_obj;
  vec3 n0 = normals[i0];
  vec3 n1 = normals[i1];
  vec3 n2 = normals[i2];
  if (dot(n0, n0) + dot(n1, n1) + dot(n2, n2) > 1e-8) {
    n_obj = normalize(b0 * n0 + b1 * n1 + b2 * n2);
  }

  vec2 uv = b0 * texcoords[i0] + b1 * texcoords[i1] + b2 * texcoords[i2];

  int mid = material_ids[prim];
  if (mid < 0 || mid >= params.material_count) {
    mid = 0;
  }
  MaterialGPU mat = materials[mid];

  if (mat.normal_tex >= 0 && mat.normal_tex < params.texture_count) {
    vec3 encoded = sample_albedo_tex(mat.normal_tex, uv);
    vec3 n_ts = encoded * 2.0 - 1.0;
    float nts2 = dot(n_ts, n_ts);
    if (nts2 > 1e-8) {
      n_ts *= inversesqrt(nts2);
      vec4 t0 = tangents[i0];
      vec4 t1 = tangents[i1];
      vec4 t2 = tangents[i2];
      vec3 T = b0 * t0.xyz + b1 * t1.xyz + b2 * t2.xyz;
      T = T - n_obj * dot(n_obj, T);
      float t2len = dot(T, T);
      if (t2len > 1e-10) {
        T *= inversesqrt(t2len);
        float hand = (b0 * t0.w + b1 * t1.w + b2 * t2.w) >= 0.0 ? 1.0 : -1.0;
        vec3 B = cross(n_obj, T) * hand;
        vec3 n_mapped = T * n_ts.x + B * n_ts.y + n_obj * n_ts.z;
        float nlen2 = dot(n_mapped, n_mapped);
        if (nlen2 > 1e-10) {
          n_obj = n_mapped * inversesqrt(nlen2);
        }
      }
    }
  }

  vec3 world_pos = (gl_ObjectToWorldEXT * vec4(obj_pos, 1.0)).xyz;
  vec3 world_n = normalize((gl_ObjectToWorldEXT * vec4(n_obj, 0.0)).xyz);
  vec3 world_ng = normalize((gl_ObjectToWorldEXT * vec4(ng_obj, 0.0)).xyz);

  vec3 base = mat.base_color;
  if (mat.albedo_tex >= 0) {
    base *= sample_albedo_tex(mat.albedo_tex, uv);
  }

  payload.hit = 1;
  payload.hit_pos = world_pos;
  payload.hit_normal = world_n;
  payload.hit_geom_normal = world_ng;
  payload.base_color = base;
  payload.emission = mat.emission;
  payload.absorption = mat.absorption;
  payload.metallic = mat.metallic;
  payload.roughness = mat.roughness;
  payload.transmission = mat.transmission;
  payload.ior = mat.ior;
  payload.t_hit = gl_HitTEXT;
  payload.flags = mat.flags;
  payload.volume_index = mat.volume_index;
  payload.radiance = vec3(0.0);
}
