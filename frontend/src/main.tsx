import { StrictMode, useState, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './App.css'
import Experience from './Experience'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import Balatro from './components/Balatro'
import FaultyTerminal from './components/FaultyTerminal'
import GradualBlur from './components/GradualBlur'
import LogoLoop from './components/LogoLoop'
import AdminLogin from './components/AdminLogin'
import CustomerLogin from './components/CustomerLogin'
import { RiAnthropicFill } from "react-icons/ri"

function App() {
  const [currentPage, setCurrentPage] = useState(window.location.hash);

  useEffect(() => {
    const handleHashChange = () => {
      setCurrentPage(window.location.hash);
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Admin page
  if (currentPage === '#admin') {
    return (
      <div style={{ width: '100vw', height: '100vh', backgroundColor: '#000000' }}>
        {/* Admin page content */}
      </div>
    );
  }

  // User page
  if (currentPage === '#user') {
    return (
      <div style={{ width: '100vw', height: '100vh', backgroundColor: '#000000' }}>
        {/* User page content */}
      </div>
    );
  }

  // Landing page
  return (
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

      {/* Title Loop - Top Center */}
      <div style={{
        position: 'fixed',
        top: 'calc(50% - 325px)',
        left: '550px',
        right: '550px',
        zIndex: 3,
      }}>
        <LogoLoop
          logos={[
            { node: <img src="/edgecart.png" alt="edgecart" style={{ filter: 'brightness(0) invert(1)', transform: 'translateY(3px)' }} /> },
            { node: <span style={{ fontFamily: '"Geist Mono", monospace', fontWeight: 100, color: '#ffffff' }}>✦</span> },
            { node: <img src="/edgecart.png" alt="edgecart" style={{ filter: 'brightness(0) invert(1)', transform: 'translateY(3px)' }} /> },
            { node: <span style={{ fontFamily: '"Geist Mono", monospace', fontWeight: 100, color: '#ffffff' }}>✦</span> },
          ]}
          speed={50}
          direction="left"
          logoHeight={40}
          gap={48}
          pauseOnHover={false}
          fadeOut={true}
        />
      </div>

      {/* Subtitle - Below Title */}
      <div style={{
        position: 'fixed',
        top: 'calc(50% - 325px + 50px)',
        left: '550px',
        right: '550px',
        zIndex: 3,
        display: 'flex',
        justifyContent: 'center',
      }}>
        <p style={{ fontFamily: '"Geist Mono", monospace', fontWeight: 100, fontSize: '1rem', color: '#ffffff', textTransform: 'lowercase', margin: 0, opacity: 0.7 }}>
          finding alpha in grocery arbitrage
        </p>
      </div>

      {/* Dither Container - Left Side (Admin) */}
      <div style={{
        position: 'fixed',
        left: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 2,
        width: '550px',
        height: '100vh',
        overflow: 'hidden',
        maskImage: 'linear-gradient(to left, transparent 0%, black 25%, black 100%)',
        WebkitMaskImage: 'linear-gradient(to left, transparent 0%, black 25%, black 100%)',
      }}>
        <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
          <FaultyTerminal
            scale={2.3}
            gridMul={[1, 1]}
            digitSize={1.8}
            timeScale={1.8}
            pause={false}
            scanlineIntensity={0.7}
            glitchAmount={1}
            flickerAmount={1}
            noiseAmp={1}
            chromaticAberration={0}
            dither={0}
            curvature={0.2}
            tint="#7ECA9C"
            mouseReact={false}
            mouseStrength={0}
            pageLoadAnimation={true}
            brightness={0.6}
          />
        </div>
        <div style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', width: '420px', height: '650px', zIndex: 1, left: '3rem' }}>
          <AdminLogin />
        </div>
      </div>

      {/* Dither Container - Right Side (Customer) */}
      <div style={{
        position: 'fixed',
        right: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 2,
        width: '550px',
        height: '100vh',
        overflow: 'hidden',
        maskImage: 'linear-gradient(to right, transparent 0%, black 25%, black 100%)',
        WebkitMaskImage: 'linear-gradient(to right, transparent 0%, black 25%, black 100%)',
      }}>
        <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
          <FaultyTerminal
            scale={2.3}
            gridMul={[1, 1]}
            digitSize={1.8}
            timeScale={1.8}
            pause={false}
            scanlineIntensity={0.7}
            glitchAmount={1}
            flickerAmount={1}
            noiseAmp={1}
            chromaticAberration={0}
            dither={0}
            curvature={0.2}
            tint="#7ECA9C"
            mouseReact={false}
            mouseStrength={0}
            pageLoadAnimation={true}
            brightness={0.6}
          />
        </div>
        <div style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', width: '420px', height: '650px', zIndex: 1, right: '3rem' }}>
          <CustomerLogin />
        </div>
      </div>

      {/* Page-level blur overlays - flat across entire page */}
      <GradualBlur
        target="page"
        position="top"
        height="80px"
        strength={5}
        curve="ease-out"
        divCount={8}
        opacity={0.35}
        zIndex={999}
      />
      <GradualBlur
        target="page"
        position="bottom"
        height="80px"
        strength={5}
        curve="ease-out"
        divCount={8}
        opacity={0.35}
        zIndex={999}
      />

      {/* Made With - Above Logo Loop */}
      <div style={{
        position: 'fixed',
        bottom: 'calc(50% - 325px + 50px)',
        left: '550px',
        right: '550px',
        zIndex: 3,
        display: 'flex',
        justifyContent: 'center',
      }}>
        <p style={{ fontFamily: '"Geist Mono", monospace', fontWeight: 100, fontSize: '1rem', color: '#ffffff', textTransform: 'lowercase', margin: 0, opacity: 0.7 }}>
          made at hackprinceton with ♥︎ using
        </p>
      </div>

      {/* LogoLoop - Bottom Center */}
      <div style={{
        position: 'fixed',
        bottom: 'calc(50% - 325px)',
        left: '550px',
        right: '550px',
        zIndex: 3,
      }}>
        <LogoLoop
          logos={[
            { node: <RiAnthropicFill style={{ color: '#ffffff' }} /> },
            { node: <span style={{ fontFamily: '"Geist Mono", monospace', fontWeight: 100, color: '#ffffff' }}>✦</span> },
            { node: <RiAnthropicFill style={{ color: '#ffffff' }} /> },
            { node: <span style={{ fontFamily: '"Geist Mono", monospace', fontWeight: 100, color: '#ffffff' }}>✦</span> },
          ]}
          speed={50}
          direction="right"
          logoHeight={40}
          gap={48}
          pauseOnHover={false}
          fadeOut={true}
        />
      </div>

      <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 1 }}>
        <Canvas
          style={{ width: '100%', height: '100%', pointerEvents: 'auto' }}
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
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
