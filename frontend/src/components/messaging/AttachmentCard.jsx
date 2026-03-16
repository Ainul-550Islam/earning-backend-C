// src/components/messaging/AttachmentCard.jsx
// All-in-one attachment card renderer
// Supports: image, video, audio, document

import { useState } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace('/api','') || 'http://localhost:8000';

// Ensure absolute URL
const absUrl = (url) => {
  if (!url) return '';
  if (url.startsWith('http')) return url;
  return `${BASE_URL}${url}`;
};

const getCategory = (att) => {
  if (att?.category) return att.category;
  const m = att?.mimetype || '';
  if (m.startsWith('image/')) return 'image';
  if (m.startsWith('video/')) return 'video';
  if (m.startsWith('audio/')) return 'audio';
  return 'document';
};

const formatBytes = (b = 0) =>
  b < 1024 ? `${b}B` : b < 1048576 ? `${(b/1024).toFixed(1)}KB` : `${(b/1048576).toFixed(1)}MB`;

const DOC_ICONS = {
  'application/pdf': '📕',
  'application/zip': '🗜️',
  'text/plain':      '📝',
  default:           '📄',
};
const docIcon = (mime) => DOC_ICONS[mime] || DOC_ICONS.default;

// ── Image Card ─────────────────────────────────────────────────────
function ImageCard({ att }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError]   = useState(false);
  const url = absUrl(att.url);

  return (
    <a href={url} target="_blank" rel="noreferrer" className="ac-image-wrap">
      {!loaded && !error && <div className="ac-image-skeleton"/>}
      {error
        ? <div className="ac-image-error">🖼️ Image unavailable</div>
        : <img
            src={url}
            alt={att.filename || 'image'}
            className={`ac-image${loaded ? ' ac-image--loaded' : ''}`}
            onLoad={() => setLoaded(true)}
            onError={() => setError(true)}
          />
      }
      {att.filename && <div className="ac-image-name">{att.filename}</div>}
    </a>
  );
}

// ── Video Card ─────────────────────────────────────────────────────
function VideoCard({ att }) {
  const url = absUrl(att.url);
  return (
    <div className="ac-video-wrap">
      <video
        src={url}
        controls
        preload="metadata"
        className="ac-video"
        onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='flex'; }}
      />
      <div className="ac-video-error" style={{display:'none'}}>
        🎥 <a href={url} target="_blank" rel="noreferrer">{att.filename || 'Download video'}</a>
      </div>
      {att.filename && <div className="ac-media-name">🎥 {att.filename} {att.size_bytes ? `· ${formatBytes(att.size_bytes)}` : ''}</div>}
    </div>
  );
}

// ── Audio Card ─────────────────────────────────────────────────────
function AudioCard({ att }) {
  const url = absUrl(att.url);
  return (
    <div className="ac-audio-wrap">
      <div className="ac-audio-header">
        <span className="ac-audio-icon">🎵</span>
        <span className="ac-audio-name">{att.filename || 'Audio file'}</span>
        {att.size_bytes && <span className="ac-audio-size">{formatBytes(att.size_bytes)}</span>}
      </div>
      <audio
        src={url}
        controls
        className="ac-audio"
        onError={(e) => { e.target.style.display='none'; }}
      />
    </div>
  );
}

// ── Document Card ──────────────────────────────────────────────────
function DocumentCard({ att }) {
  const url  = absUrl(att.url);
  const icon = docIcon(att.mimetype);
  return (
    <a href={url} target="_blank" rel="noreferrer" className="ac-doc-wrap">
      <span className="ac-doc-icon">{icon}</span>
      <div className="ac-doc-info">
        <span className="ac-doc-name">{att.filename || 'Document'}</span>
        <span className="ac-doc-meta">
          {att.mimetype?.split('/')[1]?.toUpperCase() || 'FILE'}
          {att.size_bytes ? ` · ${formatBytes(att.size_bytes)}` : ''}
        </span>
      </div>
      <span className="ac-doc-dl">⬇</span>
    </a>
  );
}

// ── Main AttachmentCard ────────────────────────────────────────────
export default function AttachmentCard({ attachment }) {
  if (!attachment?.url) return null;
  const cat = getCategory(attachment);

  return (
    <div className={`ac-root ac-root--${cat}`}>
      {cat === 'image'    && <ImageCard    att={attachment}/>}
      {cat === 'video'    && <VideoCard    att={attachment}/>}
      {cat === 'audio'    && <AudioCard    att={attachment}/>}
      {cat === 'document' && <DocumentCard att={attachment}/>}
    </div>
  );
}

// ── AttachmentList — renders multiple attachments ──────────────────
export function AttachmentList({ attachments }) {
  if (!Array.isArray(attachments) || attachments.length === 0) return null;
  return (
    <div className="ac-list">
      {attachments.map((att, i) => (
        <AttachmentCard key={att.url || i} attachment={att}/>
      ))}
    </div>
  );
}
