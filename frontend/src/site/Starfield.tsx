/** Ambient WebGL backdrop for the hero: an eight-fold geometric lattice (khatam) drawn by a fragment shader,
 *  with a soft light that follows the pointer like a lens. Pure geometry — no text, no letters, ever.
 *
 *  Performance contract:
 *  - this module is a separate lazy chunk, imported after first paint + idle (see Home.tsx);
 *  - only mounted on capable devices (hooks.capableDevice) and never with prefers-reduced-motion;
 *  - DPR capped at 1.5, renders at ≤ 30 fps, pauses when off-screen or the tab is hidden;
 *  - fails silent (no WebGL → nothing rendered, the CSS gradient underneath stays). */

import { useEffect, useRef } from "react";

const VERT = `attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}`;

// 8-fold star lattice: distance to a rotated-square pair (khatam) on a square grid, plus a moving light.
const FRAG = `precision mediump float;
uniform vec2 r;uniform float t;uniform vec2 m;uniform float dark;
float sq(vec2 p,float s){vec2 d=abs(p)-s;return max(d.x,d.y);}
mat2 rot(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}
float star(vec2 p){float a=sq(p,.30);float b=sq(rot(.7853982)*p,.30);return min(abs(a),abs(b));}
void main(){
  vec2 uv=(gl_FragCoord.xy-.5*r)/r.y;
  vec2 g=uv*3.2+vec2(t*.012,0.);
  vec2 id=floor(g);vec2 f=fract(g)-.5;
  float d=star(f);
  float d2=star(fract(g+.5)-.5);
  float line=smoothstep(.018,.0,d)+.55*smoothstep(.012,.0,d2);
  vec2 mm=(m-.5*r)/r.y;
  float lens=exp(-6.5*length(uv-mm));
  float breath=.5+.5*sin(t*.35+dot(id,vec2(.7,1.3)));
  vec3 navy=mix(vec3(.957,.961,1.),vec3(.043,.059,.165),dark);
  vec3 violet=vec3(.38,.31,.92);vec3 teal=vec3(.18,.95,.76);
  vec3 ink=mix(violet,teal,lens);
  float a=line*(.08+.30*lens+.05*breath)*(1.-.35*length(uv));
  gl_FragColor=vec4(mix(navy,ink,a),1.);
}`;

export default function Starfield({ dark }: { dark: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const darkRef = useRef(dark);
  darkRef.current = dark;

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const gl = c.getContext("webgl", { antialias: false, alpha: false, powerPreference: "low-power", preserveDrawingBuffer: false });
    if (!gl) return;
    const sh = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return s;
    };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const uR = gl.getUniformLocation(prog, "r");
    const uT = gl.getUniformLocation(prog, "t");
    const uM = gl.getUniformLocation(prog, "m");
    const uD = gl.getUniformLocation(prog, "dark");

    const dpr = Math.min(1.5, window.devicePixelRatio || 1);
    let w = 0;
    let h = 0;
    const size = () => {
      const b = c.getBoundingClientRect();
      w = Math.max(1, Math.floor(b.width * dpr));
      h = Math.max(1, Math.floor(b.height * dpr));
      c.width = w;
      c.height = h;
      gl.viewport(0, 0, w, h);
    };
    size();
    const ro = new ResizeObserver(size);
    ro.observe(c);

    // pointer → lens light (eased); default drifts slowly
    let mx = 0.62;
    let my = 0.55;
    let tx = mx;
    let ty = my;
    let pointer = false;
    const onMove = (e: PointerEvent) => {
      const b = c.getBoundingClientRect();
      tx = (e.clientX - b.left) / b.width;
      ty = 1 - (e.clientY - b.top) / b.height;
      pointer = true;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    let visible = true;
    const io = new IntersectionObserver(([en]) => (visible = !!en?.isIntersecting));
    io.observe(c);

    let raf = 0;
    let last = 0;
    let dk = darkRef.current ? 1 : 0;
    const t0 = performance.now();
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible || document.hidden || now - last < 33) return;
      last = now;
      const time = (now - t0) / 1000;
      if (!pointer) {
        tx = 0.5 + 0.22 * Math.cos(time * 0.18);
        ty = 0.55 + 0.12 * Math.sin(time * 0.23);
      }
      mx += (tx - mx) * 0.08;
      my += (ty - my) * 0.08;
      dk += ((darkRef.current ? 1 : 0) - dk) * 0.1;
      gl.uniform2f(uR, w, h);
      gl.uniform1f(uT, time);
      gl.uniform2f(uM, mx * w, my * h);
      gl.uniform1f(uD, dk);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      c.dataset["ready"] = "1";
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("pointermove", onMove);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, []);

  return <canvas ref={ref} className="starfield" aria-hidden="true" />;
}
