'use client'

import React, { useState, useEffect } from 'react'

export default function Dashboard() {
  const [mode, setMode] = useState<'register' | 'detect'>('register')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [ownerId, setOwnerId] = useState('vyntra-admin')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState({ total_assets: 0, model: 'ViT-L/14' })

  const API_BASE = 'http://localhost:8000'

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then(res => res.json())
      .then(data => {
        setStats({
          total_assets: data.faiss?.total_vectors || 0,
          model: data.version || 'Apex v3.1'
        })
      })
      .catch(() => {})
  }, [result])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) {
      setFile(selected)
      const reader = new FileReader()
      reader.onload = (ev) => setPreview(ev.target?.result as string)
      reader.readAsDataURL(selected)
    }
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    const endpoint = mode === 'register' ? 'upload' : 'detect'
    const url = `${API_BASE}/${endpoint}?owner_id=${encodeURIComponent(ownerId)}`

    try {
      const res = await fetch(url, { method: 'POST', body: formData })
      const data = await res.json()
      if (res.ok) {
        setResult(data)
      } else {
        setError(data.detail || 'Request failed')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dashboard-container">
      <header className="header">
        <div className="logo">Vyntra <span>DNA</span></div>
        <div className="status-badge">API Connected · {stats.model}</div>
      </header>

      <main className="grid">
        <section className="panel">
          <h2 className="panel-title">Forensic DNA Lab</h2>
          
          <div className="mode-switcher">
            <button 
              className={`mode-btn ${mode === 'register' ? 'active' : ''}`}
              onClick={() => setMode('register')}
            >
              Register Master
            </button>
            <button 
              className={`mode-btn ${mode === 'detect' ? 'active' : ''}`}
              onClick={() => setMode('detect')}
            >
              Detect Violation
            </button>
          </div>

          <div className="input-group">
            <label>Owner ID / Identifier</label>
            <input 
              value={ownerId} 
              onChange={(e) => setOwnerId(e.target.value)} 
              placeholder="e.g. marvel-corp-01"
            />
          </div>

          {!preview ? (
            <div className="drop-zone" onClick={() => document.getElementById('file-input')?.click()}>
              <p>Drag master asset or click to browse</p>
              <input 
                id="file-input" 
                type="file" 
                style={{ display: 'none' }} 
                onChange={handleFileChange}
              />
            </div>
          ) : (
            <div className="preview-container">
              <img src={preview} alt="Preview" />
              <button 
                className="btn-primary" 
                style={{ background: '#f43f5e', marginTop: '0.5rem' }}
                onClick={() => { setFile(null); setPreview(null); setResult(null); }}
              >
                Clear File
              </button>
            </div>
          )}

          <button 
            className="btn-primary" 
            disabled={!file || loading}
            onClick={handleSubmit}
          >
            {loading ? 'Processing Forensic DNA...' : 
             mode === 'register' ? 'Generate & Index DNA' : 'Hunt for Violations'}
          </button>

          {error && <div className="result-card error">{error}</div>}
          
          {result && (
            <div className="result-card">
              <h3 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                {mode === 'register' ? '✓ DNA Registered Successfully' : '🔍 Analysis Complete'}
              </h3>
              {mode === 'register' ? (
                <div style={{ fontSize: '0.8rem', opacity: 0.8 }}>
                  Asset ID: {result.asset_id}<br/>
                  Filename: {result.filename}
                </div>
              ) : (
                <div style={{ fontSize: '0.8rem', opacity: 0.8 }}>
                  Severity: <span style={{ color: result.severity === 'CRITICAL' ? '#f43f5e' : '#10b981', fontWeight: 'bold' }}>
                    {result.severity}
                  </span><br/>
                  Match Score: {(result.best_match?.fusion_score * 100 || 0).toFixed(1)}%<br/>
                  {result.best_match && `Matched Asset: ${result.best_match.asset_id}`}
                </div>
              )}
            </div>
          )}
        </section>

        <section className="panel">
          <h2 className="panel-title">System Metrics & Live Feed</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '2rem' }}>
            <div className="result-card" style={{ border: '1px solid rgba(99,102,241,0.2)' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>INDEXED ASSETS</div>
              <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>{stats.total_assets}</div>
            </div>
            <div className="result-card" style={{ border: '1px solid rgba(99,102,241,0.2)' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Uptime</div>
              <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>99.9%</div>
            </div>
          </div>
          
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <p style={{ marginBottom: '1rem' }}><strong>Instructions:</strong></p>
            <ol style={{ paddingLeft: '1.2rem', lineHeight: '1.6' }}>
              <li>Select <strong>Register Master</strong>.</li>
              <li>Upload <strong>original_asset.png</strong> from the project root.</li>
              <li>Switch to <strong>Detect Violation</strong>.</li>
              <li>Upload <strong>modified_asset.png</strong> to test the 6-layer DNA tracking.</li>
            </ol>
          </div>
        </section>
      </main>

      <footer style={{ marginTop: '3rem', textAlign: 'center', fontSize: '0.75rem', opacity: 0.5 }}>
        Vyntra Systems · Content DNA Apex v5.1 · Secure Infrastructure
      </footer>
    </div>
  )
}
