// src/components/features/QuizCard/QuizCard.jsx
import Card from '../../common/Card/Card';
import Button from '../../common/Button/Button';
import styles from './QuizCard.module.css';

export default function QuizCard({ question, onAnswer, disabled = false }) {
  return (
    <Card>
      <div className={styles.container}>
        <div className={styles.header}>
          <span className={styles.number}>Câu {question.id}</span>
          <h3 className={styles.question}>{question.question}</h3>
        </div>

        <div className={styles.options}>
          {question.options.map((option, idx) => (
            <button
              key={idx}
              className={styles.option}
              onClick={() => !disabled && onAnswer(option.value)}
              disabled={disabled}
            >
              <span className={styles.optionLabel}>{String.fromCharCode(65 + idx)}</span>
              <span className={styles.optionText}>{option.text}</span>
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}