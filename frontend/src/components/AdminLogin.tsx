import { useState, useEffect } from 'react';
import { AwesomeButton } from 'react-awesome-button';
import 'react-awesome-button/dist/styles.css';
import GradientText from './GradientText';
import './AdminLogin.css';

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
    'Initializing edgecart monitoring system...',
    'Camera feed connected: Store_A_Produce_01',
    'AI model loaded: freshness-detection-v2.3',
    'Scanning inventory... 247 items detected',
    'Freshness analysis: 89% optimal, 11% degrading',
    'Customer pattern analysis running...',
    'Price optimization engine: ACTIVE',
    'Notification queue: 12 pending',
    'Knot API: Connected - 1,247 active users',
    'Predictive model accuracy: 94.2%',
    'Waste reduction today: 34.7 lbs',
    'Revenue recovery: $287.45',
    'Alert: Bananas shelf B3 - 68% freshness',
    'Matched 23 customers for banana discount',
    'Notifications sent: 23/23 delivered',
    'Avocado inventory: Reduce next order by 15%',
    'System health: All services nominal',
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
        <div className="terminal-title">edgecart-system-monitor</div>
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

const AdminLogin = () => {
  return (
    <div className="admin-login">
      <h2 className="admin-title">
        <GradientText
          colors={['#7ECA9C', '#AAF0D1', '#CCFFBD', '#AAF0D1', '#7ECA9C']}
          animationSpeed={4}
          showBorder={false}
        >
          ADMINISTRATOR //
        </GradientText>
      </h2>

      <div className="camera-feed">
        <div className="camera-feed-content">
          {/* Camera feed will be integrated here */}
        </div>
      </div>

      <Terminal />

      <div className="login-button-wrapper">
        <AwesomeButton type="primary" onPress={() => window.location.hash = '#admin'}>
          <GradientText
            colors={['#7ECA9C', '#AAF0D1', '#CCFFBD', '#AAF0D1', '#7ECA9C']}
            animationSpeed={4}
            showBorder={false}
          >
            ACCESS SYSTEM
          </GradientText>
        </AwesomeButton>
      </div>
    </div>
  );
};

export default AdminLogin;
