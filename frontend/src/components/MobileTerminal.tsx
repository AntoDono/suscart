import React from 'react';
import FaultyTerminal from './FaultyTerminal';
import CustomerLogin from './CustomerLogin';
import './MobileTerminal.css';

const MobileTerminal = () => {
  return (
    <div className="mobile-terminal">
      <FaultyTerminal
        scale={0.5}
        gridMul={[1, 1]}
        digitSize={1}
        flickerAmount={0.5}
        noiseAmp={0.1}
        chromaticAberration={1}
        curvature={0.1}
        tint="#00ff00"
        mouseReact={false}
        pageLoadAnimation={true}
        brightness={0.8}
      />

      {/* Mobile Login Container */}
      <div className="mobile-login-container">
        {/* Header */}
        <div className="mobile-header">
          <img src="/edgecart.png" alt="edgecart" className="mobile-logo" />
          <p className="mobile-subtitle">finding alpha in grocery arbitrage</p>
        </div>

        {/* Login Component */}
        <div className="mobile-login">
          <CustomerLogin />
        </div>

        {/* Footer */}
        <div className="mobile-footer">
          <p>made at hackprinceton with ♥︎</p>
        </div>
      </div>
    </div>
  );
};

export default MobileTerminal;
