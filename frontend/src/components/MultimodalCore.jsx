import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

/**
 * The Multimodal Intelligence Core (Apple-grade interactive 3D WebGL core)
 * Features:
 * - High-refractive frosted crystal sphere with PMREM environment reflections
 * - Multi-layered pulsating intelligence nucleus with iridescent energy core
 * - 3 inclined orbital rings with continuous beacon traversal
 * - Dynamic particle streams flowing from multimodal inputs into the core
 * - Contextual reasoning node graph with hairline connections
 * - Damped mouse-parallax and scroll reactivity
 * - Mobile-optimized responsive layout with zero horizontal overflow
 */
export default function MultimodalCore({ scrollY = 0 }) {
  const mountRef = useRef(null);
  const [webglSupported, setWebglSupported] = useState(true);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Check accessibility setting
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // WebGL capability check
    function isWebGLAvailable() {
      try {
        const canvas = document.createElement("canvas");
        return !!(window.WebGLRenderingContext && (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
      } catch (e) {
        return false;
      }
    }

    if (!isWebGLAvailable()) {
      setWebglSupported(false);
      return;
    }

    let width = container.clientWidth || 540;
    let height = container.clientHeight || 540;

    // 1. Scene & Camera Setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    // Responsive camera distance with generous margin on narrow mobile viewports
    const getCamZ = (w) => (w < 480 ? 14.2 : w < 768 ? 12.4 : 10.2);
    camera.position.set(0, 0, getCamZ(width));

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    container.appendChild(renderer.domElement);

    // 2. In-Memory PMREM Environment Map for Apple-grade Glass Reflections
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    pmremGenerator.compileEquirectangularShader();

    const envCanvas = document.createElement("canvas");
    envCanvas.width = 512;
    envCanvas.height = 256;
    const envCtx = envCanvas.getContext("2d");
    // Deep studio ambient gradient with specular highlights
    const envGrad = envCtx.createLinearGradient(0, 0, 512, 256);
    envGrad.addColorStop(0, "#081018");
    envGrad.addColorStop(0.25, "#102a3a");
    envGrad.addColorStop(0.5, "#0b201a");
    envGrad.addColorStop(0.75, "#1c1430");
    envGrad.addColorStop(1, "#07080c");
    envCtx.fillStyle = envGrad;
    envCtx.fillRect(0, 0, 512, 256);

    // Bright specular reflections on top and sides
    envCtx.fillStyle = "rgba(123, 208, 255, 0.7)";
    envCtx.beginPath();
    envCtx.arc(140, 80, 55, 0, Math.PI * 2);
    envCtx.fill();

    envCtx.fillStyle = "rgba(99, 243, 171, 0.85)";
    envCtx.beginPath();
    envCtx.arc(380, 160, 65, 0, Math.PI * 2);
    envCtx.fill();

    envCtx.fillStyle = "rgba(224, 182, 255, 0.6)";
    envCtx.beginPath();
    envCtx.arc(260, 40, 40, 0, Math.PI * 2);
    envCtx.fill();

    const envTexture = new THREE.CanvasTexture(envCanvas);
    envTexture.mapping = THREE.EquirectangularReflectionMapping;
    const envMap = pmremGenerator.fromEquirectangular(envTexture).texture;
    scene.environment = envMap;

    // Group for global parallax tilt
    const mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // 3. Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0x7bd0ff, 3.2);
    keyLight.position.set(-6, 7, 7);
    scene.add(keyLight);

    const mintRimLight = new THREE.DirectionalLight(0x63f3ab, 3.6);
    mintRimLight.position.set(7, -5, 5);
    scene.add(mintRimLight);

    const violetFill = new THREE.PointLight(0xe0b6ff, 2.2, 30);
    violetFill.position.set(0, -6, -3);
    scene.add(violetFill);

    // Internal Core Glow Point Lights
    const coreLight = new THREE.PointLight(0x7bd0ff, 4.0, 10);
    mainGroup.add(coreLight);

    const mintCoreLight = new THREE.PointLight(0x63f3ab, 3.2, 8);
    mainGroup.add(mintCoreLight);

    // 4. Central Frosted Glass Sphere (Translucent Apple-grade Caustic Glass)
    const outerGeo = new THREE.SphereGeometry(1.95, 64, 64);
    const glassMat = new THREE.MeshPhysicalMaterial({
      roughness: 0.08,
      transmission: 0.72,
      thickness: 1.4,
      ior: 1.48,
      reflectivity: 0.95,
      color: 0xc2f0ff,
      transparent: true,
      opacity: 0.52,
      clearcoat: 1.0,
      clearcoatRoughness: 0.03,
      emissive: 0x092634,
      emissiveIntensity: 0.45,
      envMap: envMap,
      envMapIntensity: 2.2,
      depthWrite: false,
    });
    const glassSphere = new THREE.Mesh(outerGeo, glassMat);
    glassSphere.renderOrder = 2;
    mainGroup.add(glassSphere);

    // Inner Pulsing Intelligence Nucleus (Rendered before glass with additive glow)
    const innerGeo = new THREE.SphereGeometry(1.1, 36, 36);
    const innerMat = new THREE.MeshStandardMaterial({
      color: 0x63f3ab,
      emissive: 0x63f3ab,
      emissiveIntensity: 2.2,
      roughness: 0.1,
      metalness: 0.8,
      wireframe: true,
      transparent: true,
      opacity: 0.92,
    });
    const innerNucleus = new THREE.Mesh(innerGeo, innerMat);
    innerNucleus.renderOrder = 1;
    mainGroup.add(innerNucleus);

    // Core Solid Energy Star
    const beadGeo = new THREE.SphereGeometry(0.55, 32, 32);
    const beadMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.96,
    });
    const coreBead = new THREE.Mesh(beadGeo, beadMat);
    coreBead.renderOrder = 1;
    mainGroup.add(coreBead);

    // Glowing Core Halo
    const haloGeo = new THREE.SphereGeometry(0.72, 32, 32);
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0x7bd0ff,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
    });
    const coreHalo = new THREE.Mesh(haloGeo, haloMat);
    coreHalo.renderOrder = 1;
    mainGroup.add(coreHalo);

    // Internal Nucleus Floating Particles
    const innerPartGeo = new THREE.BufferGeometry();
    const innerPartCount = 100;
    const innerPartPos = new Float32Array(innerPartCount * 3);
    for (let i = 0; i < innerPartCount * 3; i += 3) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = Math.cbrt(Math.random()) * 0.95;
      innerPartPos[i] = r * Math.sin(phi) * Math.cos(theta);
      innerPartPos[i + 1] = r * Math.sin(phi) * Math.sin(theta);
      innerPartPos[i + 2] = r * Math.cos(phi);
    }
    innerPartGeo.setAttribute("position", new THREE.BufferAttribute(innerPartPos, 3));
    const innerPartMat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.06,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
    });
    const innerPoints = new THREE.Points(innerPartGeo, innerPartMat);
    innerPoints.renderOrder = 1;
    mainGroup.add(innerPoints);

    // 5. Orbital Rings (Calibrated dimensions to prevent overflow)
    const rings = [];

    function createParticleTexture() {
      const canvas = document.createElement("canvas");
      canvas.width = 64;
      canvas.height = 64;
      const ctx = canvas.getContext("2d");
      const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
      gradient.addColorStop(0, "rgba(255,255,255,1)");
      gradient.addColorStop(0.3, "rgba(123,208,255,0.9)");
      gradient.addColorStop(0.7, "rgba(99,243,171,0.3)");
      gradient.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, 64, 64);
      return new THREE.CanvasTexture(canvas);
    }
    const particleTex = createParticleTexture();

    const ringConfigs = [
      { radius: 2.85, tube: 0.016, color: 0x7bd0ff, rotX: 1.15, rotY: 0.25, speed: 0.006, beaconColor: 0x7bd0ff },
      { radius: 3.45, tube: 0.018, color: 0x63f3ab, rotX: -0.75, rotY: 0.45, speed: -0.0045, beaconColor: 0x63f3ab },
      { radius: 3.95, tube: 0.014, color: 0xe0b6ff, rotX: 0.35, rotY: -0.85, speed: 0.0035, beaconColor: 0xe0b6ff },
    ];

    ringConfigs.forEach((cfg) => {
      const ringGroup = new THREE.Group();
      ringGroup.rotation.x = cfg.rotX;
      ringGroup.rotation.y = cfg.rotY;

      // Torus mesh
      const torusGeo = new THREE.TorusGeometry(cfg.radius, cfg.tube, 24, 160);
      const torusMat = new THREE.MeshBasicMaterial({
        color: cfg.color,
        transparent: true,
        opacity: 0.55,
      });
      const torusMesh = new THREE.Mesh(torusGeo, torusMat);
      ringGroup.add(torusMesh);

      // Beacon bead
      const beaconGeo = new THREE.SphereGeometry(0.09, 16, 16);
      const beaconMat = new THREE.MeshBasicMaterial({
        color: cfg.beaconColor,
      });
      const beaconMesh = new THREE.Mesh(beaconGeo, beaconMat);
      beaconMesh.position.x = cfg.radius;
      ringGroup.add(beaconMesh);

      mainGroup.add(ringGroup);
      rings.push({ group: ringGroup, speed: cfg.speed, beacon: beaconMesh, radius: cfg.radius });
    });

    // 6. Contextual Reasoning Nodes & Links
    const nodeCount = 12;
    const nodeCoords = [];
    const nodeGroup = new THREE.Group();
    mainGroup.add(nodeGroup);

    for (let i = 0; i < nodeCount; i++) {
      const r = 2.6 + Math.random() * 1.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI;
      const pos = new THREE.Vector3(
        r * Math.cos(phi) * Math.cos(theta),
        r * Math.cos(phi) * Math.sin(theta),
        r * Math.sin(phi)
      );
      nodeCoords.push(pos);

      const dotGeo = new THREE.SphereGeometry(0.045, 12, 12);
      const dotMat = new THREE.MeshBasicMaterial({
        color: i % 2 === 0 ? 0x63f3ab : 0x7bd0ff,
        transparent: true,
        opacity: 0.85,
      });
      const dot = new THREE.Mesh(dotGeo, dotMat);
      dot.position.copy(pos);
      nodeGroup.add(dot);
    }

    // Connect close nodes with thin lines
    const linePositions = [];
    for (let i = 0; i < nodeCount; i++) {
      for (let j = i + 1; j < nodeCount; j++) {
        const dist = nodeCoords[i].distanceTo(nodeCoords[j]);
        if (dist < 2.2) {
          linePositions.push(nodeCoords[i].x, nodeCoords[i].y, nodeCoords[i].z);
          linePositions.push(nodeCoords[j].x, nodeCoords[j].y, nodeCoords[j].z);
        }
      }
    }
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(linePositions, 3));
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x7bd0ff,
      transparent: true,
      opacity: 0.18,
    });
    const connectionLines = new THREE.LineSegments(lineGeo, lineMat);
    nodeGroup.add(connectionLines);

    // 7. Particle Ingestion Streams (Cubic Bézier flow)
    const streamSources = [
      new THREE.Vector3(-3.8, 2.0, 0.4),  // Text input
      new THREE.Vector3(3.9, 1.8, -0.3),  // Visual perception
      new THREE.Vector3(-3.2, -2.2, 0.6), // Document parsing
    ];

    const streamColors = [0x7bd0ff, 0x63f3ab, 0xe0b6ff];
    const streams = [];

    streamSources.forEach((src, sIdx) => {
      const pCount = 36;
      const positions = new Float32Array(pCount * 3);
      const progress = new Float32Array(pCount);
      const speeds = new Float32Array(pCount);
      const offsets = [];

      for (let i = 0; i < pCount; i++) {
        progress[i] = Math.random();
        speeds[i] = 0.0035 + Math.random() * 0.0035;
        offsets.push(new THREE.Vector3(
          (Math.random() - 0.5) * 0.4,
          (Math.random() - 0.5) * 0.4,
          (Math.random() - 0.5) * 0.4
        ));
      }

      const pGeo = new THREE.BufferGeometry();
      pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));

      const pMat = new THREE.PointsMaterial({
        color: streamColors[sIdx],
        size: 0.09,
        map: particleTex,
        transparent: true,
        opacity: 0.92,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });

      const pSystem = new THREE.Points(pGeo, pMat);
      mainGroup.add(pSystem);

      const midPoint = new THREE.Vector3()
        .addVectors(src, new THREE.Vector3(0, 0, 0))
        .multiplyScalar(0.5);
      midPoint.x += (sIdx === 0 ? 0.7 : sIdx === 1 ? -0.7 : 0.5);
      midPoint.y += (sIdx === 2 ? 0.5 : -0.35);

      const curve = new THREE.QuadraticBezierCurve3(src, midPoint, new THREE.Vector3(0, 0, 0));

      streams.push({
        pGeo,
        positions,
        progress,
        speeds,
        offsets,
        curve,
        pCount,
      });
    });

    // 8. Mouse Parallax & Smooth Damping
    const mouse = { x: 0, y: 0, targetX: 0, targetY: 0 };
    function handleMouseMove(e) {
      const rect = container.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      mouse.targetX = (clientX / rect.width) * 2 - 1;
      mouse.targetY = -(clientY / rect.height) * 2 + 1;
    }

    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // Handle Resize & Container Bounds Observation
    function handleResize() {
      if (!container) return;
      width = container.clientWidth || 540;
      height = container.clientHeight || 540;
      camera.aspect = width / height;
      camera.position.z = getCamZ(width);
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }
    window.addEventListener("resize", handleResize);

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    resizeObserver.observe(container);

    // 9. Intersection Observer (Pause rendering when off-screen)
    let isVisible = true;
    const observer = new IntersectionObserver(
      ([entry]) => {
        isVisible = entry.isIntersecting;
      },
      { threshold: 0.05 }
    );
    observer.observe(container);

    // 10. Main Animation Loop
    let animationFrameId;
    let clock = new THREE.Clock();
    let entranceProgress = 0;

    function animate() {
      animationFrameId = requestAnimationFrame(animate);

      if (!isVisible) return;

      const elapsed = clock.getElapsedTime();

      // Cinematic entrance
      if (entranceProgress < 1) {
        entranceProgress += 0.016;
        const ease = 1 - Math.pow(1 - entranceProgress, 3);
        mainGroup.scale.set(ease, ease, ease);
      }

      // Mouse Parallax Damping
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      if (!prefersReducedMotion) {
        mainGroup.rotation.y = mouse.x * 0.24 + elapsed * 0.04;
        mainGroup.rotation.x = -mouse.y * 0.18;
        mainGroup.position.y = Math.sin(elapsed * 1.2) * 0.1;

        // Rhythmic nucleus pulse and rotation
        const pulse = 1 + Math.sin(elapsed * 2.4) * 0.08;
        innerNucleus.scale.set(pulse, pulse, pulse);
        innerNucleus.rotation.y = -elapsed * 0.18;
        innerNucleus.rotation.x = Math.sin(elapsed * 0.4) * 0.12;
        innerMat.emissiveIntensity = 2.0 + Math.sin(elapsed * 2.4) * 0.6;
        coreBead.scale.set(1 + Math.cos(elapsed * 3) * 0.12, 1 + Math.cos(elapsed * 3) * 0.12, 1 + Math.cos(elapsed * 3) * 0.12);
        coreHalo.scale.set(pulse * 1.15, pulse * 1.15, pulse * 1.15);

        // Rotation of outer glass sphere
        glassSphere.rotation.y = elapsed * 0.08;
        glassSphere.rotation.z = Math.sin(elapsed * 0.4) * 0.04;

        // Rotate inner points
        innerPoints.rotation.y = -elapsed * 0.22;
        innerPoints.rotation.x = elapsed * 0.12;

        // Rotate rings & beacons
        rings.forEach((r, idx) => {
          r.group.rotation.z += r.speed;
          const angle = elapsed * (0.75 + idx * 0.25);
          r.beacon.position.x = Math.cos(angle) * r.radius;
          r.beacon.position.y = Math.sin(angle) * r.radius;
        });

        // Rotate relationship nodes
        nodeGroup.rotation.y = elapsed * 0.025;
        nodeGroup.rotation.x = Math.sin(elapsed * 0.25) * 0.03;

        // Update Particle Ingestion Streams
        streams.forEach((st) => {
          const { positions, progress, speeds, offsets, curve, pCount, pGeo } = st;
          for (let i = 0; i < pCount; i++) {
            progress[i] += speeds[i];
            if (progress[i] > 1) {
              progress[i] = 0;
            }

            const pPoint = curve.getPoint(progress[i]);
            const offsetFactor = Math.sin(progress[i] * Math.PI) * 0.25;
            positions[i * 3] = pPoint.x + offsets[i].x * offsetFactor;
            positions[i * 3 + 1] = pPoint.y + offsets[i].y * offsetFactor;
            positions[i * 3 + 2] = pPoint.z + offsets[i].z * offsetFactor;
          }
          pGeo.attributes.position.needsUpdate = true;
        });
      }

      renderer.render(scene, camera);
    }

    animate();

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);
      resizeObserver.disconnect();
      observer.disconnect();

      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }

      // Dispose Three.js resources
      outerGeo.dispose();
      glassMat.dispose();
      innerGeo.dispose();
      innerMat.dispose();
      beadGeo.dispose();
      beadMat.dispose();
      haloGeo.dispose();
      haloMat.dispose();
      innerPartGeo.dispose();
      innerPartMat.dispose();
      lineGeo.dispose();
      lineMat.dispose();
      particleTex.dispose();
      envTexture.dispose();
      envMap.dispose();
      pmremGenerator.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div
      className="relative w-full h-[400px] sm:h-[480px] lg:h-[560px] flex items-center justify-center select-none overflow-hidden"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Soft Multi-chromatic Ambient Glow Backdrop (Pure Negative Space Lighting) */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
        <div className="w-[280px] sm:w-[380px] lg:w-[440px] h-[280px] sm:h-[380px] lg:h-[440px] rounded-full bg-gradient-to-tr from-[#63f3ab]/14 via-[#7bd0ff]/16 to-[#e0b6ff]/12 blur-[100px] animate-pulse-glow" />
        <div className="absolute w-[180px] h-[180px] rounded-full bg-secondary/18 blur-[65px]" />
      </div>

      {/* WebGL Canvas Container */}
      <div
        ref={mountRef}
        className="w-full h-full relative z-10 flex items-center justify-center cursor-grab active:cursor-grabbing overflow-hidden"
      />

      {/* Static Fallback if WebGL is unavailable */}
      {!webglSupported && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center z-10">
          <div className="w-44 h-44 rounded-full bg-gradient-to-tr from-secondary/30 via-tertiary-fixed/30 to-primary/20 border border-white/20 blur-[1px] shadow-[0_0_50px_rgba(123,208,255,0.3)] flex items-center justify-center">
            <span className="material-symbols-outlined text-white text-[42px] animate-pulse">
              blur_on
            </span>
          </div>
          <p className="mt-4 text-xs font-label-mono text-outline">
            The Multimodal Intelligence Core
          </p>
        </div>
      )}

    </div>
  );
}
