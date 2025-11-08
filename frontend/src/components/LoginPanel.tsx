import { useEffect, useRef } from 'react';
import './LoginPanel.css';

interface LoginPanelProps {
  title: string;
  buttonText?: string;
}

export default function LoginPanel({ title, buttonText = "log in" }: LoginPanelProps) {
  const glassRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const currentRef = glassRef.current;
    if (!currentRef) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = currentRef.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const specular = currentRef.querySelector('.glass-specular') as HTMLElement;
      if (specular) {
        specular.style.background = `radial-gradient(
          circle at ${x}px ${y}px,
          rgba(255,255,255,0.15) 0%,
          rgba(255,255,255,0.05) 30%,
          rgba(255,255,255,0) 60%
        )`;
      }
    };

    const handleMouseLeave = () => {
      const specular = currentRef.querySelector('.glass-specular') as HTMLElement;
      if (specular) {
        specular.style.background = 'none';
      }
    };

    currentRef.addEventListener('mousemove', handleMouseMove);
    currentRef.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      currentRef.removeEventListener('mousemove', handleMouseMove);
      currentRef.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return (
    <div className="glass-card login-panel" ref={glassRef}>
      <div className="glass-filter"></div>
      <div className="glass-distortion-overlay"></div>
      <div className="glass-overlay"></div>
      <div className="glass-specular"></div>
      <div className="glass-content">
        <h2 className="login-panel-title">{title}</h2>

        <div className="login-panel-video-container">
          {/* Video placeholder */}
        </div>

        <div className="login-panel-terminal">
          <div className="terminal-content">
            {/* Terminal content */}
          </div>
        </div>

        <button className="login-panel-button">{buttonText}</button>
      </div>
    </div>
  );
}
