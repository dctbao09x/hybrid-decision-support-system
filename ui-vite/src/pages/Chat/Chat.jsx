// src/pages/Chat/Chat.jsx
import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ChatMessage from '../../components/features/ChatMessage/ChatMessage';
import Button from '../../components/common/Button/Button';
import Loading from '../../components/common/Loading/Loading';
import { sendChatMessage, analyzeProfile } from '../../services/api';
import { safeJsonParse } from '../../utils/storage';
import styles from './Chat.module.css';

export default function Chat() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([
    {
      text: 'Xin chào! Tôi là trợ lý AI sẽ giúp bạn định hướng nghề nghiệp. Hãy chia sẻ thêm về bản thân, sở thích, và mục tiêu của bạn nhé!',
      isUser: false,
      time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const chatRequestRef = useRef(null);
  const analyzeRequestRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    return () => {
      chatRequestRef.current?.abort();
      analyzeRequestRef.current?.abort();
    };
  }, []);

  const buildChatHistoryPayload = (list) => (
    list.map(msg => ({
      role: msg.isUser ? 'user' : 'assistant',
      text: msg.text
    }))
  );

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = {
      text: input,
      isUser: true,
      time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    const controller = new AbortController();
    chatRequestRef.current?.abort();
    chatRequestRef.current = controller;

    try {
      const history = buildChatHistoryPayload([...messages, userMessage]);
      const result = await sendChatMessage(input, history, { signal: controller.signal });
      if (controller.signal.aborted) return;
      const replyText = typeof result?.reply === 'string' && result.reply.trim()
        ? result.reply
        : 'Xin lỗi, tôi chưa nhận được phản hồi phù hợp.';
      const aiResponse = {
        text: replyText,
        isUser: false,
        time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, aiResponse]);
    } catch (error) {
      if (controller.signal.aborted) return;
      const aiResponse = {
        text: 'API error. Please try again.',
        isUser: false,
        time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, aiResponse]);
    } finally {
      if (!controller.signal.aborted) {
        setIsTyping(false);
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleComplete = async () => {
    localStorage.setItem('chatHistory', JSON.stringify(messages));

    const controller = new AbortController();
    analyzeRequestRef.current?.abort();
    analyzeRequestRef.current = controller;

    try {
      const userProfile = safeJsonParse(localStorage.getItem('userProfile'), null);
      if (userProfile) {
        const payload = {
          personalInfo: {
            fullName: userProfile.fullName,
            age: userProfile.age,
            education: userProfile.education
          },
          interests: userProfile.interests || [],
          skills: userProfile.skills || '',
          careerGoal: userProfile.careerGoal || '',
          chatHistory: buildChatHistoryPayload(messages)
        };
        const processedProfile = await analyzeProfile(payload, { signal: controller.signal });
        if (!controller.signal.aborted) {
          localStorage.setItem('processedProfile', JSON.stringify(processedProfile));
        }
      }
    } catch (error) {
      // Ignore update errors
    } finally {
      navigate('/dashboard');
    }
  };

  return (
    <div className={styles.container}>
      <div className="container">
        <div className={styles.content}>
          <div className={styles.sidebar}>
            <div className={styles.sidebarContent}>
              <h3 className={styles.sidebarTitle}>💡 Gợi ý câu hỏi</h3>
              <div className={styles.suggestions}>
                <button 
                  className={styles.suggestion}
                  onClick={() => setInput('Tôi thích làm việc với dữ liệu và lập trình')}
                >
                  Tôi thích làm việc với dữ liệu
                </button>
                <button 
                  className={styles.suggestion}
                  onClick={() => setInput('Tôi muốn tìm hiểu về AI và Machine Learning')}
                >
                  Tìm hiểu về AI/ML
                </button>
                <button 
                  className={styles.suggestion}
                  onClick={() => setInput('Ngành nào đang hot hiện nay?')}
                >
                  Ngành nào đang hot?
                </button>
                <button 
                  className={styles.suggestion}
                  onClick={() => setInput('Tôi cần học gì để trở thành developer?')}
                >
                  Lộ trình developer
                </button>
              </div>

              <div className={styles.sidebarActions}>
                <Button variant="secondary" fullWidth onClick={handleComplete}>
                  Xem kết quả
                </Button>
              </div>
            </div>
          </div>

          <div className={styles.chatArea}>
            <div className={styles.chatHeader}>
              <div className={styles.chatHeaderInfo}>
                <div className={styles.botAvatar}>🤖</div>
                <div>
                  <h3 className={styles.botName}>AI Career Advisor</h3>
                  <p className={styles.botStatus}>
                    <span className={styles.onlineDot}></span>
                    Đang hoạt động
                  </p>
                </div>
              </div>
            </div>

            <div className={styles.messages}>
              {messages.map((msg, idx) => (
                <ChatMessage key={idx} message={msg} isUser={msg.isUser} />
              ))}
              
              {isTyping && (
                <div className={styles.typing}>
                  <div className={styles.typingDots}>
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            <div className={styles.inputArea}>
              <textarea
                className={styles.input}
                placeholder="Nhập tin nhắn của bạn..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                rows={1}
              />
              <button 
                className={styles.sendButton}
                onClick={handleSend}
                disabled={!input.trim()}
              >
                <span className={styles.sendIcon}>➤</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
