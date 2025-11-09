import { useState, useRef, useEffect } from 'react';
import { FaRobot, FaUser, FaPaperPlane } from 'react-icons/fa';
import { MdExpandMore } from 'react-icons/md';
import { GoogleGenerativeAI } from '@google/generative-ai';
import './ShoppingAssistant.css';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  isPurchasing?: boolean;
  purchaseComplete?: boolean;
}

interface ShoppingAssistantProps {
  customer: any;
  recommendations: any[];
  isOpen: boolean;
  onToggle: () => void;
}

const GEMINI_API_KEY = import.meta.env.VITE_GEMINI_API_KEY;
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

const ShoppingAssistant = ({ customer, recommendations, isOpen, onToggle }: ShoppingAssistantProps) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: `Hey ${customer.name.split(' ')[0]}! I'm your EdgeCart shopping assistant. I can help you find the best deals based on your preferences and even purchase items for you. What can I help you with today?`
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const buildContext = () => {
    const favoriteFruits = customer.preferences?.favorite_fruits || [];
    const avgSpend = customer.preferences?.average_spend || 0;
    const merchants = customer.preferences?.merchants_used || [];

    const availableDeals = recommendations.map(rec => ({
      fruit: rec.item.fruit_type,
      variety: rec.item.variety,
      originalPrice: rec.item.original_price,
      currentPrice: rec.item.current_price,
      discount: rec.item.discount_percentage,
      quantity: rec.item.quantity,
      freshness: rec.item.freshness?.freshness_score || 100
    }));

    return `You are a helpful shopping assistant for EdgeCart, a grocery platform that helps reduce food waste by offering deals on items nearing expiration.

Customer Profile:
- Name: ${customer.name}
- Favorite fruits: ${favoriteFruits.join(', ') || 'none specified'}
- Average spend: $${avgSpend}
- Merchants used: ${merchants.join(', ') || 'none'}

Available Deals (${availableDeals.length} items):
${availableDeals.map(deal =>
  `- ${deal.fruit} (${deal.variety}): $${deal.currentPrice} (was $${deal.originalPrice}) - ${deal.discount}% off, ${deal.quantity} available, ${deal.freshness}% fresh`
).join('\n')}

Your role:
1. Help customers find the best deals based on their preferences
2. Provide personalized shopping recommendations
3. When asked to purchase, confirm the items and quantities
4. Be friendly, concise, and helpful
5. Focus on value and freshness

Important: If the user asks you to buy something or purchase items, respond with a confirmation of what you're purchasing and ask them to confirm. Keep responses short and conversational.`;
  };

  const simulatePurchase = async (items: string) => {
    // Add a "purchasing" message
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: `Processing your order for ${items}...`,
      isPurchasing: true
    }]);

    // Simulate loading for 2 seconds
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Replace with completion message
    setMessages(prev => {
      const newMessages = [...prev];
      newMessages[newMessages.length - 1] = {
        role: 'assistant',
        content: `✓ Purchase complete! ${items} will be ready for pickup tomorrow. You saved on fresh produce while helping reduce food waste!`,
        purchaseComplete: true
      };
      return newMessages;
    });
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // Check if user wants to purchase
      const purchaseKeywords = ['buy', 'purchase', 'order', 'get', 'yes', 'confirm', 'sure'];
      const wantsToPurchase = purchaseKeywords.some(keyword =>
        userMessage.toLowerCase().includes(keyword)
      );

      // Initialize the model
      const model = genAI.getGenerativeModel({
        model: 'gemini-2.5-flash-lite',
        systemInstruction: buildContext()
      });

      // Build conversation history (skip the initial greeting message)
      const history = messages
        .slice(1) // Skip the first assistant greeting
        .filter(msg => msg.role !== 'system')
        .map(msg => ({
          role: msg.role === 'assistant' ? 'model' : 'user',
          parts: [{ text: msg.content }]
        }));

      // Start chat with history (empty if this is the first user message)
      const chat = model.startChat({ history });

      // Send message
      const result = await chat.sendMessage(userMessage);
      const response = await result.response;
      const assistantMessage = response.text();

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: assistantMessage
      }]);

      // If the assistant confirmed a purchase, simulate it
      if (wantsToPurchase && assistantMessage.toLowerCase().includes('confirm')) {
        // Extract items from the conversation
        const items = 'your selected items';
        setTimeout(() => simulatePurchase(items), 1000);
      }

    } catch (error) {
      console.error('Error calling Gemini API:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again!'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button className="assistant-float-btn" onClick={onToggle}>
          <FaRobot />
          <span className="assistant-badge">AI</span>
        </button>
      )}

      {/* Expanded Chatbox */}
      {isOpen && (
        <div className="shopping-assistant-container">
        {/* Header */}
        <div className="assistant-header">
          <div className="assistant-header-left">
            <FaRobot className="assistant-icon" />
            <div>
              <h3 className="assistant-title">shopping assistant</h3>
              <p className="assistant-subtitle">ai-powered recommendations</p>
            </div>
          </div>
          <button onClick={onToggle} className="assistant-close-btn">
            <MdExpandMore />
          </button>
        </div>

        {/* Messages */}
        <div className="assistant-messages">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`message ${msg.role} ${msg.isPurchasing ? 'purchasing' : ''} ${msg.purchaseComplete ? 'complete' : ''}`}
            >
              <div className="message-avatar">
                {msg.role === 'user' ? <FaUser /> : <FaRobot />}
              </div>
              <div className="message-content">
                {msg.isPurchasing && !msg.purchaseComplete && (
                  <div className="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                )}
                <p>{msg.content}</p>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="message-avatar">
                <FaRobot />
              </div>
              <div className="message-content">
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="assistant-input-container">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="ask me anything about your deals..."
            className="assistant-input"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="assistant-send-btn"
          >
            <FaPaperPlane />
          </button>
        </div>
      </div>
      )}
    </>
  );
};

export default ShoppingAssistant;
