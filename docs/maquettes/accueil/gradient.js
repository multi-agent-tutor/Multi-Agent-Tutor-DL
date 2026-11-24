// Dégradé vivant (WebGL 1, un seul shader, aucune bibliothèque, aucun réseau).
// Couleurs de la charte D1 : marine, bleu roi, bleu clair, bleu ciel et une lueur jaune du pompon.
// Économe : rendu à résolution réduite (le dégradé est flou par nature), pause hors écran et
// onglet caché, une seule image fixe si le visiteur préfère réduire les animations.

const FRAG = `
precision mediump float;
uniform vec2 r;
uniform float t;
uniform float clair;
const vec3 MARINE = vec3(0.043, 0.102, 0.271);
const vec3 ROI    = vec3(0.145, 0.388, 0.922);
const vec3 CLAIR  = vec3(0.298, 0.541, 0.992);
const vec3 CIEL   = vec3(0.859, 0.918, 0.996);
const vec3 JAUNE  = vec3(0.984, 0.749, 0.141);
float tache(vec2 p, vec2 c, float s) { vec2 d = p - c; return exp(-dot(d, d) / s); }
void main() {
  vec2 uv = gl_FragCoord.xy / r;
  float a = r.x / r.y;
  vec2 p = vec2(uv.x * a, uv.y);
  // Déformation lente du domaine : le dégradé « coule »
  p += 0.07 * vec2(sin(p.y * 3.1 + t * 0.21), cos(p.x * 2.3 - t * 0.17));
  p += 0.04 * vec2(sin(p.y * 7.0 - t * 0.11), sin(p.x * 5.0 + t * 0.13));
  vec3 c = MARINE;
  c = mix(c, ROI,   0.95 * tache(p, vec2(a * (0.78 + 0.10 * sin(t * 0.13)), 0.30 + 0.12 * cos(t * 0.11)), 0.20));
  c = mix(c, CLAIR, 0.85 * tache(p, vec2(a * (0.20 + 0.12 * cos(t * 0.09)), 0.05 + 0.10 * sin(t * 0.15)), 0.14));
  c = mix(c, CIEL,  (0.55 + 0.35 * clair) * tache(p, vec2(a * (0.55 + 0.15 * sin(t * 0.07)), -0.12 + 0.06 * sin(t * 0.19)), 0.10));
  c = mix(c, ROI,   0.60 * tache(p, vec2(a * (0.08 + 0.05 * sin(t * 0.12)), 0.95), 0.12));
  c = mix(c, JAUNE, 0.42 * tache(p, vec2(a * (0.92 + 0.05 * cos(t * 0.23)), 0.88 + 0.06 * sin(t * 0.2)), 0.012));
  // Grain fin : évite les bandes du dégradé sur les écrans 8 bits
  float g = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
  c += (g - 0.5) * 0.025;
  gl_FragColor = vec4(c, 1.0);
}`;

const VERT = "attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }";
const ECHELLE = 0.55;        // part de la résolution : le flou du dégradé masque la différence
const DPR_MAX = 1.5;

export function monterDegrade(canvas, { clair = 0 } = {}) {
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false, powerPreference: "low-power" });
  if (!gl) return; // le fond CSS de repli reste affiché
  const shader = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  };
  const vs = shader(gl.VERTEX_SHADER, VERT), fs = shader(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) return;
  const prog = gl.createProgram();
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const uR = gl.getUniformLocation(prog, "r"), uT = gl.getUniformLocation(prog, "t");
  gl.uniform1f(gl.getUniformLocation(prog, "clair"), clair);

  const fixe = matchMedia("(prefers-reduced-motion: reduce)");
  let visible = true, raf = 0, debut = performance.now() - 12000;

  function taille() {
    const k = Math.min(devicePixelRatio || 1, DPR_MAX) * ECHELLE;
    const w = Math.max(1, Math.round(canvas.clientWidth * k)), h = Math.max(1, Math.round(canvas.clientHeight * k));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; gl.viewport(0, 0, w, h); }
    gl.uniform2f(uR, w, h);
  }
  function dessiner(maintenant) {
    gl.uniform1f(uT, (maintenant - debut) / 1000);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  function boucle(maintenant) {
    dessiner(maintenant);
    raf = visible && !document.hidden && !fixe.matches ? requestAnimationFrame(boucle) : 0;
  }
  function relancer() {
    if (!raf && visible && !document.hidden && !fixe.matches) raf = requestAnimationFrame(boucle);
    if (fixe.matches) dessiner(debut + 20000);
  }
  new ResizeObserver(() => { taille(); if (!raf) dessiner(performance.now()); }).observe(canvas);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; relancer(); }).observe(canvas);
  document.addEventListener("visibilitychange", relancer);
  fixe.addEventListener("change", relancer);
  taille();
  canvas.classList.add("pret");
  relancer();
}
