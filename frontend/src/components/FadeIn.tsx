import { useEffect, useState } from 'react';
import './FadeIn.css';
import SolverOrb from './SolverOrb';

const FadeIn = () => {
  const [isVisible, setIsVisible] = useState(true);
  const [cubeVisible, setCubeVisible] = useState(true);
  const [shouldRender, setShouldRender] = useState(true);

  useEffect(() => {
    // Fade out cube first at 1.5 seconds
    const cubeTimer = setTimeout(() => {
      setCubeVisible(false);
    }, 1500);

    // Then fade out black overlay at 2.5 seconds
    const overlayTimer = setTimeout(() => {
      setIsVisible(false);
    }, 2500);

    // Remove from DOM completely after fade out completes (2.5s + 2s transition = 4.5s)
    const removeTimer = setTimeout(() => {
      setShouldRender(false);
    }, 4500);

    return () => {
      clearTimeout(cubeTimer);
      clearTimeout(overlayTimer);
      clearTimeout(removeTimer);
    };
  }, []);

  if (!shouldRender) return null;

  return (
    <div className={`fade-in-overlay ${!isVisible ? 'fade-out' : ''}`}>
      {isVisible && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '300px',
          height: '300px',
          opacity: cubeVisible ? 1 : 0,
          transition: 'opacity 0.8s ease-out',
        }}>
          <SolverOrb />
        </div>
      )}
    </div>
  );
};

export default FadeIn;
