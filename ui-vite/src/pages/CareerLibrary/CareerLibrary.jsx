import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../../components/common/Card/Card';
import Button from '../../components/common/Button/Button';
import Loading from '../../components/common/Loading/Loading';
import { getCareerLibrary } from '../../services/api';
import { safeJsonParse } from '../../utils/storage';
import styles from './CareerLibrary.module.css';

export default function CareerLibrary() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [careers, setCareers] = useState([]);
  const [search, setSearch] = useState('');
  const [domain, setDomain] = useState('all');
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;

    const loadLibrary = async () => {
      try {
        const cached = safeJsonParse(localStorage.getItem('careerLibrary'), null);
        if (cached && cached.length) {
          if (requestId !== requestIdRef.current) return;
          setCareers(cached);
          setLoading(false);
          return;
        }

        const response = await getCareerLibrary({ signal: controller.signal });
        const items = response.careers || [];
        if (requestId !== requestIdRef.current) return;
        setCareers(items);
        localStorage.setItem('careerLibrary', JSON.stringify(items));
      } catch (err) {
        setError('Không thể tải thư viện nghề nghiệp. Vui lòng thử lại sau.');
      } finally {
        setLoading(false);
      }
    };

    loadLibrary();
    return () => {
      controller.abort();
    };
  }, []);

  const domains = useMemo(() => {
    const set = new Set(careers.map(c => c.domain).filter(Boolean));
    return ['all', ...Array.from(set).sort()];
  }, [careers]);

  useEffect(() => {
    if (!domains.includes(domain)) {
      setDomain('all');
    }
  }, [domains, domain]);

  const filtered = useMemo(() => {
    const q = String(search || '').trim().toLowerCase();
    return careers.filter(c => {
      const careerName = String(c.name || '').toLowerCase();
      const careerDomain = c.domain || 'Unknown';
      const matchesDomain = domain === 'all' || careerDomain === domain;
      const matchesQuery = !q || careerName.includes(q);
      return matchesDomain && matchesQuery;
    });
  }, [careers, search, domain]);

  if (loading) {
    return <Loading fullScreen />;
  }

  const safeNumber = (value, fallback = 0) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  };

  return (
    <div className={styles.container}>
      <div className="container">
        <section className={styles.header}>
          <div>
            <h1 className={styles.title}>Thư viện nghề nghiệp</h1>
            <p className={styles.subtitle}>Top 42 ngành nghề có triển vọng phát triển nhất tại Việt Nam</p>
          </div>
          <div className={styles.searchBox}>
            <input
              className={styles.searchInput}
              placeholder="Tìm kiếm nghề nghiệp..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </section>

        <section className={styles.filters}>
          <div className={styles.filterButtons}>
            {domains.map(d => (
              <button
                key={d}
                className={`${styles.filterButton} ${domain === d ? styles.active : ''}`}
                onClick={() => setDomain(d)}
              >
                {d === 'all' ? 'Tất cả' : d}
              </button>
            ))}
          </div>
          <div className={styles.resultCount}>Hiển thị {filtered.length} kết quả</div>
        </section>

        {error && (
          <section className={styles.error}>{error}</section>
        )}

        <section className={styles.grid}>
          {filtered.map(career => (
            <Card key={career.id} hover>
              <div className={styles.cardHeader}>
                <div className={styles.icon}>{career.icon}</div>
                <div>
                  <div className={styles.cardTitle}>{career.name}</div>
                  <div className={styles.cardDomain}>{career.domain}</div>
                </div>
              </div>

              <div className={styles.cardMeta}>
                <div>AI: {(safeNumber(career.aiRelevance, 0) * 100).toFixed(0)}%</div>
                <div>Tăng trưởng: {(safeNumber(career.growthRate, 0) * 100).toFixed(0)}%</div>
                <div>Cạnh tranh: {(safeNumber(career.competition, 0) * 100).toFixed(0)}%</div>
              </div>

              <div className={styles.skills}>
                {(career.requiredSkills || []).slice(0, 6).map((skill, idx) => (
                  <span key={idx} className={styles.skill}>{skill}</span>
                ))}
              </div>

              <div className={styles.actions}>
                <Button variant="outline" onClick={() => navigate(`/career/${career.id}`)}>
                  Xem chi tiết
                </Button>
              </div>
            </Card>
          ))}
        </section>
      </div>
    </div>
  );
}
