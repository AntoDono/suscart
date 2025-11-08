import { useState, useEffect } from 'react';
import { AwesomeButton } from 'react-awesome-button';
import 'react-awesome-button/dist/styles.css';
import GradientText from './GradientText';
import './CustomerLogin.css';

interface TerminalLine {
  text: string;
  timestamp: string;
}

const Terminal = () => {
  const [lines, setLines] = useState<TerminalLine[]>([]);

  const generateTimestamp = () => {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { hour12: false });
  };

  const terminalMessages = [
    'Connecting to EdgeCart customer portal...',
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
        return updated.slice(-8); // Keep only last 8 lines
      });

      messageIndex++;
    };

    // Add initial lines quickly
    const initialInterval = setInterval(() => {
      if (messageIndex < 5) {
        addLine();
      } else {
        clearInterval(initialInterval);
      }
    }, 800);

    // Then add lines every 2-4 seconds
    const mainInterval = setInterval(() => {
      if (messageIndex >= 5) {
        addLine();
      }
    }, 2000 + Math.random() * 2000);

    return () => {
      clearInterval(initialInterval);
      clearInterval(mainInterval);
    };
  }, []);

  return (
    <div className="terminal">
      <div className="terminal-header">
        <div className="terminal-buttons">
          <span className="terminal-button close"></span>
          <span className="terminal-button minimize"></span>
          <span className="terminal-button maximize"></span>
        </div>
        <div className="terminal-title">edgecart-customer-portal</div>
      </div>
      <div className="terminal-body">
        {lines.map((line, index) => (
          <div key={index} className="terminal-line">
            <span className="terminal-timestamp">[{line.timestamp}]</span>
            <span className="terminal-text">{line.text}</span>
          </div>
        ))}
        <div className="terminal-cursor">▊</div>
      </div>
    </div>
  );
};

const CustomerLogin = () => {
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
          {/* Camera feed will be integrated here */}
        </div>
      </div>

      <Terminal />

      <div className="login-button-wrapper">
        <AwesomeButton type="primary" onPress={() => window.location.hash = '#user'}>
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
