import { useState, useEffect, useRef } from 'react';
import { AwesomeButton } from 'react-awesome-button';
import 'react-awesome-button/dist/styles.css';
import GradientText from './GradientText';
import LiquidChrome from './LiquidChrome';
import './AdminLogin.css';

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
    { label: 'administrator@edgecart', value: '', highlight: true },
    { label: '---------------------', value: '', separator: true },
    { label: 'OS', value: 'EdgeCart Linux x86_64' },
    { label: 'Host', value: 'EdgeCart Platform v2.3' },
    { label: 'Uptime', value: '7 days, 14 hours' },
    { label: 'Packages', value: '1247 (npm)' },
    { label: 'Shell', value: 'bash 5.2.15' },
    { label: 'Terminal', value: 'edgecart-admin-tty' },
    { label: 'CPU', value: 'Intel i9 @ 3.6GHz' },
    { label: 'Memory', value: '8742MB / 16384MB' },
  ];

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
        <div className="terminal-title">administrator@edgecart</div>
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
