// @ts-nocheck
import { useFrame, useThree } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import { createNoise3D } from 'simplex-noise';
import { Sparkles } from "@react-three/drei";
// Helper to convert Vector3 array to Float32Array
const vectorsToFloat32Array = ( vectors: THREE.Vector3[] ) => {
    const array = new Float32Array( vectors.length * 3 );
    vectors.forEach( ( vector, i ) => {
        array[ i * 3 ] = vector.x;
        array[ i * 3 + 1 ] = vector.y;
        array[ i * 3 + 2 ] = vector.z;
    } );
    return array;
};
const noise = createNoise3D( Math.random )
const pointPos = ( count ) => {
    const points = [];
    for ( let i = 0; i < count; i++ ) {
        points.push( new THREE.Vector3( Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5 ) )
    }
    return points
}
const g = new THREE.BufferGeometry()
g.setAttribute( 'position', new THREE.BufferAttribute( vectorsToFloat32Array( pointPos( 100 ) ), 3 ) )
const m = new THREE.Mesh( g, new THREE.PointsMaterial( { color: 0xffffff } ) )
const pointsTrail = new THREE.Points( g, new THREE.PointsMaterial( { color: 0xffffff } ) )
const animatePoint = ( position: THREE.Vector3, trailLength: number ) => {
    const points = [];
    const emitterDelay = 0.1;
    for ( let i = 0; i < trailLength; i++ ) {
        const offset = i / trailLength;
        const delay = emitterDelay * ( 1 - offset );
        const point = position.clone();
        point.multiplyScalar( 1 - offset );
        // add noise
        const noiseValue = noise( point.x, point.y, point.z );
        point.addScalar( noiseValue * 0.05 );
        points.push( point );
    }
    return points;
}
function createSphereLayer( radius: number, particleCount: number, isInner: boolean ) {
    const geometry = new THREE.BufferGeometry();
    const positions: THREE.Vector3[] = [];
    const colors = new Float32Array( particleCount * 3 );
    const rotationAxes: THREE.Vector3[] = [];
    const rotationSpeeds = new Float32Array( particleCount );
    const sizes = new Float32Array( particleCount );
    const color = new THREE.Color();
    const baseRadius = 0.1;



    const colorPalette = [
        [ 0.34, 0.53, 0.96 ],
        [ 0.24, 0.453, 0.96 ],
        [ 0.34, 0.53, 0.96 ],
    ];

    for ( let i = 0; i < particleCount; i++ ) {
        // Create position on sphere surface
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos( 2 * Math.random() - 1 );
        const x = baseRadius * Math.sin( phi ) * Math.cos( theta );
        const y = baseRadius * Math.sin( phi ) * Math.sin( theta );
        const z = baseRadius * Math.cos( phi );

        positions.push( new THREE.Vector3( x, y, z ) );

        // Create random rotation axis
        const axisTheta = Math.random() * Math.PI * 2;
        const axisPhi = Math.acos( 2 * Math.random() - 1 );
        rotationAxes.push( new THREE.Vector3(
            Math.sin( axisPhi ) * Math.cos( axisTheta ),
            Math.sin( axisPhi ) * Math.sin( axisTheta ),
            Math.cos( axisPhi )
        ).normalize() );

        // Set random rotation speed
        rotationSpeeds[ i ] = ( Math.random() * 0.5 + 0.5 ) * ( isInner ? 1 : -1 );

        // Set colors
        const colorIndex = Math.floor( Math.random() * colorPalette.length );
        const [ r, g, b ] = colorPalette[ colorIndex ];
        color.setRGB(
            r + ( Math.random() - 0.5 ) * 0.1,
            g + ( Math.random() - 0.5 ) * 0.1,
            b + ( Math.random() - 0.5 ) * 0.1
        );

        const i3 = i * 3;
        colors[ i3 ] = color.r;
        colors[ i3 + 1 ] = color.g;
        colors[ i3 + 2 ] = color.b;

        sizes[ i ] = Math.random() * radius;
    }

    // Convert positions to buffer attribute
    geometry.setAttribute(
        'position',
        new THREE.BufferAttribute( vectorsToFloat32Array( positions ), 3 )
    );
    geometry.setAttribute( 'color', new THREE.BufferAttribute( colors, 3 ) );
    geometry.setAttribute( 'rotationAxis',
        new THREE.BufferAttribute( vectorsToFloat32Array( rotationAxes ), 3 )
    );
    geometry.setAttribute( 'rotationSpeed',
        new THREE.BufferAttribute( rotationSpeeds, 1 )
    );

    geometry.setAttribute( 'size', new THREE.BufferAttribute( sizes, 1 ) );

    const material = new THREE.ShaderMaterial( {
        uniforms: {
            time: { value: 0.0 },
            mouse: { value: new THREE.Vector2() }
        },
        vertexShader: `
      attribute vec3 rotationAxis;
      attribute float rotationSpeed;
      varying vec3 vColor;
      uniform float time;
      uniform vec2 mouse;

      mat3 rotationMatrix(vec3 axis, float angle) {
        axis = normalize(axis);
        float s = sin(angle);
        float c = cos(angle);
        float oc = 1.0 - c;
        
        return mat3(
          oc * axis.x * axis.x + c,           oc * axis.x * axis.y - axis.z * s,  oc * axis.z * axis.x + axis.y * s,
          oc * axis.x * axis.y + axis.z * s,  oc * axis.y * axis.y + c,           oc * axis.y * axis.z - axis.x * s,
          oc * axis.z * axis.x - axis.y * s,  oc * axis.y * axis.z + axis.x * s,  oc * axis.z * axis.z + c
        );
      }

      void main() {
        vColor = color;
        
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vec4 projectedPosition = projectionMatrix * mvPosition;
        
        // Normalize the w component to prevent perspective scaling
        // projectedPosition.xyz /= projectedPosition.w;
        // projectedPosition.w = 1.0;
        
        gl_Position = projectedPosition;
        gl_PointSize = 1.5;
      }
    `,
        fragmentShader: `
      varying vec3 vColor;

      void main() {
        vec2 xy = gl_PointCoord.xy - vec2(0.5);
        float radius = length(xy);
        float alpha = smoothstep(0.5, 0.45, radius);
        gl_FragColor = vec4(vColor, alpha * 0.8);
      }
    `,
        transparent: true,
        vertexColors: true,
        verticesNeedUpdate: true
    } );

    return new THREE.Points( geometry, material );
}


export const MouseFollower = ( {
    radius = 0.1,
} ) => {
    const meshRef = useRef<THREE.Points>();
    const points = createSphereLayer( 0.2, 2000, false );
    const { raycaster, pointer, camera } = useThree();
    const raycastPlane = new THREE.Plane( new THREE.Vector3( 0, 0, 1 ), 0 );
    const intersection = new THREE.Vector3();

    useFrame( ( { clock } ) => {
        if ( !meshRef.current ) return;

        // Update raycaster with current pointer
        raycaster.setFromCamera( pointer, camera );

        // Get intersection point with plane
        raycaster.ray.intersectPlane( raycastPlane, intersection );

        if ( intersection ) {
            // Update mesh position to follow intersection point
            meshRef.current.position.copy( intersection );
        }

        const elapsedTime = clock.getElapsedTime();

        const positions = points.geometry.attributes.position.array as number[];
        const rotationAxes = points.geometry.attributes.rotationAxis.array as number[];
        for ( let i = 0; i < positions.length; i += 3 ) {
            const x = positions[ i ];
            const y = positions[ i + 1 ];
            const z = positions[ i + 2 ];

            const vec = new THREE.Vector3( x, y, z );
            const axis = new THREE.Vector3(
                rotationAxes[ i ],
                rotationAxes[ i + 1 ],
                rotationAxes[ i + 2 ]
            );
            vec.applyAxisAngle( axis, elapsedTime * 0.5 ); // Adjust rotation speed here
            const n = noise( vec.x, vec.y, vec.z );

            // add noise so the orbiting sphere is more interesting
            positions[ i ] = vec.x + n * 0.01;
            positions[ i + 1 ] = vec.y + n * 0.01;
            positions[ i + 2 ] = vec.z + n * 0.01;
        }
        points.geometry.attributes.position.needsUpdate = true;
    } );

    return (
        <group ref={ meshRef }>
            <Sparkles
                size={ 1.1 }
                color={
                    'red'
                }
            ></Sparkles>
            <primitive object={ points } />;
        </group>
    )
};