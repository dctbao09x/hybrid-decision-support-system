// src/pages/Assessment/Assessment.jsx
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import QuizCard from '../../components/features/QuizCard/QuizCard';
import ProgressBar from '../../components/common/ProgressBar/ProgressBar';
import Button from '../../components/common/Button/Button';
import { assessmentQuestions } from '../../utils/mockData';
import { getCareerRecommendations } from '../../services/api';
import { safeJsonParse } from '../../utils/storage';
import styles from './Assessment.module.css';

export default function Assessment() {
  const navigate = useNavigate();
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState({});
  const [isComplete, setIsComplete] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [isAnswering, setIsAnswering] = useState(false);
  const answerTimeoutRef = useRef(null);
  const submitControllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (answerTimeoutRef.current) {
        clearTimeout(answerTimeoutRef.current);
      }
      submitControllerRef.current?.abort();
    };
  }, []);

  const handleAnswer = (value) => {
    if (isAnswering) return;
    setIsAnswering(true);

    setAnswers(prev => ({
      ...prev,
      [currentQuestion]: value
    }));

    if (currentQuestion < assessmentQuestions.length - 1) {
      if (answerTimeoutRef.current) {
        clearTimeout(answerTimeoutRef.current);
      }
      answerTimeoutRef.current = setTimeout(() => {
        setCurrentQuestion(prev => prev + 1);
        setIsAnswering(false);
      }, 300);
    } else {
      setIsComplete(true);
      setIsAnswering(false);
    }
  };

  const handleComplete = async () => {
    setIsSubmitting(true);
    setError('');
    localStorage.setItem('assessmentAnswers', JSON.stringify(answers));

    const controller = new AbortController();
    submitControllerRef.current?.abort();
    submitControllerRef.current = controller;

    try {
      const processedProfile = safeJsonParse(localStorage.getItem('processedProfile'), null);
      const userProfile = safeJsonParse(localStorage.getItem('userProfile'), null);
      const chatHistory = safeJsonParse(localStorage.getItem('chatHistory'), []);

      const response = await getCareerRecommendations({
        processedProfile,
        userProfile,
        assessmentAnswers: answers,
        chatHistory
      }, { signal: controller.signal });

      if (!controller.signal.aborted) {
        localStorage.setItem('careerRecommendations', JSON.stringify(response.recommendations || []));
        navigate('/chat');
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setError('Không thể tải gợi ý nghề nghiệp. Vui lòng thử lại.');
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsSubmitting(false);
      }
    }
  };

  const progress = ((currentQuestion + 1) / assessmentQuestions.length) * 100;

  if (isComplete) {
    return (
      <div className={styles.container}>
        <div className="container">
          <div className={styles.complete}>
            <div className={styles.completeIcon}>🎉</div>
            <h2 className={styles.completeTitle}>Hoàn thành đánh giá!</h2>
            <p className={styles.completeDescription}>
              Bạn đã trả lời tất cả {assessmentQuestions.length} câu hỏi. 
              Tiếp tục để trò chuyện với AI và nhận gợi ý nghề nghiệp.
            </p>
            {error && (
              <div className={styles.error}>{error}</div>
            )}
            <div className={styles.completeActions}>
              <Button size="lg" onClick={handleComplete} disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Tiếp tục với AI Chat'}
              </Button>
              {error && (
                <Button variant="outline" onClick={() => navigate('/chat')}>
                  Bỏ qua và tiếp tục
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className="container">
        <div className={styles.content}>
          <div className={styles.header}>
            <h1 className={styles.title}>Đánh giá nghề nghiệp</h1>
            <p className={styles.description}>
              Câu {currentQuestion + 1} / {assessmentQuestions.length}
            </p>
          </div>

          <ProgressBar value={progress} max={100} />

          <div className={styles.questionContainer}>
            <QuizCard
              question={assessmentQuestions[currentQuestion]}
              onAnswer={handleAnswer}
              disabled={isAnswering}
            />
          </div>

          {currentQuestion > 0 && (
            <div className={styles.navigation}>
              <Button 
                variant="outline" 
                onClick={() => setCurrentQuestion(currentQuestion - 1)}
              >
                Câu trước
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
