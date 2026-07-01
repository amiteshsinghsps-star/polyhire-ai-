// Vertex shader for constellation trail lines.
// Draws arcing gold lines from the JD core to each candidate node,
// with opacity weighted by the candidate's fusion score.
//
// Attributes:
//   position  — vec3 world-space position along the trail curve
//   aOpacity  — float per-vertex opacity (set via BufferAttribute)
//   aSelected — float (0.0 or 1.0) for highlighting selected nodes

uniform float uTime;
uniform float uPixelRatio;

attribute float aOpacity;
attribute float aSelected;

varying float vOpacity;
varying float vSelected;

void main() {
  vOpacity = aOpacity;
  vSelected = aSelected;

  // Subtle pulse animation on selected trails.
  float pulse = 1.0 + 0.15 * sin(uTime * 2.0) * aSelected;

  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mvPosition;

  // Boost point size for selected nodes.
  gl_PointSize = 4.0 * uPixelRatio * pulse;
}
