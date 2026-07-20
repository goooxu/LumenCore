#version 460
#extension GL_GOOGLE_include_directive : enable
#extension GL_EXT_ray_tracing : require

#include "common.glsl"

layout(location = 1) rayPayloadInEXT ShadowPayload shadow_payload;

void main() {
  // Unoccluded: ray reached the light distance without hitting geometry.
  shadow_payload.visible = 1u;
}
