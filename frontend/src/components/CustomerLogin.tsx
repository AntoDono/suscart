import { useState, useEffect, useRef } from 'react';
import { AwesomeButton } from 'react-awesome-button';
import 'react-awesome-button/dist/styles.css';
import GradientText from './GradientText';
import LiquidChrome from './LiquidChrome';
import './CustomerLogin.css';

interface TerminalLine {
  text: string;
  timestamp: string;
}

const Terminal = () => {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const showFastfetch = true;
  const bottomRef = useRef<HTMLDivElement>(null);

  const generateTimestamp = () => {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { hour12: false });
  };

  const asciiArt = `....................
.....+++++++*+*+:...
:*##-:+********:....
...+##==*****+-##=:.
...:*##==***==##*-..
....=###+-*=+###+...
.....####+:=*++=:...
.....-#++++++++-....
.......::.:::::.....
......-#*:..=**.....
....................`;

  const systemInfo = [
    { label: 'customer@edgecart', value: '', highlight: true },
    { label: '------------------', value: '', separator: true },
    { label: 'Version', value: 'v2.3.0-stable' },
    { label: 'Session', value: 'Guest Mode' },
    { label: 'Offers', value: '12 deals' },
    { label: 'Savings', value: '$23.50/week' },
    { label: 'Stores', value: '3 nearby' },
    { label: 'Rewards', value: '450 points' },
    { label: 'Alerts', value: 'Active' },
    { label: 'Status', value: 'Ready' },
  ];

  const terminalMessages = [
    'Connecting to edgecart customer portal...',
    'Authentication service: Ready',
    'Loading personalized offers...',
    'Scanning local inventory data...',
    'Fresh produce deals: 12 available',
    'Your saved preferences loaded',
    'Nearby stores: 3 detected',
    'Price comparison active',
    'Freshness notifications enabled',
    'Smart shopping list synced',
    'Weekly savings tracker: $23.50',
    'Waste prevention tips ready',
    'Seasonal recommendations loaded',
    'Loyalty rewards: 450 points',
    'System ready for login',
  ];

  useEffect(() => {
    let messageIndex = 0;

    const addLine = () => {
      const newLine: TerminalLine = {
        text: terminalMessages[messageIndex % terminalMessages.length],
        timestamp: generateTimestamp(),
      };

      setLines(prev => {
        const updated = [...prev, newLine];
        return updated.slice(-15); // Keep more lines visible
      });

      messageIndex++;
    };

    // Wait 3 seconds before first message
    const startTimeout = setTimeout(() => {
      // Add initial lines quickly
      const initialInterval = setInterval(() => {
        if (messageIndex < 3) {
          addLine();
        } else {
          clearInterval(initialInterval);
        }
      }, 800);

      // Then add lines every 2-4 seconds
      const mainInterval = setInterval(() => {
        if (messageIndex >= 3) {
          addLine();
        }
      }, 2000 + Math.random() * 2000);

      return () => {
        clearInterval(initialInterval);
        clearInterval(mainInterval);
      };
    }, 3000);

    return () => {
      clearTimeout(startTimeout);
    };
  }, []);

  useEffect(() => {
    // Auto-scroll to bottom on new message
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  return (
    <div className="terminal">
      <div className="terminal-header">
        <div className="terminal-buttons">
          <span className="terminal-button close"></span>
          <span className="terminal-button minimize"></span>
          <span className="terminal-button maximize"></span>
        </div>
        <div className="terminal-title">customer@edgecart</div>
      </div>
      <div className="terminal-body">
        {showFastfetch && (
          <div className="fastfetch-container">
            <pre className="ascii-art">{asciiArt}</pre>
            <div className="system-info">
              {systemInfo.map((info, index) => (
                <div key={index} className={`info-line ${info.highlight ? 'highlight' : ''} ${info.separator ? 'separator' : ''}`}>
                  {info.label && <span className="info-label">{info.label}</span>}
                  {info.value && <span className="info-value">{info.value}</span>}
                </div>
              ))}
            </div>
          </div>
        )}
        {lines.map((line, index) => (
          <div key={index} className="terminal-line">
            <span className="terminal-timestamp">[{line.timestamp}]</span>
            <span className="terminal-text">{line.text}</span>
          </div>
        ))}
        <div className="terminal-cursor">▊</div>
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

const CustomerLogin = () => {
  const handleLogin = () => {
    // Create fade to black overlay
    const fadeOverlay = document.createElement('div');
    fadeOverlay.style.position = 'fixed';
    fadeOverlay.style.top = '0';
    fadeOverlay.style.left = '0';
    fadeOverlay.style.width = '100vw';
    fadeOverlay.style.height = '100vh';
    fadeOverlay.style.backgroundColor = '#000000';
    fadeOverlay.style.opacity = '0';
    fadeOverlay.style.transition = 'opacity 1s ease-in-out';
    fadeOverlay.style.zIndex = '9999';
    fadeOverlay.style.pointerEvents = 'none';

    document.body.appendChild(fadeOverlay);

    // Trigger fade
    setTimeout(() => {
      fadeOverlay.style.opacity = '1';
    }, 10);

    // Navigate after fade completes
    setTimeout(() => {
      window.location.hash = '#user';
      // Remove overlay after navigation
      setTimeout(() => {
        fadeOverlay.style.opacity = '0';
        setTimeout(() => {
          document.body.removeChild(fadeOverlay);
        }, 1000);
      }, 100);
    }, 1000);
  };

  return (
    <div className="customer-login">
      <h2 className="customer-title">
        <GradientText
          colors={['#7ECA9C', '#AAF0D1', '#CCFFBD', '#AAF0D1', '#7ECA9C']}
          animationSpeed={4}
          showBorder={false}
        >
          \\ CUSTOMER
        </GradientText>
      </h2>

      <div className="camera-feed">
        <div className="camera-feed-content">
          <LiquidChrome
            baseColor={[0.08, 0.18, 0.14]}
            speed={0.5}
            amplitude={0.4}
            frequencyX={3}
            frequencyY={3}
            interactive={true}
          />
        </div>
      </div>

      {/* Mobile branding - shown only on mobile inside terminal */}
      <div className="mobile-terminal-branding">
        <img src="/edgecart.png" alt="edgecart" className="mobile-terminal-logo" />
        <p className="mobile-terminal-subtitle">finding alpha in grocery arbitrage</p>
      </div>

      <Terminal />

      <div className="login-button-wrapper">
        <AwesomeButton type="primary" onPress={handleLogin}>
          <GradientText
            colors={['#7ECA9C', '#AAF0D1', '#CCFFBD', '#AAF0D1', '#7ECA9C']}
            animationSpeed={4}
            showBorder={false}
          >
            LOG IN
          </GradientText>
        </AwesomeButton>
      </div>
    </div>
  );
};

export default CustomerLogin;
