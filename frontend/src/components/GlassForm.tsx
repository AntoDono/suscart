import { useEffect, useRef } from 'react';
import './GlassForm.css';

interface GlassFormProps {
  title?: string;
  buttonText?: string;
}

export default function GlassForm({ title = "Login", buttonText = "log in" }: GlassFormProps) {
  const glassRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = glassRef.current;
    if (!element) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = element.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const specular = element.querySelector('.glass-specular') as HTMLElement;
      if (specular) {
        specular.style.background = `radial-gradient(
          circle at ${x}px ${y}px,
          rgba(255,255,255,0.05) 0%,
          rgba(255,255,255,0.02) 30%,
          rgba(255,255,255,0) 60%
        )`;
      }
    };

    const handleMouseLeave = () => {
      const specular = element.querySelector('.glass-specular') as HTMLElement;
      if (specular) {
        specular.style.background = 'none';
      }
    };

    element.addEventListener('mousemove', handleMouseMove);
    element.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      element.removeEventListener('mousemove', handleMouseMove);
      element.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return (
    <div className="glass-form" ref={glassRef}>
      <div className="glass-filter"></div>
      <div className="glass-overlay"></div>
      <div className="glass-specular"></div>
      <div className="glass-content">
        <h3>{title}</h3>

        <div className="video-container">
          {/* Video placeholder */}
        </div>

        <div className="terminal-container">
          <div className="terminal-content">
            {/* Terminal content */}
          </div>
        </div>

        <button type="submit" className="login-button">{buttonText}</button>
      </div>
    </div>
  );
}
