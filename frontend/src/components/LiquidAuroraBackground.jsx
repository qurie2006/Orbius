import React, { useEffect, useRef, useState } from "react";

/**
 * LiquidAuroraBackground
 * 
 * Apple product-launch inspired flowing liquid aurora hero background.
 * Features:
 * - Fluid domain-warping fragment shader with layered organic waves
 * - Charcoal base (#121318) with flowing ribbons of muted mint, dark oceanic teal, cyan & subtle violet
 * - Continuous slow fluid motion without abrupt resets
 * - Subtle cursor-responsive parallax
 * - Travelling illumination crests along fluid waves
 * - Seamless edge-vignette blending into the page background
 * - Accessible fallback for prefers-reduced-motion and non-WebGL devices
 */
export default function LiquidAuroraBackground() {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const [webglSupported, setWebglSupported] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    // Check reduced motion preference
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Attempt to initialize WebGL context
    let gl = canvas.getContext("webgl", {
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });

    if (!gl) {
      gl = canvas.getContext("experimental-webgl");
    }

    if (!gl) {
      setWebglSupported(false);
      return;
    }

    // Vertex Shader: full-screen quad
    const vsSource = `
      attribute vec2 a_position;
      varying vec2 v_uv;
      void main() {
        v_uv = (a_position + 1.0) * 0.5;
        gl_Position = vec4(a_position, 0.0, 1.0);
      }
    `;

    // Fragment Shader: Organic domain-warped liquid aurora ribbons
    const fsSource = `
      precision highp float;
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform vec2 u_mouse;
      uniform float u_opacity;
      varying vec2 v_uv;

      // 2D Simplex Noise
      vec3 permute(vec3 x) { return mod(((x*34.0)+1.0)*x, 289.0); }

      float snoise(vec2 v){
        const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                 -0.577350269189626, 0.024390243902439);
        vec2 i  = floor(v + dot(v, C.yy) );
        vec2 x0 = v -   i + dot(i, C.xx);
        vec2 i1;
        i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec4 x12 = x0.xyxy + C.xxzz;
        x12.xy -= i1;
        i = mod(i, 289.0);
        vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 ))
        + i.x + vec3(0.0, i1.x, 1.0 ));
        vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy),
          dot(x12.zw,x12.zw)), 0.0);
        m = m*m ;
        m = m*m ;
        vec3 x = 2.0 * fract(p * C.www) - 1.0;
        vec3 h = abs(x) - 0.5;
        vec3 ox = floor(x + 0.5);
        vec3 a0 = x - ox;
        m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
        vec3 g;
        g.x  = a0.x  * x0.x  + h.x  * x0.y;
        g.yz = a0.yz * x12.xz + h.yz * x12.yw;
        return 130.0 * dot(m, g);
      }

      // Fractional Brownian Motion (fBm)
      float fbm(vec2 p) {
        float total = 0.0;
        float amp = 0.5;
        for (int i = 0; i < 4; i++) {
          total += snoise(p) * amp;
          p = p * 2.04 + vec2(1.6, 3.4);
          amp *= 0.5;
        }
        return total;
      }

      void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        float aspect = u_resolution.x / u_resolution.y;
        
        // Aspect-corrected coordinate space centered around the left/center hero
        vec2 p = uv;
        p.x *= aspect;
        
        // Slow continuous organic time flow
        float t = u_time * 0.075;

        // Subtle cursor parallax offset (damped)
        vec2 mouseShift = (u_mouse - 0.5) * 0.12;
        p += mouseShift;

        // Domain warping for liquid silk / aurora sheets
        vec2 q = vec2(
          fbm(p * 0.75 + vec2(t * 0.35, t * 0.2)),
          fbm(p * 0.85 - vec2(t * 0.25, t * 0.3))
        );

        vec2 r = vec2(
          fbm(p * 0.95 + 1.25 * q + vec2(1.7, 9.2) + vec2(t * 0.22, -t * 0.18)),
          fbm(p * 1.05 + 1.25 * q + vec2(8.3, 2.8) - vec2(t * 0.18, -t * 0.24))
        );

        // Core fluid noise field
        float f = fbm(p * 0.8 + 1.6 * r + t * 0.15);

        // Wave Layer 1: Diagonal silk ribbon flowing behind heading (mint + teal)
        float wave1 = sin((p.x * 1.35 - p.y * 0.75) + q.x * 2.4 + t * 0.6) * 0.5 + 0.5;
        float ribbon1 = smoothstep(0.18, 0.72, wave1) * smoothstep(0.96, 0.42, wave1);

        // Wave Layer 2: Secondary undulating cyan wave crossing center & right
        float wave2 = cos((p.x * 1.1 + p.y * 1.2) + r.y * 2.8 - t * 0.5) * 0.5 + 0.5;
        float ribbon2 = smoothstep(0.22, 0.78, wave2) * smoothstep(0.96, 0.45, wave2);

        // Wave Layer 3: Travelling illumination crests
        float crest = pow(max(0.0, sin(f * 5.5 + t * 0.9)), 7.0) * 0.28;

        // Sophisticated Apple Color Palette (Muted, Dark, Cinematic)
        vec3 bgCharcoal = vec3(0.071, 0.075, 0.094); // #121318 exact background
        vec3 darkTeal   = vec3(0.012, 0.115, 0.155); // #031d27 deep oceanic teal
        vec3 mutedMint  = vec3(0.22, 0.62, 0.46);   // #389e75 muted mint green
        vec3 softCyan   = vec3(0.18, 0.48, 0.68);   // #2e7cae soft cyan
        vec3 subViolet  = vec3(0.38, 0.24, 0.50);   // #613d80 extremely subtle violet

        // Base atmospheric gradient with oceanic teal depths
        vec3 color = bgCharcoal;
        float tealDensity = smoothstep(-0.4, 0.8, f) * 0.55;
        color = mix(color, darkTeal, tealDensity);

        // Add Layer 1: Muted Mint Flow (accentuating the left hero typography area)
        float mintWeight = ribbon1 * 0.42;
        color = mix(color, mutedMint, mintWeight);

        // Add Layer 2: Cyan Liquid Flow
        float cyanWeight = ribbon2 * 0.38;
        color = mix(color, softCyan, cyanWeight);

        // Add Subtle Violet Chromatic Undertone
        float violetWeight = clamp((r.x * r.y) * 0.45, 0.0, 0.22);
        color = mix(color, subViolet, violetWeight);

        // Travelling Illumination Crests along fluid waves
        color += crest * softCyan * 0.35;
        color += crest * mutedMint * 0.25;

        // Controlled contrast & brightness: Never overwhelm foreground white text
        color = clamp(color, 0.0, 0.48);

        // Seamless Vignette & Edge Feathering: guarantees ZERO visible frame or boundaries
        float edgeY = smoothstep(0.0, 0.22, uv.y) * smoothstep(1.0, 0.82, uv.y);
        float edgeX = smoothstep(0.0, 0.08, uv.x) * smoothstep(1.0, 0.92, uv.x);
        float vignette = edgeX * edgeY;

        // Final blend into the pure dark background
        vec3 finalColor = mix(bgCharcoal, color, vignette * u_opacity);

        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    // Compile shader helper
    function createShader(glCtx, type, source) {
      const shader = glCtx.createShader(type);
      glCtx.shaderSource(shader, source);
      glCtx.compileShader(shader);
      if (!glCtx.getShaderParameter(shader, glCtx.COMPILE_STATUS)) {
        console.error("Shader compilation error:", glCtx.getShaderInfoLog(shader));
        glCtx.deleteShader(shader);
        return null;
      }
      return shader;
    }

    const vs = createShader(gl, gl.VERTEX_SHADER, vsSource);
    const fs = createShader(gl, gl.FRAGMENT_SHADER, fsSource);

    if (!vs || !fs) {
      setWebglSupported(false);
      return;
    }

    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error("Program link error:", gl.getProgramInfoLog(program));
      setWebglSupported(false);
      return;
    }

    gl.useProgram(program);

    // Quad geometry covering [-1, 1]
    const posBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW
    );

    const aPosLoc = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(aPosLoc);
    gl.vertexAttribPointer(aPosLoc, 2, gl.FLOAT, false, 0, 0);

    // Uniform locations
    const uTimeLoc = gl.getUniformLocation(program, "u_time");
    const uResLoc = gl.getUniformLocation(program, "u_resolution");
    const uMouseLoc = gl.getUniformLocation(program, "u_mouse");
    const uOpacityLoc = gl.getUniformLocation(program, "u_opacity");

    // Dimensions & DPR
    let width = 0;
    let height = 0;

    function handleResize() {
      if (!container || !canvas) return;
      const rect = container.getBoundingClientRect();
      width = Math.max(rect.width, 320);
      height = Math.max(rect.height, 400);

      // DPR capped at 1.5 to guarantee buttery 60fps even on high-density displays
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);

      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.useProgram(program);
      gl.uniform2f(uResLoc, canvas.width, canvas.height);
    }

    handleResize();

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    resizeObserver.observe(container);

    // Mouse Tracking (Smooth interpolation)
    const mouse = { x: 0.5, y: 0.5, targetX: 0.5, targetY: 0.5 };

    function handleMouseMove(e) {
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = 1.0 - (e.clientY - rect.top) / rect.height;
      mouse.targetX = Math.max(0.0, Math.min(1.0, x));
      mouse.targetY = Math.max(0.0, Math.min(1.0, y));
    }

    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // Intersection Observer: Pause rendering when scrolled out of view
    let isVisible = true;
    const observer = new IntersectionObserver(
      ([entry]) => {
        isVisible = entry.isIntersecting;
      },
      { threshold: 0.05 }
    );
    observer.observe(container);

    // Animation Loop
    let animFrameId;
    let startTime = performance.now();
    let opacity = 0.0;

    function renderLoop(now) {
      animFrameId = requestAnimationFrame(renderLoop);

      if (!isVisible) return;

      const elapsed = (now - startTime) * 0.001;

      // Silky initial entrance fade-in (1.2s ease)
      if (opacity < 1.0) {
        opacity = Math.min(1.0, opacity + 0.018);
      }

      // Smooth mouse lerp
      mouse.x += (mouse.targetX - mouse.x) * 0.04;
      mouse.y += (mouse.targetY - mouse.y) * 0.04;

      gl.useProgram(program);
      gl.uniform1f(uTimeLoc, prefersReducedMotion ? 10.0 : elapsed);
      gl.uniform2f(uMouseLoc, mouse.x, mouse.y);
      gl.uniform1f(uOpacityLoc, opacity);

      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }

    animFrameId = requestAnimationFrame(renderLoop);

    // Cleanup
    return () => {
      cancelAnimationFrame(animFrameId);
      window.removeEventListener("mousemove", handleMouseMove);
      resizeObserver.disconnect();
      observer.disconnect();

      if (gl) {
        gl.deleteBuffer(posBuffer);
        gl.deleteProgram(program);
        gl.deleteShader(vs);
        gl.deleteShader(fs);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full pointer-events-none overflow-hidden select-none z-0"
      aria-hidden="true"
    >
      {/* GPU Shader Canvas */}
      {webglSupported ? (
        <canvas
          ref={canvasRef}
          className="w-full h-full block opacity-95 transition-opacity duration-1000"
          style={{ filter: "blur(0.5px)" }}
        />
      ) : (
        /* CSS Organic Aurora Fallback */
        <div className="w-full h-full relative overflow-hidden bg-[#121318]">
          <div className="absolute -top-[20%] -left-[10%] w-[80vw] h-[70vh] rounded-full bg-gradient-to-tr from-[#031d27]/40 via-[#389e75]/25 to-[#2e7cae]/20 blur-[130px] animate-pulse-glow" />
          <div className="absolute top-[20%] left-[25%] w-[60vw] h-[60vh] rounded-full bg-gradient-to-br from-[#2e7cae]/20 via-[#613d80]/15 to-[#389e75]/20 blur-[140px]" />
        </div>
      )}

      {/* Atmospheric Soft Vignette Overlay to fuse seamlessly with #121318 */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#121318]/50 via-transparent to-[#121318] pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-r from-[#121318]/40 via-transparent to-[#121318]/40 pointer-events-none" />
    </div>
  );
}
