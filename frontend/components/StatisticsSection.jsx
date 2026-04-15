import React from 'react';

function StatisticsSection({ stats }) {
  return (
    <div className="card">
      <h2>📊 System DNA Statistics</h2>
      
      <div className="stats-grid">
        <div className="stat-item">
          <div className="stat-label">Verified Assets</div>
          <div className="stat-value">{stats.total_matches || 0}</div>
        </div>
        <div className="stat-item warning">
          <div className="stat-label">Threats Detected</div>
          <div className="stat-value">
            {stats.unauthorized_count || 0}
          </div>
        </div>
        <div className="stat-item success">
          <div className="stat-label">Network Alerts</div>
          <div className="stat-value">{stats.total_alerts || 0}</div>
        </div>
        <div className="stat-item danger">
          <div className="stat-label">Critical Breaches</div>
          <div className="stat-value">
            {stats.critical_alerts || 0}
          </div>
        </div>
      </div>

      {stats.avg_similarity !== undefined && (
        <div style={{ 
          marginTop: '2rem', 
          padding: '1.5rem', 
          background: 'rgba(255,255,255,0.03)', 
          borderRadius: '1.25rem',
          border: '1px solid var(--glass-border)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <span style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>Avg DNA Similarity:</span>
            <span style={{ fontWeight: 700 }}>{(stats.avg_similarity * 100).toFixed(1)}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <span style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>Database Integrity:</span>
            <span style={{ fontWeight: 700 }}>{stats.database?.total_embeddings || 0} Signatures</span>
          </div>
          <div className="similarity-meter">
            <div className="similarity-progress" style={{ width: `${(stats.avg_similarity || 0) * 100}%` }}></div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StatisticsSection;
