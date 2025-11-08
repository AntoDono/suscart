import { SparklingSphereR3F } from './components/SparklingSphereR3F'
import { useFrame } from '@react-three/fiber'
import { useRef, useState, useEffect } from 'react'
import * as THREE from 'three'

export default function Experience() {
  const [key, setKey] = useState(0)

  // Force remount on initial load to fix particle initialization
  useEffect(() => {
    setKey(1)
  }, [])
  const targetRotation = useRef(new THREE.Vector2(0, 0))
  const currentRotation = useRef(new THREE.Vector2(0, 0))
  const groupRef = useRef<THREE.Group>(null)

  useFrame((state) => {
    // More dramatic movement based on mouse position
    targetRotation.current.x = state.mouse.y * 0.8
    targetRotation.current.y = state.mouse.x * 0.8

    // Smooth lerp
    currentRotation.current.x += (targetRotation.current.x - currentRotation.current.x) * 0.08
    currentRotation.current.y += (targetRotation.current.y - currentRotation.current.y) * 0.08

    if (groupRef.current) {
      groupRef.current.rotation.x = currentRotation.current.x
      groupRef.current.rotation.y = currentRotation.current.y
    }
  })

  return (
    <group ref={groupRef}>
      <directionalLight position={ [ 1, 2, 3 ] } intensity={ 1.5 } />
      <ambientLight intensity={ 0.5 } />
      <SparklingSphereR3F key={key} />
    </group>
  )
}
