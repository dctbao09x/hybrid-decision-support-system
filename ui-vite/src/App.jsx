// src/App.jsx
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/layout/Header/Header';
import Footer from './components/layout/Footer/Footer';
import Landing from './pages/Landing/Landing';
import ProfileSetup from './pages/ProfileSetup/ProfileSetup';
import Assessment from './pages/Assessment/Assessment';
import Chat from './pages/Chat/Chat';
import Dashboard from './pages/Dashboard/Dashboard';
import CareerDetail from './pages/CareerDetail/CareerDetail';
import CareerLibrary from './pages/CareerLibrary/CareerLibrary';
import ErrorBoundary from './components/common/ErrorBoundary/ErrorBoundary';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <Header />
        <main className="main-content">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/profile" element={<ProfileSetup />} />
              <Route path="/assessment" element={<Assessment />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/career/:id" element={<CareerDetail />} />
              <Route path="/library" element={<CareerLibrary />} />
            </Routes>
          </ErrorBoundary>
        </main>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
