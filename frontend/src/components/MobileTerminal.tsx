import React from 'react';
import { FaGithub } from 'react-icons/fa';
import { SiDevpost } from 'react-icons/si';
import Balatro from './Balatro';
import CustomerLogin from './CustomerLogin';
import './MobileTerminal.css';

const MobileTerminal = () => {
  return (
    <div className="mobile-terminal">
      {/* Balatro Background */}
      <div className="mobile-background">
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

      {/* Top Header */}
      <div className="mobile-top-header">
        <a
          href="https://github.com/AntoDono/edgecart"
          target="_blank"
          rel="noopener noreferrer"
          className="mobile-header-icon"
        >
          <FaGithub />
        </a>

        <span className="mobile-header-spacer">✦</span>

        <div className="mobile-mlh-logo">
          <img src="/mlh.png" alt="MLH" />
        </div>

        <span className="mobile-header-spacer">✦</span>

        <a
          href="https://devpost.com/software/edgecart"
          target="_blank"
          rel="noopener noreferrer"
          className="mobile-header-icon"
        >
          <SiDevpost />
        </a>
      </div>

      {/* Mobile Login Container */}
      <div className="mobile-login-container">
        <CustomerLogin />
        <p className="mobile-footer-text">made with ♥︎ at hackprinceton</p>
      </div>
    </div>
  );
};

export default MobileTerminal;
