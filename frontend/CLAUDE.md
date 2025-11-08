# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a React + TypeScript + Vite frontend project featuring an interactive 3D particle sphere visualization using React Three Fiber (R3F). The main feature is the SparklingSphereR3F component, which creates a dynamic sphere made of particles that react to mouse interaction with physics-based dispersal, color transitions, and particle emission effects.

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

## Architecture

### Entry Point Flow
- `main.tsx` → Sets up React Three Fiber Canvas with postprocessing effects (Bloom)
- `Experience.tsx` → Scene container with OrbitControls and lighting setup
- `SparklingSphereR3F.tsx` → Main interactive particle sphere component

### Key Components

**SparklingSphereR3F** (`src/components/SparklingSphereR3F.tsx`)
- Core interactive component with 1000+ individual particle meshes
- Uses `useFrame` hook for animation loop and physics updates
- Implements custom particle system with:
  - Mouse-based raycasting for 3D interaction
  - Velocity-based physics with damping and return forces
  - Dynamic color transitions through multiple color palettes
  - Secondary particle emission on collision
- Key props: `radius`, `particleCount`, `interactionRadius`, `dispersalForce`, `returnForce`, `dampingFactor`, `rotationSpeed`, `maxRepelDistance`

**Other Components**
- `Design.tsx`, `FramerSparklingSphere.tsx`, `follower.tsx`, `particle.tsx` - Additional component experiments (not currently active in main flow)

### 3D Stack
- **React Three Fiber**: React renderer for Three.js
- **@react-three/drei**: Helper components (OrbitControls)
- **@react-three/postprocessing**: Post-processing effects (Bloom effect for glow)
- **Three.js v0.158.0**: Core 3D engine
- **simplex-noise**: For potential procedural effects

### Rendering Configuration
- Canvas setup in `main.tsx` includes:
  - ACESFilmicToneMapping (value: 3)
  - sRGBEncoding (value: 3)
  - Adaptive DPR [1, 2] for performance
  - 45° FOV camera at position [0, 0, 6]
  - Multisampling: 8x for antialiasing
  - Bloom postprocessing with intensity 2.0

## Important Implementation Details

### Particle Physics System
- Each particle tracks: position, velocity, originalPosition, baseColor, repelColor, maxDistanceTraveled
- Interaction uses raycasting to project mouse position onto a Z=0 plane in 3D space
- Mouse velocity is calculated and influences particle repulsion direction
- Color transitions through 3-color palettes based on distance traveled from origin
- Forces are distance and speed-dependent with damping

### Performance Considerations
- Particle emission is heavily throttled (10% probability, 0.5s cooldown, 1-2 particles max)
- Geometry reuses IcosahedronGeometry with shared material clones
- All particles created once at initialization, not dynamically
- useFrame updates run every frame - optimize carefully

### Color System
Two coordinated palettes:
- **baseColors**: [Mint green #7ECA9C, Light mint #CCFFBD, Dark purple-grey #40394A]
- **repelColors**: [Light mint #CCFFBD, Mint green #7ECA9C, Dark space purple #1C1427]

## Project Structure Notes

- `sparkling-sphere/` subdirectory appears to be a duplicate/experimental version with identical dependencies
- `App.tsx` exists but is unused (default Vite template)
- Main entry uses `Experience.tsx` directly, not `App.tsx`
