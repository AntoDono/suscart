// API Configuration
const API_URL = import.meta.env.VITE_API_URL || 'http://10.25.10.163:3000';
// Convert HTTP/HTTPS URL to WebSocket URL
const WS_URL = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws');

export const config = {
  apiUrl: API_URL,
  wsUrl: WS_URL,
};

