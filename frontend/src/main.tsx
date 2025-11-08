import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './App.css'
import Experience from './Experience'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import Balatro from './components/Balatro'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <div style={{ width: '100vw', height: '100vh', position: 'fixed', top: 0, left: 0, backgroundColor: '#000000' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0 }}>
        <Balatro
          isRotate={false}
          mouseInteraction={true}
          pixelFilter={6969}
          color1="#000000"
          color2="#2a382aff"
          color3="#0d0d0dff"
          spinRotation={-2.0}
          spinSpeed={7.0}
          contrast={1.5}
          lighting={0.4}
          spinAmount={0.25}
          spinEase={1.0}
        />
      </div>
      <div style={{
        position: 'fixed',
        top: '50%',
        left: '8%',
        transform: 'translateY(-50%)',
        fontSize: '8rem',
        fontWeight: 100,
        color: '#FFFFFF',
        zIndex: 2,
        fontFamily: '"Geist", sans-serif',
        letterSpacing: '-0.02em',
        textShadow: '0 0 40px rgba(255, 255, 255, 0.3)',
      }}>
        EDGE
      </div>
      <div style={{
        position: 'fixed',
        top: '50%',
        right: '8%',
        transform: 'translateY(-50%)',
        fontSize: '8rem',
        fontWeight: 100,
        color: '#FFFFFF',
        zIndex: 2,
        fontFamily: '"Geist", sans-serif',
        letterSpacing: '-0.02em',
        textShadow: '0 0 40px rgba(255, 255, 255, 0.3)',
      }}>
        CART
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
