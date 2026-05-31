"use client";

/**
 * ThreeBg — WebGL animated wireframe terrain (synthwave wave).
 * GPU-light: ~3.7K verts updated CPU-side per frame, no heavy shaders.
 * Fixed di belakang semua konten (-z-10), pointer-events-none → murni dekoratif.
 */

import { Canvas, useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

function WaveGrid({ color }: { color: string }) {
  const geo = useMemo(() => new THREE.PlaneGeometry(40, 40, 60, 60), []);
  const original = useMemo(
    () => Float32Array.from(geo.attributes.position.array as Float32Array),
    [geo]
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = original[i * 3];
      const y = original[i * 3 + 1];
      const z =
        Math.sin(x * 0.4 + t) * 0.6 +
        Math.cos(y * 0.4 + t * 0.8) * 0.6;
      pos.setZ(i, z);
    }
    pos.needsUpdate = true;
  });

  return (
    <mesh geometry={geo} rotation={[-Math.PI / 2.15, 0, 0]} position={[0, -2.2, 0]}>
      <meshBasicMaterial color={color} wireframe transparent opacity={0.3} />
    </mesh>
  );
}

export function ThreeBg({
  color = "#6366f1",
  bg = "#020617",
}: {
  color?: string;
  bg?: string;
}) {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none">
      <Canvas
        camera={{ position: [0, 1.6, 6], fov: 60 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        dpr={[1, 1.5]}
      >
        <color attach="background" args={[bg]} />
        <fog attach="fog" args={[bg, 5, 17]} />
        <WaveGrid color={color} />
      </Canvas>
    </div>
  );
}
