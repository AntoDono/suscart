# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a React + TypeScript + Vite frontend project for "edgecart" - a landing page featuring layered interactive visual effects combining WebGL shaders, 3D particle systems, and glassmorphic UI components. The page showcases multiple rendering technologies stacked in z-index layers.

## Development Commands

```bash
# Start development server with HMR
npm run dev

# Build for production (runs TypeScript compiler first, then Vite build)
npm run build

# Lint code with ESLint
npm run lint

# Preview production build locally
npm run preview
```

## Architecture Overview

The application uses a layered rendering approach with three primary z-index layers:

1. **Background Layer (z-index: 0)** - Balatro WebGL shader background
2. **3D Canvas Layer (z-index: 1)** - React Three Fiber particle sphere
3. **UI Layer (z-index: 2-3)** - Glass panels and logo loops

### Entry Point Flow

`main.tsx` sets up the complete page layout with:
- Balatro shader background at z-index 0
- React Three Fiber Canvas containing Experience component at z-index 1
- SimpleGlass panels (left/right) at z-index 2
- LogoLoop components (top/bottom) and text overlays at z-index 3

## Key Technologies

### 3D Rendering Stack
- **React Three Fiber (R3F)**: React renderer for Three.js
- **@react-three/drei**: Helper components (not currently used, but available)
- **@react-three/postprocessing**: Bloom effect for particle glow
- **Three.js v0.158.0**: Core 3D engine
- **simplex-noise**: Procedural noise for particle distortion effects

### WebGL Stack
- **OGL (Open Graphics Library)**: Minimal WebGL library for Balatro shader
- Custom GLSL fragment/vertex shaders for procedural effects

### UI Stack
- **Framer Motion**: Animation library (installed but not actively used in main flow)
- **React Icons**: Icon components (RiAnthropicFill used)

## Component Architecture

### 3D Components

**Experience.tsx** (`src/Experience.tsx`)
- Container for R3F scene
- Implements subtle mouse-based camera rotation using lerp
- Provides directional and ambient lighting for particles
- Contains SparklingSphereR3F component in a rotating group

**SparklingSphereR3F** (`src/components/SparklingSphereR3F.tsx`)
- 1000+ particle sphere with mouse interaction physics
- Uses `useFrame` hook for animation loop (runs every frame)
- Key features:
  - Raycasting for 3D mouse position on Z=0 plane
  - Velocity-based physics with damping and return forces
  - Simplex noise for natural "breathing" motion
  - Dynamic color transitions through multi-color palettes
  - Secondary particle emission on mouse interaction (3% probability, 1s cooldown)
- Performance: All particles created at initialization, geometry/material reused via clones
- Props: `radius`, `particleCount`, `interactionRadius`, `dispersalForce`, `returnForce`, `dampingFactor`, `rotationSpeed`, `maxRepelDistance`

**Color System**:
- baseColors: [Light mint #CCFFBD, Aqua mint #AAF0D1, Mint green #7ECA9C]
- repelColors: [Brightest mint #CCFFBD, Mid mint #7ECA9C, Dark space purple #1C1427]
- Colors transition based on distortion amount and distance from origin

**Canvas Configuration** (in main.tsx):
- ACESFilmicToneMapping (value: 3)
- sRGBEncoding (value: 3)
- Adaptive DPR [1, 2]
- 45° FOV, camera at [0, 0, 6]
- 8x multisampling for antialiasing
- Bloom: intensity 2.0, luminanceThreshold 0.2, luminanceSmoothing 0.9, mipmapBlur enabled

### WebGL Shader Components

**Balatro** (`src/components/Balatro.tsx`)
- Full-screen WebGL shader background using OGL
- Custom GLSL fragment shader with procedural swirl/spiral effect
- Mouse interaction: X-position influences spin speed
- Props for extensive visual customization:
  - Colors: `color1`, `color2`, `color3` (hex to vec4 conversion)
  - Motion: `spinRotation`, `spinSpeed`, `spinAmount`, `spinEase`
  - Rendering: `pixelFilter`, `contrast`, `lighting`
  - Interaction: `isRotate` (auto-rotation), `mouseInteraction`
- Uses OGL's minimal renderer (not Three.js)
- Handles resize events and cleanup properly

### UI Components

**SimpleGlass** (`src/components/SimpleGlass.tsx`)
- Glassmorphic container with backdrop-filter blur
- Props: `width`, `height`, `borderRadius`, `style`
- CSS handles glass effect (see SimpleGlass.css)

**LogoLoop** (`src/components/LogoLoop.tsx`)
- Infinite horizontal scrolling logo carousel
- Supports both image logos and React node logos
- Features:
  - Smooth velocity-based animation with easing
  - Auto-calculates copies needed based on container width
  - ResizeObserver for responsive behavior
  - Image loading detection before animation starts
  - Optional pause on hover, fade-out edges, scale on hover
- Props: `logos`, `speed`, `direction`, `width`, `logoHeight`, `gap`, `pauseOnHover`, `fadeOut`, `fadeOutColor`, `scaleOnHover`
- Performance: Uses translate3d for GPU acceleration, requestAnimationFrame for smooth animation

### Other Components

The following components exist in `src/components/` but are not used in the current main.tsx flow:
- `Aurora.tsx` - Alternative background effect
- `IridescenceBackground.tsx` - Another background variant
- `RippleGrid.tsx` - Grid-based ripple effect
- `CurvedLoop.tsx` - Variant of LogoLoop
- `GlassSurface.tsx`, `GlassForm.tsx` - Glass effect variants
- `LoginPanel.tsx` - Login UI (not currently shown)
- `Design.tsx`, `FramerSparklingSphere.tsx`, `follower.tsx`, `particle.tsx` - Experimental components

## Layout Structure

The main.tsx layout uses fixed positioning with calculated offsets:

```
├── Balatro (fullscreen background, z-index 0)
├── Canvas (fullscreen 3D scene, z-index 1)
│   └── Experience
│       └── SparklingSphereR3F
├── SimpleGlass Left (450x650px, left: 4rem, z-index 2)
├── SimpleGlass Right (450x650px, right: 4rem, z-index 2)
├── LogoLoop Top (title, z-index 3)
│   - Position: top: calc(50% - 325px), left/right: calc(4rem + 450px)
├── LogoLoop Bottom (tech logos, z-index 3)
│   - Position: bottom: calc(50% - 325px), left/right: calc(4rem + 450px)
└── Text overlays (subtitle, "made with", z-index 3)
```

Typography: "Geist Mono" monospace font, lowercase styling throughout

## Important Implementation Notes

### Performance Considerations
- SparklingSphereR3F: useFrame runs every frame - be careful with heavy operations
- Particle emission is throttled (3% probability, 1s cooldown)
- All particles created once at initialization
- Geometry/materials reused via cloning
- Canvas uses adaptive DPR for performance
- LogoLoop uses translate3d for GPU acceleration

### Shader Performance (Balatro)
- Pixel filtering reduces resolution for performance (`pixelFilter` prop)
- Uses OGL's minimal renderer for better performance than Three.js
- Proper cleanup on unmount (canvas removal, context loss)

### TypeScript Notes
- Strict mode enabled
- All components properly typed with interfaces
- Material types often need `instanceof` checks before property access

## Project Structure Notes

- `sparkling-sphere/` subdirectory is a duplicate/experimental version with its own node_modules
- `App.tsx` exists but is unused (default Vite template)
- Main entry directly renders the layout in `main.tsx`, not through App.tsx
- Each component typically has an accompanying CSS file for styles
