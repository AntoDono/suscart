import { useEffect, useRef } from 'react';
import './IridescenceBackground.css';

function IridescenceBackground() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const uniformsRef = useRef<{
    uTime?: WebGLUniformLocation | null;
    uColor?: WebGLUniformLocation | null;
    uResolution?: WebGLUniformLocation | null;
    uMouse?: WebGLUniformLocation | null;
    uAmplitude?: WebGLUniformLocation | null;
    uSpeed?: WebGLUniformLocation | null;
  }>({});
  const accumTimeRef = useRef(0);
  const lastTimeRef = useRef(performance.now());

  useEffect(() => {
    if (!containerRef.current) return;

    const canvas = document.createElement('canvas');
    canvas.style.position = 'absolute';
    canvas.style.inset = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    containerRef.current.appendChild(canvas);
    canvasRef.current = canvas;

    const gl = canvas.getContext('webgl', { antialias: false, alpha: false });
    if (!gl) return;
    glRef.current = gl;

    const vertexShader = `
attribute vec2 uv;
attribute vec2 position;

varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

    const fragmentShader = `
precision highp float;

uniform float uTime;
uniform vec3 uColor;
uniform vec3 uResolution;
uniform vec2 uMouse;
uniform float uAmplitude;
uniform float uSpeed;

varying vec2 vUv;

void main() {
  float mr = min(uResolution.x, uResolution.y);
  vec2 uv = (vUv.xy * 2.0 - 1.0) * uResolution.xy / mr;

  uv += (uMouse - vec2(0.5)) * uAmplitude;

  float d = -uTime * 0.5 * uSpeed;
  float a = 0.0;
  for (float i = 0.0; i < 8.0; ++i) {
    a += cos(i - d - a * uv.x);
    d += sin(uv.y * i + a);
  }
  d += uTime * 0.5 * uSpeed;

  // Create grayscale pattern
  float pattern = cos(length(uv * vec2(d, a))) * 0.5 + 0.5;
  pattern = cos(pattern * 3.14159 * 2.0) * 0.5 + 0.5;

  // Apply to all channels equally for true black and white
  vec3 col = vec3(pattern) * uColor;
  gl_FragColor = vec4(col, 1.0);
}
`;

    function createShader(type: number, source: string) {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      return shader;
    }

    const vShader = createShader(gl.VERTEX_SHADER, vertexShader);
    const fShader = createShader(gl.FRAGMENT_SHADER, fragmentShader);

    if (!vShader || !fShader) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vShader);
    gl.attachShader(program, fShader);
    gl.linkProgram(program);
    gl.useProgram(program);
    programRef.current = program;

    const positions = new Float32Array([-1, -1, 0, 0, 3, -1, 2, 0, -1, 3, 0, 2]);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const posLoc = gl.getAttribLocation(program, 'position');
    const uvLoc = gl.getAttribLocation(program, 'uv');
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 16, 0);
    gl.enableVertexAttribArray(uvLoc);
    gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 16, 8);

    uniformsRef.current = {
      uTime: gl.getUniformLocation(program, 'uTime'),
      uColor: gl.getUniformLocation(program, 'uColor'),
      uResolution: gl.getUniformLocation(program, 'uResolution'),
      uMouse: gl.getUniformLocation(program, 'uMouse'),
      uAmplitude: gl.getUniformLocation(program, 'uAmplitude'),
      uSpeed: gl.getUniformLocation(program, 'uSpeed'),
    };

    gl.uniform3f(uniformsRef.current.uColor, 0.15, 0.15, 0.15);
    gl.uniform2f(uniformsRef.current.uMouse, 0.5, 0.5);
    gl.uniform1f(uniformsRef.current.uAmplitude, 0.1);
    gl.uniform1f(uniformsRef.current.uSpeed, 0.5);

    function resize() {
      if (!canvas || !containerRef.current) return;
      canvas.width = containerRef.current.clientWidth;
      canvas.height = containerRef.current.clientHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform3f(uniformsRef.current.uResolution!, canvas.width, canvas.height, canvas.width / canvas.height);
    }
    window.addEventListener('resize', resize);
    resize();

    let rafId: number;
    function animate(now: number) {
      if (!glRef.current) return;
      rafId = requestAnimationFrame(animate);
      const dt = (now - lastTimeRef.current) * 0.001;
      lastTimeRef.current = now;
      accumTimeRef.current += dt;
      gl.uniform1f(uniformsRef.current.uTime!, accumTimeRef.current);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    animate(performance.now());

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(rafId);
      if (canvas && containerRef.current && containerRef.current.contains(canvas)) {
        containerRef.current.removeChild(canvas);
      }
    };
  }, []);

  return <div ref={containerRef} className="iridescence-bg" />;
}

export default IridescenceBackground;
