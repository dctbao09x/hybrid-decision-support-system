// src/pages/CareerDetail/CareerDetail.jsx
import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import Card from '../../components/common/Card/Card';
import Badge from '../../components/common/Badge/Badge';
import Button from '../../components/common/Button/Button';
import ProgressBar from '../../components/common/ProgressBar/ProgressBar';
import Loading from '../../components/common/Loading/Loading';
import { getCareerRecommendations, getCareerLibrary } from '../../services/api';
import { safeJsonParse } from '../../utils/storage';
import styles from './CareerDetail.module.css';

export default function CareerDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [career, setCareer] = useState(null);
  const [allCareers, setAllCareers] = useState([]);
  const [loading, setLoading] = useState(true);
  const requestIdRef = useRef(0);

  const normalizeCareer = (item) => {
    if (!item) return null;
    const safeNumber = (value, fallback = 0) => {
      const num = Number(value);
      return Number.isFinite(num) ? num : fallback;
    };

    return {
      ...item,
      domain: item.domain || 'Unknown',
      description: item.description || '',
      icon: item.icon || '??',
      matchScore: safeNumber(item.matchScore, 0),
      growthRate: safeNumber(item.growthRate, 0),
      competition: safeNumber(item.competition, 0),
      aiRelevance: safeNumber(item.aiRelevance, 0),
      requiredSkills: Array.isArray(item.requiredSkills) ? item.requiredSkills : []
    };
  };

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;

    const loadCareer = async () => {
      try {
        const cached = safeJsonParse(localStorage.getItem('careerRecommendations'), null);
        let recs = cached;

        if (!recs || !recs.length) {
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

          recs = response.recommendations || [];
          localStorage.setItem('careerRecommendations', JSON.stringify(recs));
        }

        let found = (recs || []).find(c => c.id === id);
        let all = recs || [];

        if (!found) {
          const cachedLibrary = safeJsonParse(localStorage.getItem('careerLibrary'), null);
          let library = cachedLibrary;

          if (!library || !library.length) {
            const libResponse = await getCareerLibrary({ signal: controller.signal });
            library = libResponse.careers || [];
            localStorage.setItem('careerLibrary', JSON.stringify(library));
          }

          all = library || all;
          found = (library || []).find(c => c.id === id) || null;
        }

        if (requestId !== requestIdRef.current) return;
        setAllCareers((all || []).map(normalizeCareer).filter(Boolean));
        setCareer(normalizeCareer(found || null));
      } catch (error) {
        if (requestId !== requestIdRef.current) return;
        setCareer(null);
      } finally {
        if (requestId !== requestIdRef.current) return;
        setLoading(false);
      }
    };

    loadCareer();
    return () => {
      controller.abort();
    };
  }, [id]);

  if (loading) {
    return <Loading fullScreen />;
  }

  if (!career) {
    return (
      <div className={styles.notFound}>
        <h2>Không tìm thấy nghề nghiệp</h2>
        <Button onClick={() => navigate('/dashboard')}>Quay lại</Button>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className="container">
        {/* Header */}
        <section className={styles.header}>
          <Button variant="ghost" onClick={() => navigate(-1)}>
            ← Quay lại
          </Button>

          <div className={styles.hero}>
            <div className={styles.heroIcon}>{career.icon}</div>
            <div className={styles.heroContent}>
              <h1 className={styles.title}>{career.name}</h1>
              <p className={styles.domain}>{career.domain}</p>
              <div className={styles.badges}>
                <Badge variant="primary" size="lg">
                  Match: {(career.matchScore * 100).toFixed(0)}%
                </Badge>
                <Badge variant="success" size="lg">
                  Tăng trưởng: {(career.growthRate * 100).toFixed(0)}%
                </Badge>
                <Badge variant="warning" size="lg">
                  Cạnh tranh: {(career.competition * 100).toFixed(0)}%
                </Badge>
              </div>
            </div>
          </div>
        </section>

        <div className={styles.content}>
          {/* Main Content */}
          <div className={styles.main}>
            {/* Overview */}
            <Card>
              <h2 className={styles.sectionTitle}>Tổng quan</h2>
              <p className={styles.description}>{career.description}</p>
            </Card>

            {/* Skills */}
            <Card>
              <h2 className={styles.sectionTitle}>Kỹ năng yêu cầu</h2>
              <div className={styles.skills}>
                {(career.requiredSkills || []).map((skill, idx) => (
                  <div key={idx} className={styles.skillTag}>
                    {skill}
                  </div>
                ))}
              </div>
            </Card>

            {/* Career Path */}
            <Card>
              <h2 className={styles.sectionTitle}>Lộ trình phát triển</h2>
              <div className={styles.pathway}>
                {['Junior', 'Middle', 'Senior', 'Lead/Expert'].map((level, idx) => (
                  <div key={idx} className={styles.pathwayStep}>
                    <div className={styles.pathwayNumber}>{idx + 1}</div>
                    <div className={styles.pathwayContent}>
                      <h4>{level}</h4>
                      <p>
                        {idx === 0 && '1-2 năm kinh nghiệm'}
                        {idx === 1 && '2-4 năm kinh nghiệm'}
                        {idx === 2 && '4-7 năm kinh nghiệm'}
                        {idx === 3 && '7+ năm kinh nghiệm'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Learning Resources */}
            <Card>
              <h2 className={styles.sectionTitle}>Tài nguyên học tập</h2>
              <div className={styles.resources}>
                <div className={styles.resource}>
                  <span className={styles.resourceIcon}>📚</span>
                  <div>
                    <h4>Khóa học trực tuyến</h4>
                    <p>Coursera, Udemy, edX</p>
                  </div>
                </div>
                <div className={styles.resource}>
                  <span className={styles.resourceIcon}>💻</span>
                  <div>
                    <h4>Thực hành</h4>
                    <p>GitHub, LeetCode, Kaggle</p>
                  </div>
                </div>
                <div className={styles.resource}>
                  <span className={styles.resourceIcon}>👥</span>
                  <div>
                    <h4>Cộng đồng</h4>
                    <p>Discord, Reddit, Stack Overflow</p>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Sidebar */}
          <div className={styles.sidebar}>
            {/* Quick Stats */}
            <Card>
              <h3 className={styles.sidebarTitle}>Chỉ số quan trọng</h3>
              <div className={styles.stats}>
                <div className={styles.statItem}>
                  <span className={styles.statLabel}>Mức độ khớp</span>
                  <ProgressBar 
                    value={career.matchScore * 100} 
                    max={100}
                    showLabel={true}
                  />
                </div>
                <div className={styles.statItem}>
                  <span className={styles.statLabel}>Tăng trưởng</span>
                  <ProgressBar 
                    value={career.growthRate * 100} 
                    max={100}
                    showLabel={true}
                  />
                </div>
                <div className={styles.statItem}>
                  <span className={styles.statLabel}>Cạnh tranh</span>
                  <ProgressBar 
                    value={career.competition * 100} 
                    max={100}
                    showLabel={true}
                  />
                </div>
                <div className={styles.statItem}>
                  <span className={styles.statLabel}>Liên quan AI</span>
                  <ProgressBar 
                    value={career.aiRelevance * 100} 
                    max={100}
                    showLabel={true}
                  />
                </div>
              </div>
            </Card>

            {/* Actions */}
            <Card>
              <h3 className={styles.sidebarTitle}>Hành động</h3>
              <div className={styles.actions}>
                <Button fullWidth variant="primary">
                  Lưu nghề nghiệp
                </Button>
                <Button fullWidth variant="outline">
                  Chia sẻ
                </Button>
                <Button fullWidth variant="ghost">
                  So sánh với nghề khác
                </Button>
              </div>
            </Card>

            {/* Related Careers */}
            <Card>
              <h3 className={styles.sidebarTitle}>Nghề liên quan</h3>
              <div className={styles.related}>
                {allCareers
                  .filter(c => c.id !== id && c.domain === career.domain)
                  .slice(0, 3)
                  .map(relatedCareer => (
                    <button
                      key={relatedCareer.id}
                      className={styles.relatedItem}
                      onClick={() => navigate(`/career/${relatedCareer.id}`)}
                    >
                      <span className={styles.relatedIcon}>{relatedCareer.icon}</span>
                      <div className={styles.relatedInfo}>
                        <h5>{relatedCareer.name}</h5>
                        <p>{(Number(relatedCareer.matchScore || 0) * 100).toFixed(0)}% match</p>
                      </div>
                    </button>
                  ))}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}