// src/components/layout/Header/Header.jsx
import { Link, useLocation } from 'react-router-dom';
import styles from './Header.module.css';

export default function Header() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Trang chủ' },
    { path: '/assessment', label: 'Đánh giá' },
    { path: '/chat', label: 'Tư vấn AI' },
    { path: '/library', label: 'Thư viện nghề' },
    { path: '/dashboard', label: 'Kết quả' }
  ];

  return (
    <header className={styles.header}>
      <div className="container">
        <div className={styles.content}>
          <Link to="/" className={styles.logo}>
            <span className={styles.logoIcon}>🎯</span>
            <span className={styles.logoText}>CareerAI</span>
          </Link>

          <nav className={styles.nav}>
            {navItems.map(item => (
              <Link
                key={item.path}
                to={item.path}
                className={`${styles.navLink} ${location.pathname === item.path ? styles.active : ''}`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className={styles.actions}>
            <Link to="/profile">
              <button className={styles.profileButton}>
                <span className={styles.avatar}>👤</span>
              </button>
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}
