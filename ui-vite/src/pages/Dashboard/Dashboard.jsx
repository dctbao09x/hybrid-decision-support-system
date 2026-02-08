// src/pages/Dashboard/Dashboard.jsx
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import CareerCard from '../../components/features/CareerCard/CareerCard';
import Card from '../../components/common/Card/Card';
import Badge from '../../components/common/Badge/Badge';
import Button from '../../components/common/Button/Button';
import Loading from '../../components/common/Loading/Loading';
import { getCareerRecommendations } from '../../services/api';
import { safeJsonParse } from '../../utils/storage';
import styles from './Dashboard.module.css';

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [careers, setCareers] = useState([]);
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;

    const loadRecommendations = async () => {
      try {
        const cached = safeJsonParse(localStorage.getItem('careerRecommendations'), null);
        if (cached && cached.length) {
          if (requestId !== requestIdRef.current) return;
          setCareers(cached);
          setLoading(false);
          return;
        }

        const processedProfile = safeJsonParse(localStorage.getItem('processedProfile'), null);
        const userProfile = safeJsonParse(localStorage.getItem('userProfile'), null);
        const assessmentAnswers = safeJsonParse(localStorage.getItem('assessmentAnswers'), null);
        const chatHistory = safeJsonParse(localStorage.getItem('chatHistory'), []);

        const response = await getCareerRecommendations({
          processedProfile,
          userProfile,
          assessmentAnswers,
          chatHistory
        }, { signal: controller.signal });

        const recs = response.recommendations || [];
        if (requestId !== requestIdRef.current) return;
        setCareers(recs);
        localStorage.setItem('careerRecommendations', JSON.stringify(recs));
      } catch (err) {
        if (requestId !== requestIdRef.current) return;
        setError('Failed to load recommendations. Please try again.');
      } finally {
        if (requestId !== requestIdRef.current) return;
        setLoading(false);
      }
    };

    loadRecommendations();
    return () => {
      controller.abort();
    };
  }, []);

  const filteredCareers = careers.filter(career => {
    if (filter === 'all') return true;
    if (filter === 'high-match') return career.matchScore >= 0.8;
    if (filter === 'ai') return career.domain === 'AI' || career.domain === 'Data';
    return career.domain === filter;
  });

  if (loading) {
    return <Loading fullScreen />;
  }

  const safeNumber = (value, fallback = 0) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  };

  const topMatchScore = safeNumber(careers[0]?.matchScore, 0);

  return (
    <div className={styles.container}>
      <div className="container">
        {/* Summary Section */}
        <section className={styles.summary}>
          <Card>
            <div className={styles.summaryContent}>
              <div className={styles.summaryText}>
                <h1 className={styles.title}>Kết quả phân tích nghề nghiệp</h1>
                <p className={styles.description}>
                  Dựa trên phân tích của chúng tôi, đây là các nghề nghiệp phù hợp nhất với bạn
                </p>
              </div>
              <div className={styles.stats}>
                <div className={styles.stat}>
                  <div className={styles.statValue}>{careers.length}</div>
                  <div className={styles.statLabel}>Nghề phù hợp</div>
                </div>
                <div className={styles.stat}>
                  <div className={styles.statValue}>
                    {Math.round(topMatchScore * 100)}%
                  </div>
                  <div className={styles.statLabel}>Khớp cao nhất</div>
                </div>
                <div className={styles.stat}>
                  <div className={styles.statValue}>
                    {careers.filter(c => safeNumber(c.matchScore, 0) >= 0.8).length}
                  </div>
                  <div className={styles.statLabel}>Khớp trên 80%</div>
                </div>
              </div>
            </div>
          </Card>
        </section>

        {error && (
          <section className={styles.filters}>
            <div className={styles.resultCount}>{error}</div>
          </section>
        )}

        {/* Filters */}
        <section className={styles.filters}>
          <div className={styles.filterButtons}>
            <button
              className={`${styles.filterButton} ${filter === 'all' ? styles.active : ''}`}
              onClick={() => setFilter('all')}
            >
              Tất cả
            </button>
            <button
              className={`${styles.filterButton} ${filter === 'high-match' ? styles.active : ''}`}
              onClick={() => setFilter('high-match')}
            >
              Khớp cao
            </button>
            <button
              className={`${styles.filterButton} ${filter === 'ai' ? styles.active : ''}`}
              onClick={() => setFilter('ai')}
            >
              AI & Data
            </button>
            <button
              className={`${styles.filterButton} ${filter === 'Software' ? styles.active : ''}`}
              onClick={() => setFilter('Software')}
            >
              Phần mềm
            </button>
            <button
              className={`${styles.filterButton} ${filter === 'Design' ? styles.active : ''}`}
              onClick={() => setFilter('Design')}
            >
              Thiết kế
            </button>
          </div>
          
          <div className={styles.resultCount}>
            Hiển thị {filteredCareers.length} kết quả
          </div>
        </section>

        {/* Career Grid */}
        <section className={styles.careers}>
          <div className={styles.careerGrid}>
            {filteredCareers.map(career => (
              <CareerCard key={career.id} career={career} />
            ))}
          </div>

          {filteredCareers.length === 0 && (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}>🔍</div>
              <h3>Không tìm thấy kết quả</h3>
              <p>Thử thay đổi bộ lọc để xem thêm nghề nghiệp khác</p>
            </div>
          )}
        </section>

        {/* Actions */}
        <section className={styles.actions}>
          <Card>
            <div className={styles.actionsContent}>
              <h3 className={styles.actionsTitle}>Chưa hài lòng với kết quả?</h3>
              <p className={styles.actionsDescription}>
                Cập nhật thông tin hoặc trò chuyện thêm với AI để có gợi ý tốt hơn
              </p>
              <div className={styles.actionButtons}>
                <Button variant="outline" onClick={() => navigate('/profile')}>
                  Cập nhật hồ sơ
                </Button>
                <Button onClick={() => navigate('/chat')}>
                  Trò chuyện với AI
                </Button>
              </div>
            </div>
          </Card>
        </section>
      </div>
    </div>
  );
}