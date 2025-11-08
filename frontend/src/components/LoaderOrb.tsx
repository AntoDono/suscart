import { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { SimplexNoise } from 'three/examples/jsm/math/SimplexNoise.js';

const LoaderOrb = () => {
  const mountRef = useRef(null);

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
    camera.position.set(0, 0, 15);
    camera.lookAt(scene.position);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(currentMount.clientWidth, currentMount.clientHeight);
    currentMount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const shaderMaterial = {
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
    };

    const tori = [];
    const numRings = 5;
    const baseRadius = 1.2;
    const radiusStep = 0.3;
    const tubeThickness = 0.06;

    for (let i = 0; i < numRings; i++) {
      const radius = baseRadius + i * radiusStep;
      const geometry = new THREE.TorusGeometry(radius, tubeThickness, 16, 100);

      // Store original positions for distortion
      const positions = geometry.getAttribute('position');
      geometry.userData.originalPositions = new Float32Array(positions.array);

      const material = new THREE.ShaderMaterial({
        uniforms: THREE.UniformsUtils.clone(shaderMaterial.uniforms),
        vertexShader: shaderMaterial.vertexShader,
        fragmentShader: shaderMaterial.fragmentShader,
        transparent: shaderMaterial.transparent,
        depthWrite: shaderMaterial.depthWrite,
        side: THREE.DoubleSide,
      });

      const torus = new THREE.Mesh(geometry, material);

      // Random initial rotation
      torus.rotation.x = Math.random() * Math.PI * 2;
      torus.rotation.y = Math.random() * Math.PI * 2;
      torus.rotation.z = Math.random() * Math.PI * 2;

      // Random rotation speeds
      torus.userData.rotSpeed = new THREE.Vector3(
        (Math.random() - 0.5) * 0.02,
        (Math.random() - 0.5) * 0.02,
        (Math.random() - 0.5) * 0.02
      );

      group.add(torus);
      tori.push(torus);
    }

    const noise = new SimplexNoise();
    let animationFrameId;

    const modulate = (val, minVal, maxVal, outMin, outMax) => {
      const fr = (val - minVal) / (maxVal - minVal);
      const delta = outMax - outMin;
      return outMin + fr * delta;
    };

    const distortMesh = (mesh, bassFr, treFr) => {
      const vertices = mesh.geometry.getAttribute('position');
      const originalPositions = mesh.geometry.userData.originalPositions;
      const time = window.performance.now();

      const rf1 = 0.00001, rf2 = 0.00008;
      const amp1 = 2, amp2 = 0.5;

      for (let i = 0; i < vertices.count; i++) {
        const origX = originalPositions[i * 3];
        const origY = originalPositions[i * 3 + 1];
        const origZ = originalPositions[i * 3 + 2];

        const origLength = Math.sqrt(origX * origX + origY * origY + origZ * origZ);
        if (origLength === 0) continue;

        const nx = origX / origLength;
        const ny = origY / origLength;
        const nz = origZ / origLength;

        const noiseVal1 = noise.noise3d(
          nx + time * rf1 * 7,
          ny + time * rf1 * 8,
          nz + time * rf1 * 9
        );
        const noiseVal2 = noise.noise3d(
          nx + time * rf2 * 5,
          ny + time * rf2 * 6,
          nz + time * rf2 * 7
        );

        const distortion = (noiseVal1 * amp1 * treFr + noiseVal2 * amp2 * treFr) * 0.1;
        const distance = origLength + bassFr * 0.1 + distortion;

        vertices.setXYZ(i, nx * distance, ny * distance, nz * distance);
      }
      vertices.needsUpdate = true;
      mesh.geometry.computeVertexNormals();
    };

    const render = () => {
      // Idle animation with sine waves
      const time = performance.now() * 0.001;
      const bassFr = modulate(Math.sin(time * 0.5) * 0.5 + 0.5, 0, 1, 0.1, 0.3);
      const treFr = modulate(Math.sin(time * 0.8) * 0.5 + 0.5, 0, 1, 0.1, 0.3);

      tori.forEach(torus => {
        torus.rotation.x += torus.userData.rotSpeed.x;
        torus.rotation.y += torus.userData.rotSpeed.y;
        torus.rotation.z += torus.userData.rotSpeed.z;
        distortMesh(torus, bassFr, treFr);
      });

      group.rotation.x += 0.001;

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
      window.removeEventListener('resize', onWindowResize);
      if (currentMount && renderer.domElement) {
        currentMount.removeChild(renderer.domElement);
      }
      scene.remove(group);
      tori.forEach(torus => {
        torus.geometry.dispose();
        torus.material.dispose();
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

export default LoaderOrb;
