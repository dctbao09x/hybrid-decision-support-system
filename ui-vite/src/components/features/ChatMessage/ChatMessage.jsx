// src/components/features/ChatMessage/ChatMessage.jsx
import styles from './ChatMessage.module.css';

export default function ChatMessage({ message, isUser }) {
  return (
    <div className={`${styles.message} ${isUser ? styles.user : styles.ai}`}>
      <div className={styles.avatar}>
        {isUser ? '👤' : '🤖'}
      </div>
      <div className={styles.content}>
        <div className={styles.bubble}>
          {message.text}
        </div>
        <span className={styles.time}>{message.time}</span>
      </div>
    </div>
  );
}