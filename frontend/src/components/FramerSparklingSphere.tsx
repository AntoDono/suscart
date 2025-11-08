import { Canvas } from '@react-three/fiber';
import { SparklingSphereR3F } from './SparklingSphereR3F';
import { addPropertyControls, ControlType } from 'framer';

interface FramerSparklingSphereProps {
  particleCount: number;
  interactionRadius: number;
  maxGlowIntensity: number;
  baseGlowIntensity: number;
  dispersalForce: number;
  returnForce: number;
  dampingFactor: number;
  rotationSpeed: number;
  bloomIntensity: number;
  bloomThreshold: number;
  bloomRadius: number;
  backgroundColor: string;
}

export function FramerSparklingSphere({
  particleCount = 2500,
  interactionRadius = 1.5,
  maxGlowIntensity = 5,
  baseGlowIntensity = 0.5,
  dispersalForce = 0.08,
  returnForce = 0.02,
  dampingFactor = 0.95,
  rotationSpeed = 0.0025,
  bloomIntensity = 1.5,
  bloomThreshold = 0.1,
  bloomRadius = 0.4,
  backgroundColor = "#000000",
}: FramerSparklingSphereProps) {
  return (
    <div style={{ width: '100%', height: '100%', background: backgroundColor }}>
      <Canvas>
        <color attach="background" args={[backgroundColor]} />
        <ambientLight intensity={0.1} />
        <pointLight position={[5, 5, 5]} intensity={1} />
        <SparklingSphereR3F
          particleCount={particleCount}
          interactionRadius={interactionRadius}
          maxGlowIntensity={maxGlowIntensity}
          baseGlowIntensity={baseGlowIntensity}
          dispersalForce={dispersalForce}
          returnForce={returnForce}
          dampingFactor={dampingFactor}
          rotationSpeed={rotationSpeed}
          bloomIntensity={bloomIntensity}
          bloomThreshold={bloomThreshold}
          bloomRadius={bloomRadius}
        />
      </Canvas>
    </div>
  );
}

// Add Framer property controls
addPropertyControls(FramerSparklingSphere, {
  particleCount: {
    type: ControlType.Number,
    title: "Particle Count",
    min: 100,
    max: 10000,
    defaultValue: 2500,
  },
  interactionRadius: {
    type: ControlType.Number,
    title: "Interaction Radius",
    min: 0.1,
    max: 5,
    defaultValue: 1.5,
    step: 0.1,
  },
  maxGlowIntensity: {
    type: ControlType.Number,
    title: "Max Glow Intensity",
    min: 1,
    max: 10,
    defaultValue: 5,
    step: 0.1,
  },
  baseGlowIntensity: {
    type: ControlType.Number,
    title: "Base Glow Intensity",
    min: 0.1,
    max: 2,
    defaultValue: 0.5,
    step: 0.1,
  },
  dispersalForce: {
    type: ControlType.Number,
    title: "Dispersal Force",
    min: 0.01,
    max: 0.5,
    defaultValue: 0.08,
    step: 0.01,
  },
  returnForce: {
    type: ControlType.Number,
    title: "Return Force",
    min: 0.01,
    max: 0.2,
    defaultValue: 0.02,
    step: 0.01,
  },
  dampingFactor: {
    type: ControlType.Number,
    title: "Damping Factor",
    min: 0.5,
    max: 0.99,
    defaultValue: 0.95,
    step: 0.01,
  },
  rotationSpeed: {
    type: ControlType.Number,
    title: "Rotation Speed",
    min: 0,
    max: 0.01,
    defaultValue: 0.0025,
    step: 0.0001,
  },
  bloomIntensity: {
    type: ControlType.Number,
    title: "Bloom Intensity",
    min: 0,
    max: 5,
    defaultValue: 1.5,
    step: 0.1,
  },
  bloomThreshold: {
    type: ControlType.Number,
    title: "Bloom Threshold",
    min: 0,
    max: 1,
    defaultValue: 0.1,
    step: 0.05,
  },
  bloomRadius: {
    type: ControlType.Number,
    title: "Bloom Radius",
    min: 0,
    max: 1,
    defaultValue: 0.4,
    step: 0.05,
  },
  backgroundColor: {
    type: ControlType.Color,
    title: "Background Color",
    defaultValue: "#000000",
  },
});
