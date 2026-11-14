
import React, { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html, Stars } from "@react-three/drei";
import * as THREE from "three";

// Create a procedural lunar surface texture
function createMoonTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 512;

  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#888888";
  ctx.fillRect(0, 0, 1024, 512);

  for (let i = 0; i < 18000; i++) {
    const x = Math.random() * 1024;
    const y = Math.random() * 512;
    const r = Math.random() * 5 + 1;
    const shade = Math.floor(Math.random() * 100 + 90);

    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = `rgb(${shade}, ${shade}, ${shade})`;
    ctx.fill();
  }

  // Add larger crater-like features
  for (let i = 0; i < 100; i++) {
    const x = Math.random() * 1024;
    const y = Math.random() * 512;
    const r = Math.random() * 15 + 5;

    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(35,35,35,0.45)";
    ctx.lineWidth = 3;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(x - r * 0.2, y - r * 0.2, r * 0.6, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(210,210,210,0.15)";
    ctx.fill();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// Rotating Moon
function Moon() {
  const moonRef = useRef();

  const moonTexture = useMemo(() => createMoonTexture(), []);

  useFrame((state, delta) => {
    if (moonRef.current) {
      moonRef.current.rotation.y += delta * 0.035;
    }
  });

  return (
    <mesh ref={moonRef}>
      <sphereGeometry args={[2, 96, 96]} />
      <meshStandardMaterial
        map={moonTexture}
        bumpMap={moonTexture}
        bumpScale={0.035}
        roughness={1}
      />
    </mesh>
  );
}

// Temporary demonstration markers (not scientific landing coordinates)
function DemoMarkers() {
  const markers = [
    { id: 1, name: "Demo Site 1", position: [0, 1.95, 0.45] },
    { id: 2, name: "Demo Site 2", position: [-1.1, 1.55, 0.5] },
    { id: 3, name: "Demo Site 3", position: [1.2, -1.4, 0.45] },
  ];

  return (
    <>
      {markers.map((marker) => (
        <group key={marker.id} position={marker.position}>
          <mesh>
            <sphereGeometry args={[0.065, 16, 16]} />
            <meshBasicMaterial color="#00e5ff" />
          </mesh>

          <Html distanceFactor={8}>
            <div
              style={{
                color: "white",
                background: "#102b3b",
                border: "1px solid #00e5ff",
                borderRadius: "5px",
                padding: "5px 8px",
                whiteSpace: "nowrap",
                fontSize: "11px",
              }}
            >
              {marker.name}
            </div>
          </Html>
        </group>
      ))}
    </>
  );
}

export default function MoonGlobe() {
  return (
    <div style={{ width: "100%", height: "550px" }}>
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }}>
        <color attach="background" args={["#030712"]} />

        <ambientLight intensity={0.65} />

        <directionalLight
          position={[5, 3, 5]}
          intensity={2.2}
        />

        <Stars
          radius={80}
          depth={50}
          count={2500}
          factor={4}
          fade
        />

        <Moon />
        <DemoMarkers />

        <OrbitControls
          enablePan={false}
          enableZoom={true}
          minDistance={3}
          maxDistance={10}
          enableDamping
        />
      </Canvas>
    </div>
  );
}
