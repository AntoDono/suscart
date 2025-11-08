import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './App.css'
import Experience from './Experience'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import Balatro from './components/Balatro'
import GlassForm from './components/GlassForm'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <div style={{ width: '100vw', height: '100vh', position: 'fixed', top: 0, left: 0, backgroundColor: '#000000' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0 }}>
        <Balatro
          isRotate={false}
          mouseInteraction={true}
          pixelFilter={6969}
          color1="#101111ff"
          color2="#2a382aff"
          color3="#000000ff"
          spinRotation={-2.0}
          spinSpeed={7.0}
          contrast={1.5}
          lighting={0.4}
          spinAmount={0.25}
          spinEase={1.0}
        />
      </div>

      {/* Admin Form - Left Side */}
      <div style={{
        position: 'fixed',
        left: '4rem',
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 2,
      }}>
        <GlassForm />
      </div>

      {/* User Form - Right Side */}
      <div style={{
        position: 'fixed',
        right: '4rem',
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 2,
      }}>
        <GlassForm />
      </div>

      <Canvas
        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 1 }}
        gl={{
          antialias: true,
          toneMapping: 3, // ACESFilmicToneMapping
          outputEncoding: 3, // sRGBEncoding
          alpha: true,
        }}
        dpr={[1, 2]}
        camera={{
          fov: 45,
          near: 0.1,
          far: 200,
          position: [0, 0, 6]
        }}
      >
        <Experience />
        <EffectComposer multisampling={8}>
          <Bloom
            intensity={2.0}
            luminanceThreshold={0.2}
            luminanceSmoothing={0.9}
            mipmapBlur
          />
        </EffectComposer>
      </Canvas>
    </div>
  </StrictMode>
)
