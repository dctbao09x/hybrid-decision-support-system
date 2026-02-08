// src/pages/Landing/Landing.jsx
import { useNavigate } from 'react-router-dom';
import Button from '../../components/common/Button/Button';
import Card from '../../components/common/Card/Card';
import styles from './Landing.module.css';

export default function Landing() {
  const navigate = useNavigate();

  const features = [
    {
      icon: '🎯',
      title: 'Đánh giá toàn diện',
      description: 'Phân tích sở thích, kỹ năng và mục tiêu nghề nghiệp của bạn'
    },
    {
      icon: '🤖',
      title: 'AI tư vấn thông minh',
      description: 'Trò chuyện với AI để nhận tư vấn nghề nghiệp cá nhân hóa'
    },
    {
      icon: '📊',
      title: 'Gợi ý chính xác',
      description: 'Nhận danh sách nghề nghiệp phù hợp dựa trên phân tích dữ liệu'
    },
    {
      icon: '📚',
      title: 'Thư viện nghề nghiệp',
      description: 'Khám phá chi tiết hơn 40+ ngành nghề phổ biến'
    }
  ];

  return (
    <div className={styles.landing}>
      {/* Hero Section */}
      <section className={styles.hero}>
        <div className="container">
          <div className={styles.heroContent}>
            <div className={styles.heroText}>
              <h1 className={styles.heroTitle}>
                Tìm kiếm con đường
                <br />
                <span className={styles.gradient}>nghề nghiệp lý tưởng</span>
              </h1>
              <p className={styles.heroDescription}>
                Hệ thống hỗ trợ định hướng nghề nghiệp thông minh với công nghệ AI, 
                giúp bạn khám phá tiềm năng và đưa ra quyết định sáng suốt cho tương lai.
              </p>
              <div className={styles.heroButtons}>
                <Button size="lg" onClick={() => navigate('/profile')}>
                  Bắt đầu ngay 🚀
                </Button>
                <Button size="lg" variant="outline" onClick={() => navigate('/assessment')}>
                  Tìm hiểu thêm
                </Button>
              </div>
            </div>
            <div className={styles.heroImage}>
              <div className={styles.floatingCard}>
                <span className={styles.cardIcon}>💼</span>
                <div className={styles.cardContent}>
                  <div className={styles.cardTitle}>AI Engineer</div>
                  <div className={styles.cardMatch}>Match: 95%</div>
                </div>
              </div>
              <div className={`${styles.floatingCard} ${styles.card2}`}>
                <span className={styles.cardIcon}>📊</span>
                <div className={styles.cardContent}>
                  <div className={styles.cardTitle}>Data Scientist</div>
                  <div className={styles.cardMatch}>Match: 88%</div>
                </div>
              </div>
              <div className={`${styles.floatingCard} ${styles.card3}`}>
                <span className={styles.cardIcon}>🎨</span>
                <div className={styles.cardContent}>
                  <div className={styles.cardTitle}>UI/UX Designer</div>
                  <div className={styles.cardMatch}>Match: 82%</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className={styles.features}>
        <div className="container">
          <h2 className={styles.sectionTitle}>Tính năng nổi bật</h2>
          <div className={styles.featuresGrid}>
            {features.map((feature, idx) => (
              <Card key={idx} hover>
                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>{feature.icon}</div>
                  <h3 className={styles.featureTitle}>{feature.title}</h3>
                  <p className={styles.featureDescription}>{feature.description}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className={styles.cta}>
        <div className="container">
          <Card>
            <div className={styles.ctaContent}>
              <h2 className={styles.ctaTitle}>Sẵn sàng khám phá nghề nghiệp của bạn?</h2>
              <p className={styles.ctaDescription}>
                Bắt đầu hành trình định hướng nghề nghiệp của bạn ngay hôm nay
              </p>
              <Button size="lg" onClick={() => navigate('/profile')}>
                Bắt đầu đánh giá
              </Button>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}