import React, { useState, useRef } from 'react';

function UploadSection({ onUpload, onCheck, loading, error }) {
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [mode, setMode] = useState('check'); // 'upload' or 'check'

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    setSelectedFile(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    if (mode === 'upload') {
      await onUpload(selectedFile);
    } else {
      await onCheck(selectedFile);
    }
    
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="card">
      <h2><span>📡</span> Upload & Scan</h2>
      
      <div className="mode-toggle">
        <button 
          className={`mode-btn ${mode === 'check' ? 'active' : ''}`}
          onClick={() => setMode('check')}
          disabled={loading}
        >
          🔍 Scan for Infringement
        </button>
        <button 
          className={`mode-btn ${mode === 'upload' ? 'active' : ''}`}
          onClick={() => setMode('upload')}
          disabled={loading}
        >
          🛡️ Secure New Asset
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div
          className={`upload-zone ${dragActive ? 'dragover' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleChange}
            accept="image/*,video/*"
            disabled={loading}
          />
          <div className="upload-icon">
            {selectedFile ? '✅' : mode === 'check' ? '📸' : '🔐'}
          </div>
          <p style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: '0.5rem' }}>
            {selectedFile ? selectedFile.name : 'Drop file to process or click to browse'}
          </p>
          <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>
            JPG, PNG, GIF, WebP, MP4, AVI, MOV up to 50MB
          </p>
        </div>

        <button 
          className="btn-primary" 
          type="submit" 
          disabled={!selectedFile || loading}
        >
          {loading ? (
            <>
              <div className="loading-spinner"></div>
              <span>Processing DNA...</span>
            </>
          ) : (
            <>
              <span>{mode === 'check' ? 'Initiate Global Scan' : 'Generate Content DNA'}</span>
            </>
          )}
        </button>
      </form>

      {error && (
        <div style={{ marginTop: '1.5rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}

export default UploadSection;
