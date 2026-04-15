import React from 'react';

function ResultsSection({ results }) {
  const { 
    has_unauthorized_use, 
    best_match, 
    matches, 
    alerts, 
    query_asset_id 
  } = results;

  return (
    <div className="container">
      <div className="card">
        <h2 style={{ marginBottom: '2.5rem' }}>
          <span>🛰️</span> Analysis Report
        </h2>
        
        <div style={{ marginBottom: '3rem' }}>
          {has_unauthorized_use ? (
            <div style={{ 
              background: 'rgba(239, 68, 68, 0.1)', 
              border: '1px solid var(--danger)', 
              color: 'var(--danger)',
              padding: '1.5rem',
              borderRadius: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              fontWeight: 800,
              fontSize: '1.25rem'
            }}>
              <span>⚠️</span> UNAUTHORIZED USE DETECTED
            </div>
          ) : (
            <div style={{ 
              background: 'rgba(16, 185, 129, 0.1)', 
              border: '1px solid var(--success)', 
              color: 'var(--success)',
              padding: '1.5rem',
              borderRadius: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              fontWeight: 800,
              fontSize: '1.25rem'
            }}>
              <span>✓</span> ASSET SIGNAL VERIFIED (ORIGINAL)
            </div>
          )}
        </div>

        <div className="results-grid">
          {/* Best Match Card */}
          {best_match ? (
            <div className={`match-card ${has_unauthorized_use ? 'danger' : ''}`} style={{ borderLeft: `4px solid ${has_unauthorized_use ? 'var(--danger)' : 'var(--success)'}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>🎯 Top Signature Match</h3>
                <span className="similarity-badge" style={{ padding: '0.4rem 0.8rem', background: 'rgba(255,255,255,0.05)', borderRadius: '1rem', fontSize: '0.9rem', fontWeight: 800 }}>
                  {(best_match.similarity_score * 100).toFixed(1)}% Match
                </span>
              </div>
              
              <div style={{ color: 'var(--text-dim)', fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <p><strong>Matched Asset:</strong> {best_match.matched_filename}</p>
                <p><strong>Signature ID:</strong> {best_match.matched_asset_id.substring(0, 16)}...</p>
                <p><strong>Classification:</strong> {best_match.match_type.replace('_', ' ').toUpperCase()}</p>
              </div>

              <div className="similarity-meter" style={{ marginTop: '1.5rem' }}>
                <div 
                  className="similarity-progress" 
                  style={{ 
                    width: `${best_match.similarity_score * 100}%`,
                    background: best_match.similarity_score > 0.85 ? 'var(--danger)' : 'var(--primary)'
                  }}
                ></div>
              </div>
            </div>
          ) : (
            <div className="match-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '150px', background: 'rgba(255,255,255,0.02)' }}>
              <p style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No comparative matches found</p>
            </div>
          )}

          {/* Analysis Summary */}
          <div className="match-card">
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '1.5rem' }}>🛡️ Intelligence Summary</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-dim)' }}>Matches Reviewed:</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 800 }}>{matches.length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-dim)' }}>Security Alerts:</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 800, color: alerts.length > 0 ? 'var(--warning)' : 'var(--text-main)' }}>{alerts.length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-dim)' }}>Risk Level:</span>
                <span style={{ 
                  fontWeight: 800, 
                  color: alerts.some(a => a.severity === 'critical') ? 'var(--danger)' : has_unauthorized_use ? 'var(--warning)' : 'var(--success)' 
                }}>
                  {alerts.some(a => a.severity === 'critical') ? 'CRITICAL' : has_unauthorized_use ? 'HIGH' : 'LOW'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Detailed Alerts List */}
        {alerts.length > 0 && (
          <div style={{ marginTop: '3rem' }}>
            <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span>🚨</span> System Alerts
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {alerts.map((alert, idx) => (
                <div key={idx} style={{ 
                  background: 'rgba(255,255,255,0.03)', 
                  border: `1px solid ${alert.severity === 'critical' ? 'rgba(239, 68, 68, 0.2)' : 'var(--glass-border)'}`, 
                  borderRadius: '1.25rem',
                  padding: '1.25rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <p style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{alert.message}</p>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                      Matched Signature: {alert.matched_asset_id.substring(0, 12)}... | Score: {(alert.similarity_score * 100).toFixed(1)}%
                    </p>
                  </div>
                  <span style={{ 
                    padding: '0.4rem 1rem', 
                    borderRadius: '0.75rem', 
                    fontSize: '0.75rem', 
                    fontWeight: 900,
                    background: alert.severity === 'critical' ? 'var(--danger)' : 'rgba(255,255,255,0.05)',
                    color: alert.severity === 'critical' ? 'white' : 'var(--text-dim)'
                  }}>
                    {alert.severity.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResultsSection;
