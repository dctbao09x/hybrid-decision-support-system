// src/components/features/CareerCard/CareerCard.jsx
import { useNavigate } from 'react-router-dom';
import Card from '../../common/Card/Card';
import Badge from '../../common/Badge/Badge';
import styles from './CareerCard.module.css';

export default function CareerCard({ career }) {
  const navigate = useNavigate();

  return (
    <Card hover onClick={() => navigate(`/career/${career.id}`)}>
      <div className={styles.header}>
        <div className={styles.icon}>{career.icon}</div>
        <div className={styles.headerContent}>
          <h3 className={styles.title}>{career.name}</h3>
          <p className={styles.domain}>{career.domain}</p>
        </div>
      </div>

      <p className={styles.description}>{career.description}</p>

      <div className={styles.badges}>
        <Badge variant="primary">Match: {(career.matchScore * 100).toFixed(0)}%</Badge>
        <Badge variant="success">Tăng trưởng: {(career.growthRate * 100).toFixed(0)}%</Badge>
      </div>

      <div className={styles.skills}>
        <span className={styles.skillsLabel}>Kỹ năng:</span>
        <div className={styles.skillsList}>
          {career.requiredSkills.slice(0, 3).map((skill, idx) => (
            <span key={idx} className={styles.skill}>{skill}</span>
          ))}
          {career.requiredSkills.length > 3 && (
            <span className={styles.skillMore}>+{career.requiredSkills.length - 3}</span>
          )}
        </div>
      </div>
    </Card>
  );
}