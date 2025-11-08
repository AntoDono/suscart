// @ts-nocheck
import { useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { createNoise3D } from 'simplex-noise';

interface EmittedParticle {
  mesh: THREE.Mesh;
  velocity: THREE.Vector3;
  life: number;
}

interface ParticleProps {
  position: THREE.Vector3;
  baseColor: THREE.Color;
  mesh: THREE.Mesh;
  originalPosition: THREE.Vector3;
  velocity: THREE.Vector3;
  quaternion: THREE.Quaternion;
  currentIntensity: number;
  repelColor: THREE.Color;
  maxDistanceTraveled: number;
  lastEmitTime?: number;
}

interface SparklingSphereR3FProps {
  radius?: number;
  particleCount?: number;
  interactionRadius?: number;
  maxGlowIntensity?: number;
  baseGlowIntensity?: number;
  dispersalForce?: number;
  returnForce?: number;
  dampingFactor?: number;
  rotationSpeed?: number;
  maxRepelDistance?: number;
}

const baseColors = [
  new THREE.Color(0xCCFFBD), // Light mint - rgb(204, 255, 189)
  new THREE.Color(0xAAF0D1), // Aqua mint - rgb(170, 240, 209)
  new THREE.Color(0x7ECA9C), // Mint green - rgb(126, 202, 156)
];
const repelColors = [
  new THREE.Color(0xCCFFBD), // Brightest mint when hit - rgb(204, 255, 189)
  new THREE.Color(0x7ECA9C), // Transition to mid mint - rgb(126, 202, 156)
  new THREE.Color(0x1C1427), // Dark space purple - rgb(28, 20, 39)
];

export const SparklingSphereR3F = ({
  radius = 1.1,
  particleCount = 1000,
  interactionRadius = 1.5 * radius,
  maxGlowIntensity = 9,
  baseGlowIntensity = 2,
  dispersalForce = 0.008,        // Even gentler push for smoother interaction
  returnForce = 0.01,            // Reduced from 0.02 - slower return
  dampingFactor = 0.95,          // Higher damping for smoother motion
  rotationSpeed = 0.001,         // Reduced from 0.0025 - slower rotation
  maxRepelDistance = 0.3,        // Reduced from 0.5 - particles don't travel as far
}: SparklingSphereR3FProps) => {
  const groupRef = useRef<THREE.Group>(null);
  const particles = useRef<ParticleProps[]>([]);
  const emittedParticles = useRef<EmittedParticle[]>([]);
  const mousePos = useRef(new THREE.Vector2());
  const lastMousePos = useRef(new THREE.Vector3());
  const mousePosition3D = useRef(new THREE.Vector3());
  const mouseVelocity = useRef(new THREE.Vector3());
  const raycaster = useRef(new THREE.Raycaster());
  const lastTime = useRef(0);
  const noise3D = useRef(createNoise3D());

  // Create particles if they don't exist
  if (particles.current.length === 0) {
    const geometry = new THREE.IcosahedronGeometry(0.015, 6);
    const material = new THREE.MeshPhongMaterial({
      emissiveIntensity: 2,
      specular: new THREE.Color(0xffffff),
      shininess: 100,
      transparent: true,
      opacity: 0.9,
      fog: true,
    });

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);

      const baseColor = baseColors[Math.floor(Math.random() * baseColors.length)];
      const repelColor = repelColors[Math.floor(Math.random() * repelColors.length)];

      const m = material.clone();
      m.color = baseColor;
      m.emissive = repelColor;

      const mesh = new THREE.Mesh(geometry, m);
      mesh.receiveShadow = true;
      mesh.castShadow = true;
      mesh.position.set(x, y, z);

      particles.current.push({
        mesh,
        position: mesh.position.clone(),
        originalPosition: mesh.position.clone(),
        velocity: new THREE.Vector3(),
        quaternion: new THREE.Quaternion(),
        baseColor,
        repelColor,
        currentIntensity: baseGlowIntensity,
        maxDistanceTraveled: 0,
      });
    }
  }

  const emitParticles = (position: THREE.Vector3, direction: THREE.Vector3, color: THREE.Color, speed: number) => {
    // Super minimal emission - only 1 particle sometimes
    const emitCount = Math.random() > 0.7 ? 1 : 0;
    const emitGeometry = new THREE.IcosahedronGeometry(0.003, 1);
    const baseSpeed = speed * 1;

    for (let i = 0; i < emitCount; i++) {
      const spread = new THREE.Vector3(
        (Math.random() - 0.5) * 0.8,
        (Math.random() - 0.5) * 0.8,
        (Math.random() - 0.5) * 0.8
      );
      const emitDir = direction.clone().add(spread).normalize();

      const particleSpeed = Math.max(
        baseSpeed * (0.5 + Math.random() * 0.5),
        0.02
      );

      const material = new THREE.MeshPhongMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 2,
        transparent: true,
        opacity: 1,
      });

      const mesh = new THREE.Mesh(emitGeometry, material);
      mesh.position.copy(position);
      groupRef.current?.add(mesh);

      emittedParticles.current.push({
        mesh,
        velocity: emitDir.multiplyScalar(particleSpeed),
        life: 1.0,
      });
    }
  };

  useFrame((state, delta) => {
    if (!groupRef.current) return;

    // Calculate mouse velocity
    const currentTime = state.clock.getElapsedTime();
    const deltaTime = currentTime - lastTime.current;
    lastTime.current = currentTime;

    // Update mouse position and calculate velocity
    const newMousePos = new THREE.Vector3(
      (state.mouse.x * state.viewport.width) / 2,
      (state.mouse.y * state.viewport.height) / 2,
      0
    );

    mouseVelocity.current
      .copy(newMousePos)
      .sub(lastMousePos.current)
      .divideScalar(deltaTime);
    
    lastMousePos.current.copy(newMousePos);
    mousePos.current.set(newMousePos.x, newMousePos.y);

    // Calculate mouse speed (magnitude of velocity)
    const mouseSpeed = mouseVelocity.current.length();
    
    raycaster.current.setFromCamera(mousePos.current, state.camera);
    const intersectPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    raycaster.current.ray.intersectPlane(intersectPlane, mousePosition3D.current);

    // Update particles
    particles.current.forEach((particle) => {
      // Add natural distortion using noise
      const noiseScale = 0.5; // Scale of noise
      const noiseStrength = 0.02; // Strength of distortion
      const noiseSpeed = 0.3; // Speed of animation

      const noiseValue = noise3D.current(
        particle.originalPosition.x * noiseScale,
        particle.originalPosition.y * noiseScale,
        particle.originalPosition.z * noiseScale + currentTime * noiseSpeed
      );

      // Apply natural breathing motion
      const breathingOffset = particle.originalPosition
        .clone()
        .normalize()
        .multiplyScalar(noiseValue * noiseStrength);

      // Add the breathing motion to velocity gently
      particle.velocity.add(breathingOffset.multiplyScalar(0.1));

      // Calculate distortion-based color - map noise value to color
      const distortionAmount = Math.abs(noiseValue); // 0 to 1
      const distortionColor = new THREE.Color();

      // Interpolate through base colors based on distortion
      if (distortionAmount < 0.5) {
        // Low distortion: interpolate between first two base colors
        const t = distortionAmount * 2;
        distortionColor.lerpColors(baseColors[0], baseColors[1], t);
      } else {
        // High distortion: interpolate between second and third base colors
        const t = (distortionAmount - 0.5) * 2;
        distortionColor.lerpColors(baseColors[1], baseColors[2], t);
      }

      const distanceToMouse = mousePosition3D.current.distanceTo(particle.position);
      const isInRange = distanceToMouse < interactionRadius;

      // Scale force based on mouse speed and distance - much gentler
      const speedFactor = Math.min(mouseSpeed * 2, 1); // Reduced multiplier and cap
      const distanceFactor = 1 - (distanceToMouse / interactionRadius);
      const force = isInRange
        ? dispersalForce * speedFactor * distanceFactor
        : 0;

      if (isInRange) {
        // Calculate repulsion direction based on mouse movement
        const repulsionDir = particle.position
          .clone()
          .sub(mousePosition3D.current)
          .normalize();

        // Add some influence from mouse velocity direction - reduced
        const mouseInfluence = mouseVelocity.current.clone().normalize();
        repulsionDir.lerp(mouseInfluence, 0.15); // Reduced from 0.3 to 0.15

        // Apply force with less randomization for smoother movement
        const randomFactor = 1 + (Math.random() - 0.5) * 0.2; // Reduced from ±20% to ±10%
        particle.velocity.add(
          repulsionDir.multiplyScalar(force * randomFactor)
        );

        // Calculate distance from original position
        const distanceFromOrigin = particle.position.distanceTo(particle.originalPosition);
        particle.maxDistanceTraveled = Math.max(particle.maxDistanceTraveled, distanceFromOrigin);

        // Calculate progress for intensity (0 to 1)
        const progress = Math.min(distanceFromOrigin / maxRepelDistance, 1);

        // Add natural pulsating glow
        const pulse = Math.sin(currentTime * 2) * 0.5 + 0.5; // 0 to 1 oscillation
        const hoverPulse = Math.sin(currentTime * 3 + distanceToMouse) * 0.3 + 0.7; // Faster pulse on hover

        // Use distortion color as base, add smooth glow on hover
        particle.mesh.material.color = distortionColor;
        particle.mesh.material.emissive = distortionColor;
        particle.mesh.material.emissiveIntensity = 2 + distortionAmount * 2 + (pulse * 1.5) + (progress * hoverPulse * 4); // Pulsating + hover glow
        particle.mesh.material.opacity = 0.9;

        // Emit particles on collision with longer cooldown and probability check
        // Only 3% of particles emit, and only every 1 second
        if (Math.random() < 0.03 && (!particle.lastEmitTime || currentTime - particle.lastEmitTime > 1.0)) {
          emitParticles(
            particle.position.clone(),
            particle.velocity.clone().normalize(),
            particle.mesh.material.emissive,
            mouseSpeed
          );
          particle.lastEmitTime = currentTime;
        }
      } else {
        // Not in mouse range - use distortion-based colors
        if (particle.maxDistanceTraveled > 0.01) {
          // Still returning from mouse interaction
          const returnProgress = 1 - Math.min(particle.maxDistanceTraveled / maxRepelDistance, 1);

          // Determine which colors to lerp between for return
          const colorIndex = Math.min(
            Math.floor((1 - returnProgress) * (repelColors.length - 1)),
            repelColors.length - 2
          );
          const colorProgress = ((1 - returnProgress) * (repelColors.length - 1)) % 1;

          // Lerp between current and next color
          const returnColor = new THREE.Color();
          returnColor.lerpColors(
            repelColors[colorIndex],
            repelColors[colorIndex + 1],
            colorProgress
          );

          // Add natural pulsating glow
          const pulse = Math.sin(currentTime * 2) * 0.5 + 0.5; // 0 to 1 oscillation

          particle.mesh.material.color = returnColor.lerp(distortionColor, returnProgress);
          particle.mesh.material.emissive = returnColor.lerp(distortionColor, returnProgress);
          particle.mesh.material.emissiveIntensity = 2 + (1 - returnProgress) * 3 + (pulse * 1.5);
          particle.mesh.material.opacity = 0.9;
        } else {
          // Fully at rest - use distortion-based color with pulsating
          const pulse = Math.sin(currentTime * 2) * 0.5 + 0.5; // 0 to 1 oscillation

          particle.mesh.material.color = distortionColor;
          particle.mesh.material.emissive = distortionColor;
          particle.mesh.material.emissiveIntensity = 2 + distortionAmount * 2 + (pulse * 1.5);
          particle.mesh.material.opacity = 0.9;
        }

        // Reset max distance when particle returns close to original position
        if (particle.position.distanceTo(particle.originalPosition) < 0.1) {
          particle.maxDistanceTraveled = 0;
        }
      }

      const distanceToOrigin = particle.position.distanceTo(particle.originalPosition);
      const returnForceVector = particle.originalPosition
        .clone()
        .sub(particle.position)
        .normalize()
        .multiplyScalar(returnForce * distanceToOrigin);

      particle.velocity.add(returnForceVector);
      particle.velocity.multiplyScalar(dampingFactor);

      particle.position.add(particle.velocity);
      particle.mesh.position.copy(particle.position);

      // Particle rotation based on velocity
      if (particle.velocity.length() > 0.001) {
        particle.quaternion.setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          particle.velocity.clone().normalize()
        );
        particle.mesh.quaternion.slerp(particle.quaternion, 0.1);
      }
    });

    // Update emitted particles with improved physics
    emittedParticles.current = emittedParticles.current.filter((emitted) => {
      emitted.life -= delta * (1.5 + Math.random() * 0.5); // Varied fade speed
      if (emitted.life <= 0) {
        groupRef.current?.remove(emitted.mesh);
        return false;
      }

      // Add slight gravity effect
      emitted.velocity.y -= delta * 0.1;
      
      // Update position with damping
      emitted.mesh.position.add(emitted.velocity);
      emitted.velocity.multiplyScalar(0.98); // Slight air resistance

      if (emitted.mesh.material instanceof THREE.MeshPhongMaterial) {
        emitted.mesh.material.opacity = emitted.life;
        emitted.mesh.material.emissiveIntensity = emitted.life * 2;
      }

      return true;
    });

    groupRef.current.rotation.y += rotationSpeed;
  });

  return (
    <group ref={groupRef}>
      {particles.current.map((particle, index) => (
        <primitive key={index} object={particle.mesh} />
      ))}
    </group>
  );
};
