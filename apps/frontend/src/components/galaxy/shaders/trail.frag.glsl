// Fragment shader for constellation trail lines.
// Fades from gold (selected / high-score) to muted gridline blue (low-score).

uniform vec3 uColorSelected; // #E8A33D
uniform vec3 uColorDefault;  // #2A2F4D

varying float vOpacity;
varying float vSelected;

void main() {
  // Discard fully transparent fragments.
  if (vOpacity < 0.01) discard;

  vec3 color = mix(uColorDefault, uColorSelected, vSelected);

  // Soft glow effect via distance-from-center.
  float dist = length(gl_PointCoord - vec2(0.5));
  float alpha = smoothstep(0.5, 0.2, dist) * vOpacity;

  gl_FragColor = vec4(color, alpha);
}
