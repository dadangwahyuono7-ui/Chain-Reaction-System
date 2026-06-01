"use client";

/**
 * ThreeBg — WebGL animated wireframe terrain (synthwave wave) REAKTIF MOUSE.
 * - kamera parallax ngikutin kursor
 * - terrain beriak (ripple) di posisi kursor
 * GPU-light: ~3.7K verts, basic material, no lights.
 */

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

function WaveGrid({ color }: { color: string }) {
  const geo = useMemo(() => new THREE.PlaneGeometry(40, 40, 60, 60), []);
  const original = useMemo(
    () => Float32Array.from(geo.attributes.position.array as Float32Array),
    [geo]
  );
  const { pointer } = useThree();

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    // posisi kursor diproyeksikan kasar ke grid-space
    const cx = pointer.x * 18;
    const cy = -pointer.y * 18;
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = original[i * 3];
      const y = original[i * 3 + 1];
      const base =
        Math.sin(x * 0.4 + t) * 0.6 + Math.cos(y * 0.4 + t * 0.8) * 0.6;
      // ripple di sekitar kursor
      const d2 = (x - cx) * (x - cx) + (y - cy) * (y - cy);
      const ripple = Math.exp(-d2 / 26) * Math.sin(t * 4 - Math.sqrt(d2)) * 1.4;
      pos.setZ(i, base + ripple);
    }
    pos.needsUpdate = true;
  });

  return (
    <mesh geometry={geo} rotation={[-Math.PI / 2.15, 0, 0]} position={[0, -2.2, 0]}>
      <meshBasicMaterial color={color} wireframe transparent opacity={0.32} />
    </mesh>
  );
}

function CameraRig() {
  useFrame((state) => {
    const p = state.pointer;
    state.camera.position.x += (p.x * 1.8 - state.camera.position.x) * 0.04;
    state.camera.position.y += (1.6 + p.y * 0.9 - state.camera.position.y) * 0.04;
    state.camera.lookAt(0, -0.4, 0);
  });
  return null;
}

export function ThreeBg({
  color = "#6366f1",
  bg = "#020617",
}: {
  color?: string;
  bg?: string;
}) {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none" style={{ backgroundColor: bg }}>
      <Canvas
        camera={{ position: [0, 1.6, 6], fov: 60 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        dpr={[1, 1.5]}
      >
        <color attach="background" args={[bg]} />
        <fog attach="fog" args={[bg, 5, 17]} />
        <CameraRig />
        <WaveGrid color={color} />
      </Canvas>
    </div>
  );
}
