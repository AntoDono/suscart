import { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';

interface CubeMesh extends THREE.Mesh {
  center: THREE.Vector3;
}

const SolverOrb = () => {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const currentMount = mountRef.current;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      45,
      currentMount.clientWidth / currentMount.clientHeight,
      0.1,
      1000
    );
    camera.position.set(7, 7, 14);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(currentMount.clientWidth, currentMount.clientHeight);
    currentMount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const shaderMaterial = new THREE.ShaderMaterial({
      uniforms: {
        rimPower: { value: 2.0 },
        rimIntensity: { value: 1.2 },
      },
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          vViewPosition = -mvPosition.xyz;
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        uniform float rimPower;
        uniform float rimIntensity;
        void main() {
          vec3 viewDir = normalize(vViewPosition);
          float fresnel = 1.0 - dot(viewDir, vNormal);
          fresnel = pow(fresnel, rimPower) * rimIntensity;
          float gray = fresnel * 0.6;
          gl_FragColor = vec4(gray, gray, gray, 1.0);
        }
      `,
      transparent: true,
      depthWrite: false,
    });

    const cubes: CubeMesh[] = [];

    // Create 3x3x3 Rubik's cube
    for (let x = -1; x <= 1; x++) {
      for (let y = -1; y <= 1; y++) {
        for (let z = -1; z <= 1; z++) {
          const cube = new THREE.Mesh(
            new RoundedBoxGeometry(0.95, 0.95, 0.95, 2, 0.05),
            shaderMaterial.clone()
          ) as unknown as CubeMesh;
          cube.center = new THREE.Vector3(x, y, z);
          cube.geometry.translate(x, y, z);
          cubes.push(cube);
          group.add(cube);
        }
      }
    }

    let animationFrameId: number;
    let rotationTimeout: ReturnType<typeof setTimeout>;
    let isRotating = false;

    const rotations = [
      () => rotate('XYZ', 'x', 1, -1),
      () => rotate('XYZ', 'x', 1, 1),
      () => rotate('XYZ', 'x', -1, 1),
      () => rotate('XYZ', 'x', -1, -1),
      () => rotate('YZX', 'y', 1, -1),
      () => rotate('YZX', 'y', 1, 1),
      () => rotate('YZX', 'y', -1, 1),
      () => rotate('YZX', 'y', -1, -1),
      () => rotate('ZXY', 'z', 1, -1),
      () => rotate('ZXY', 'z', 1, 1),
      () => rotate('ZXY', 'z', -1, 1),
      () => rotate('ZXY', 'z', -1, -1),
    ];

    let rot = { k: 0, oldK: 0 };
    const e = new THREE.Euler();

    function rotate(order: THREE.EulerOrder, axis: 'x' | 'y' | 'z', sign: number, dir: number) {
      for (let cube of cubes) {
        if (Math.abs(cube.center[axis] - sign) < 0.1) {
          cube.rotation.reorder(order);
          cube.rotation[axis] += dir * Math.PI / 2 * (rot.k - rot.oldK);

          e.set(0, 0, 0, order);
          if (axis === 'x') e.x = dir * Math.PI / 2 * (rot.k - rot.oldK);
          if (axis === 'y') e.y = dir * Math.PI / 2 * (rot.k - rot.oldK);
          if (axis === 'z') e.z = dir * Math.PI / 2 * (rot.k - rot.oldK);
          cube.center.applyEuler(e);
        }
      }
      rot.oldK = rot.k;
    }

    function animateRotation(startTime: number, duration: number, rotationFn: () => void) {
      const currentTime = performance.now();
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Quartic ease in-out
      const eased = progress < 0.5
        ? 8 * progress * progress * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 4) / 2;

      rot.k = eased;
      rotationFn();

      if (progress < 1) {
        return true; // Continue animation
      } else {
        // Cleanup after rotation
        cubes.forEach(cube => cube.center.round());
        rot.k = 0;
        rot.oldK = 0;
        return false; // Animation complete
      }
    }

    let currentRotationFn: (() => void) | null = null;
    let rotationStartTime = 0;
    const rotationDuration = 700;
    const delayBetweenRotations = 500;

    function startNewRotation() {
      if (!isRotating) {
        isRotating = true;
        rot.k = 0;
        rot.oldK = 0;
        currentRotationFn = rotations[Math.floor(rotations.length * Math.random())];
        rotationStartTime = performance.now();
      }
    }

    function scheduleNextRotation() {
      rotationTimeout = setTimeout(startNewRotation, delayBetweenRotations);
    }

    startNewRotation();

    const render = () => {
      if (isRotating && currentRotationFn) {
        const continueAnimation = animateRotation(rotationStartTime, rotationDuration, currentRotationFn);
        if (!continueAnimation) {
          isRotating = false;
          currentRotationFn = null;
          scheduleNextRotation();
        }
      }

      group.rotation.y += 0.002;

      renderer.render(scene, camera);
      animationFrameId = requestAnimationFrame(render);
    };

    const onWindowResize = () => {
      if (currentMount) {
        const width = currentMount.clientWidth;
        const height = currentMount.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
      }
    };

    window.addEventListener('resize', onWindowResize, false);
    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      clearTimeout(rotationTimeout);
      window.removeEventListener('resize', onWindowResize);
      if (currentMount && renderer.domElement) {
        currentMount.removeChild(renderer.domElement);
      }
      scene.remove(group);
      cubes.forEach(cube => {
        cube.geometry.dispose();
        if (Array.isArray(cube.material)) {
          cube.material.forEach(m => m.dispose());
        } else {
          cube.material.dispose();
        }
      });
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: 10,
      }}
    />
  );
};

export default SolverOrb;
