// src/components/messaging/MessageAttachments.jsx — v2 Bulletproof
// Fix: onAttachmentsReady via ref — never causes setState-in-render

import { useState, useRef, useCallback, useEffect } from 'react';
import axios from 'axios';

const UPLOAD_URL   = 'import.meta.env.VITE_API_BASE_URL + '/messaging/upload/'';
const ACCEPT_TYPES = [
  'image/jpeg','image/png','image/gif','image/webp',
  'video/mp4','video/webm','video/quicktime',
  'audio/mpeg','audio/wav','audio/ogg','audio/mp4',
  'application/pdf','text/plain','application/zip',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
].join(',');

const MAX_MB = { image:10, video:50, audio:20, document:20 };

const getMimeCategory = (mime='') => {
  if (mime.startsWith('image/')) return 'image';
  if (mime.startsWith('video/')) return 'video';
  if (mime.startsWith('audio/')) return 'audio';
  return 'document';
};
const getCategoryIcon = (cat) => ({ image:'🖼️', video:'🎥', audio:'🎵', document:'📄' }[cat] || '📎');
const formatBytes = (b=0) => b < 1024 ? `${b}B` : b < 1048576 ? `${(b/1024).toFixed(1)}KB` : `${(b/1048576).toFixed(1)}MB`;

export default function MessageAttachments({ onAttachmentsReady, onClear, disabled=false }) {
  const [items, setItems]       = useState([]);
  const [dragging, setDragging] = useState(false);
  const inputRef                = useRef(null);
  const abortRefs               = useRef({});

  // ── KEY FIX: keep onAttachmentsReady in a ref ──────────────────
  // This prevents useEffect from re-running on every render
  const onReadyRef = useRef(onAttachmentsReady);
  useEffect(() => { onReadyRef.current = onAttachmentsReady; }, [onAttachmentsReady]);

  // ── Notify parent AFTER render via useEffect ───────────────────
  useEffect(() => {
    const done = items.filter(i => i.status === 'done' && i.result).map(i => i.result);
    // Use setTimeout to ensure we're not inside a render cycle
    const tid = setTimeout(() => { onReadyRef.current?.(done); }, 0);
    return () => clearTimeout(tid);
  }, [items]);

  const updateItem = useCallback((id, patch) =>
    setItems(prev => prev.map(i => i.id === id ? { ...i, ...patch } : i)), []);

  const validate = (file) => {
    if (!file?.name) return 'Invalid file';
    const cat = getMimeCategory(file.type);
    if (file.size === 0) return 'File is empty';
    if (file.size > (MAX_MB[cat] || 20) * 1024 * 1024)
      return `Exceeds ${MAX_MB[cat] || 20}MB limit`;
    return null;
  };

  const uploadItem = useCallback((item) => {
    const ctrl = new AbortController();
    abortRefs.current[item.id] = ctrl;
    updateItem(item.id, { status: 'uploading', progress: 0 });

    const fd    = new FormData();
    fd.append('files', item.file);
    const token = localStorage.getItem('adminAccessToken') || '';

    axios.post(UPLOAD_URL, fd, {
      signal: ctrl.signal,
      headers: {
        'Content-Type': 'multipart/form-data',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      onUploadProgress: (e) => {
        const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 0;
        updateItem(item.id, { progress: pct });
      },
    })
    .then(({ data }) => {
      const att = data?.attachments?.[0];
      if (att) {
        updateItem(item.id, { status: 'done', result: att, progress: 100 });
      } else {
        updateItem(item.id, { status: 'error', error: data?.errors?.[0]?.error || 'Upload failed' });
      }
    })
    .catch((err) => {
      if (axios.isCancel(err)) {
        updateItem(item.id, { status: 'pending', progress: 0 });
      } else {
        updateItem(item.id, { status: 'error', error: err?.response?.data?.detail || 'Upload failed' });
      }
    })
    .finally(() => { delete abortRefs.current[item.id]; });
  }, [updateItem]);

  const addFiles = useCallback((fileList) => {
    const newItems = Array.from(fileList || []).map(file => {
      const err = validate(file);
      const cat = getMimeCategory(file.type);
      return {
        id:       crypto.randomUUID(),
        file, progress: 0,
        preview:  cat === 'image' ? URL.createObjectURL(file) : null,
        status:   err ? 'error' : 'pending',
        result:   null, error: err || null, category: cat,
      };
    });
    setItems(prev => [...prev, ...newItems]);
    newItems.filter(i => i.status === 'pending').forEach(uploadItem);
  }, [uploadItem]);

  const removeItem = useCallback((id) => {
    abortRefs.current[id]?.abort();
    setItems(prev => {
      const item = prev.find(i => i.id === id);
      if (item?.preview) URL.revokeObjectURL(item.preview);
      return prev.filter(i => i.id !== id);
    });
  }, []);

  const retryItem = useCallback((id) => {
    setItems(prev => {
      const item = prev.find(i => i.id === id);
      if (item) setTimeout(() => uploadItem({ ...item, status:'pending' }), 50);
      return prev.map(i => i.id === id ? { ...i, status:'pending', error:null, progress:0 } : i);
    });
  }, [uploadItem]);

  const clearAll = useCallback(() => {
    Object.values(abortRefs.current).forEach(c => c.abort());
    abortRefs.current = {};
    setItems(prev => { prev.forEach(i => { if (i.preview) URL.revokeObjectURL(i.preview); }); return []; });
    onClear?.();
  }, [onClear]);

  const onDragOver  = (e) => { e.preventDefault(); if (!disabled) setDragging(true); };
  const onDragLeave = ()  => setDragging(false);
  const onDrop      = (e) => { e.preventDefault(); setDragging(false); if (!disabled) addFiles(e.dataTransfer.files); };

  if (items.length === 0) return (
    <div
      className={`ma-dropzone${dragging?' ma-dropzone--active':''}${disabled?' ma-dropzone--disabled':''}`}
      onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <span className="ma-dz-icon">📎</span>
      <span className="ma-dz-text">Drag & drop or click to attach</span>
      <span className="ma-dz-hint">Images · Videos · Audio · Documents (max 50MB)</span>
      <input ref={inputRef} type="file" multiple accept={ACCEPT_TYPES}
        style={{display:'none'}} onChange={e => addFiles(e.target.files)}/>
    </div>
  );

  return (
    <div className="ma-root">
      <div className="ma-list">
        {items.map(item => (
          <AttachmentItem key={item.id} item={item}
            onRemove={() => removeItem(item.id)}
            onRetry={() => retryItem(item.id)}/>
        ))}
        <button className="ma-add-more" onClick={() => inputRef.current?.click()} disabled={disabled}>＋</button>
      </div>
      <div className="ma-footer">
        <span className="ma-count">{items.filter(i=>i.status==='done').length}/{items.length} uploaded</span>
        <button className="ma-clear" onClick={clearAll}>✕ Clear all</button>
      </div>
      <input ref={inputRef} type="file" multiple accept={ACCEPT_TYPES}
        style={{display:'none'}} onChange={e => addFiles(e.target.files)}/>
    </div>
  );
}

function AttachmentItem({ item, onRemove, onRetry }) {
  const { file, preview, progress, status, error, category } = item;
  return (
    <div className={`ma-item ma-item--${status}`}>
      <div className="ma-preview">
        {preview
          ? <img src={preview} alt={file.name} className="ma-thumb"/>
          : <span className="ma-icon">{getCategoryIcon(category)}</span>}
      </div>
      <div className="ma-info">
        <span className="ma-name" title={file.name}>{file.name}</span>
        <span className="ma-size">{formatBytes(file.size)}</span>
        {status==='error' && <span className="ma-error">{error}</span>}
      </div>
      {status==='uploading' && (
        <div className="ma-bar-wrap">
          <div className="ma-bar" style={{width:`${progress}%`}}/>
        </div>
      )}
      <div className="ma-status">
        {status==='done'      && <span className="ma-ok">✓</span>}
        {status==='uploading' && <span className="ma-spin">⟳</span>}
        {status==='error'     && <button className="ma-retry" onClick={onRetry}>↺</button>}
      </div>
      <button className="ma-remove" onClick={onRemove}>✕</button>
    </div>
  );
}
