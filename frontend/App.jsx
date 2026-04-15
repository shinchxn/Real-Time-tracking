import React, { useState, useEffect } from 'react';
import axios from 'axios';
import UploadSection from './components/UploadSection';
import ResultsSection from './components/ResultsSection';
import StatisticsSection from './components/StatisticsSection';
import './index.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [results, setResults] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [checkHistory, setCheckHistory] = useState([]);
  const [backendStatus, setBackendStatus] = useState('connecting');

  const handleUpload = async (file) => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);

      await axios.post(`${API_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });

      setError(null);
      await fetchStatistics();
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCheck = async (file) => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API_URL}/check`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });

      setResults(response.data);
      setCheckHistory((prev) => [response.data, ...prev.slice(0, 4)]); // Keep last 5
      await fetchStatistics();
    } catch (err) {
      setError(err.response?.data?.detail || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const fetchStatistics = async () => {
    try {
      const response = await axios.get(`${API_URL}/results`);
      setStatistics(response.data);
      setBackendStatus('online');
    } catch (err) {
      setBackendStatus('offline');
      console.error('Failed to fetch statistics:', err);
    }
  };

  useEffect(() => {
    fetchStatistics();
    const interval = setInterval(fetchStatistics, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard">
      <div style={{ 
        position: 'fixed', 
        top: 0, 
        left: 0, 
        right: 0, 
        padding: '0.5rem 2.5rem', 
        display: 'flex', 
        justifyContent: 'flex-end',
        zIndex: 100,
        background: 'rgba(0,0,0,0.2)',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: backendStatus === 'online' ? 'var(--success)' : 'var(--danger)', boxShadow: backendStatus === 'online' ? '0 0 8px var(--success)' : '0 0 8px var(--danger)' }}></span>
          <span style={{ color: backendStatus === 'online' ? 'var(--success)' : 'var(--danger)' }}>Backend {backendStatus}</span>
        </div>
      </div>

      <div className="header">
        <div className="logo-icon">🛡️</div>
        <h1>Digital Asset Protection</h1>
        <p>Advanced Content DNA Tracking & Intelligence</p>
      </div>

      <div className="container">
        <div className="grid">
          <UploadSection
            onUpload={handleUpload}
            onCheck={handleCheck}
            loading={loading}
            error={error}
          />
          
          {statistics && <StatisticsSection stats={statistics} />}
        </div>

        {results && <ResultsSection results={results} />}

        {checkHistory.length > 0 && (
          <div className="card">
            <h2><span>📋</span> Activity Logs</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginTop: '1rem' }}>
              {checkHistory.map((result, idx) => (
                <div key={idx} className="match-card" style={{ padding: '1.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-dim)' }}>REPORT #{results ? checkHistory.length - idx : ''}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{new Date(result.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ 
                      width: '40px', 
                      height: '40px', 
                      borderRadius: '12px', 
                      background: result.has_unauthorized_use ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '1.25rem'
                    }}>
                      {result.has_unauthorized_use ? '⚠️' : '✓'}
                    </div>
                    <div>
                      <p style={{ fontWeight: 700 }}>{result.has_unauthorized_use ? 'Infringement Found' : 'Verified Secure'}</p>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>{result.matches.length} Signatures Detected</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
