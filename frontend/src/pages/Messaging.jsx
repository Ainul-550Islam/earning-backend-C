// src/pages/Messaging.jsx
// Full redesign — Icon + Title + BigNumber + Sparkline + Neon Border
// Real backend data via useMessaging hooks + WebSocket

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useChats, useChatMessages, useInbox, useSupportThreads, useBroadcasts } from '../hooks/useMessaging';
import { useChatWebSocket, useSupportWebSocket, wsStateColor, wsStateLabel } from '../hooks/useWebSocket';
import '../styles/Messaging.css';
import MessageAttachments from '../components/messaging/MessageAttachments';
import '../styles/MessageAttachments.css';
import { AttachmentList } from '../components/messaging/AttachmentCard';
import '../styles/AttachmentCard.css';

// ── Mini Sparkline SVG ────────────────────────────────────────────
function Sparkline({ data = [], color = '#00f3ff', height = 32, width = 80 }) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');
  const areaBottom = `${width},${height} 0,${height}`;
  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id={`sg-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`${pts} ${areaBottom}`} fill={`url(#sg-${color.replace('#','')})`}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        style={{ filter: `drop-shadow(0 0 3px ${color})` }}/>
      {/* Last point dot */}
      {data.length > 0 && (() => {
        const last = data[data.length - 1];
        const lx = width;
        const ly = height - ((last - min) / range) * height;
        return <circle cx={lx} cy={ly} r="2.5" fill={color}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}/>;
      })()}
    </svg>
  );
}

// ── Stat Card (Top summary cards) ────────────────────────────────
function StatCard({ icon, label, value, sub, color = '#00f3ff', spark = [], trend }) {
  return (
    <div className="msg-stat-card" style={{ '--card-color': color }}>
      <div className="msg-stat-top">
        <div className="msg-stat-icon">{icon}</div>
        <div className="msg-stat-spark">
          <Sparkline data={spark} color={color} width={70} height={28}/>
        </div>
      </div>
      <div className="msg-stat-value">{value}</div>
      <div className="msg-stat-label">{label}</div>
      {(sub || trend != null) && (
        <div className="msg-stat-sub">
          {trend != null && (
            <span className={`msg-stat-trend ${trend >= 0 ? 'up' : 'down'}`}>
              {trend >= 0 ? '▲' : '▼'} {Math.abs(trend)}%
            </span>
          )}
          {sub && <span>{sub}</span>}
        </div>
      )}
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────
const Icon = {
  Chat:      () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  Inbox:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>,
  Support:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  Broadcast: () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.07 13 19.79 19.79 0 0 1 1 4.18 2 2 0 0 1 2.97 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21 17z"/><polyline points="16 2 20 2 20 6"/><line x1="14" y1="8" x2="20" y2="2"/></svg>,
  Send:      () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>,
  Plus:      () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  Trash:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>,
  Archive:   () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>,
  Check:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>,
  Group:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  Users:     () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  Activity:  () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  Mail:      () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>,
  Bell:      () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
  Ticket:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v2z"/></svg>,
  Signal:    () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="2" y1="20" x2="2" y2="14"/><line x1="7" y1="20" x2="7" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="17" y1="20" x2="17" y2="10"/><line x1="22" y1="20" x2="22" y2="14"/></svg>,
};

const TABS = [
  { key: 'chats',     label: 'Chats',     icon: Icon.Chat      },
  { key: 'inbox',     label: 'Inbox',     icon: Icon.Inbox     },
  { key: 'support',   label: 'Support',   icon: Icon.Support   },
  { key: 'broadcast', label: 'Broadcast', icon: Icon.Broadcast },
];

const STATUS_COLOR = {
  ACTIVE:'#00f3ff', ARCHIVED:'#888', DELETED:'#ff3355',
  DRAFT:'#ffd700', SCHEDULED:'#00f3ff', SENDING:'#ff00ff',
  SENT:'#00ff88', FAILED:'#ff3355', CANCELLED:'#888',
  OPEN:'#00f3ff', IN_PROGRESS:'#ff00ff', WAITING_USER:'#ffd700',
  RESOLVED:'#00ff88', CLOSED:'#888',
  NORMAL:'#00f3ff', HIGH:'#ffd700', URGENT:'#ff3355',
};

// fake spark data helper (replace with real time-series when available)
function fakeSpark(base, len = 8) {
  return Array.from({ length: len }, (_, i) =>
    Math.max(0, base + Math.round((Math.random() - 0.4) * base * 0.6 + i * 0.5))
  );
}

// ── WS Badge ─────────────────────────────────────────────────────
function WSBadge({ state }) {
  return (
    <div className="msg-ws-badge" style={{ '--ws-color': wsStateColor(state) }}>
      <span className="msg-ws-dot"/>
      {wsStateLabel(state)}
    </div>
  );
}

// ── Typing ────────────────────────────────────────────────────────
function TypingIndicator({ users }) {
  if (!users.length) return null;
  return (
    <div className="msg-typing">
      <div className="msg-typing-dots"><span/><span/><span/></div>
      <span className="msg-typing-text">{users.map(u => u.user_name).join(', ')} typing…</span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// CHATS PANEL
// ═══════════════════════════════════════════════════════════════════
function ChatsPanel() {
  const { chats, loading, createDirect, createGroup } = useChats();
  const [activeChatId, setActiveChatId] = useState(null);
  const [showNewDirect, setShowNewDirect] = useState(false);
  const [showNewGroup,  setShowNewGroup]  = useState(false);
  const [directUserId,  setDirectUserId]  = useState('');
  const [groupName,     setGroupName]     = useState('');
  const [groupMembers,  setGroupMembers]  = useState('');
  const activeChat = chats.find(c => c.id === activeChatId);

  // Stats derived from real data
  const totalChats   = chats.length;
  const groupCount   = chats.filter(c => c.is_group).length;
  const directCount  = chats.filter(c => !c.is_group).length;
  const activeCount  = chats.filter(c => c.status === 'ACTIVE').length;

  const handleCreateDirect = async () => {
    if (!directUserId.trim()) return;
    const chat = await createDirect(directUserId.trim());
    if (chat) { setActiveChatId(chat.id); setShowNewDirect(false); setDirectUserId(''); }
  };
  const handleCreateGroup = async () => {
    if (!groupName.trim()) return;
    const ids = groupMembers.split(',').map(s => s.trim()).filter(Boolean);
    const chat = await createGroup(groupName.trim(), ids);
    if (chat) { setActiveChatId(chat.id); setShowNewGroup(false); setGroupName(''); setGroupMembers(''); }
  };

  return (
    <div className="msg-panel-full">
      {/* ── Stat Cards Row ── */}
      <div className="msg-stats-row">
        <StatCard icon={<Icon.Chat/>}     label="Total Chats"   value={totalChats}  color="#00f3ff" spark={fakeSpark(totalChats)}  trend={12}/>
        <StatCard icon={<Icon.Activity/>} label="Active"        value={activeCount} color="#00ff88" spark={fakeSpark(activeCount)} trend={5}/>
        <StatCard icon={<Icon.Group/>}    label="Group Chats"   value={groupCount}  color="#ff00ff" spark={fakeSpark(groupCount)}  trend={-2}/>
        <StatCard icon={<Icon.Users/>}    label="Direct Msgs"   value={directCount} color="#ffd700" spark={fakeSpark(directCount)} trend={8}/>
      </div>

      {/* ── Split: list + chat ── */}
      <div className="msg-split">
        <div className="msg-list-col">
          <div className="msg-list-header">
            <span className="msg-col-title">Conversations</span>
            <div className="msg-header-actions">
              <button className="msg-icon-btn" title="New Direct" onClick={() => { setShowNewDirect(v=>!v); setShowNewGroup(false); }}><Icon.Chat/></button>
              <button className="msg-icon-btn" title="New Group"  onClick={() => { setShowNewGroup(v=>!v);  setShowNewDirect(false); }}><Icon.Group/></button>
            </div>
          </div>

          {showNewDirect && (
            <div className="msg-quick-form">
              <input className="msg-input" placeholder="User ID" value={directUserId}
                onChange={e => setDirectUserId(e.target.value)}
                onKeyDown={e => e.key==='Enter' && handleCreateDirect()}/>
              <button className="msg-btn-primary" onClick={handleCreateDirect}>Open Chat</button>
            </div>
          )}
          {showNewGroup && (
            <div className="msg-quick-form">
              <input className="msg-input" placeholder="Group name" value={groupName} onChange={e => setGroupName(e.target.value)}/>
              <input className="msg-input" placeholder="Member IDs (comma separated)" value={groupMembers} onChange={e => setGroupMembers(e.target.value)}/>
              <button className="msg-btn-primary" onClick={handleCreateGroup}>Create Group</button>
            </div>
          )}

          <div className="msg-list-scroll">
            {loading && <div className="msg-loading"><div className="msg-spinner"/></div>}
            {!loading && chats.length === 0 && <div className="msg-empty">No conversations yet</div>}
            {chats.map(chat => (
              <ChatListCard key={chat.id} chat={chat} active={activeChatId===chat.id} onClick={() => setActiveChatId(chat.id)}/>
            ))}
          </div>
        </div>

        <div className="msg-chat-col">
          {activeChatId
            ? <ChatWindow chat={activeChat} chatId={activeChatId}/>
            : <div className="msg-no-chat"><Icon.Chat/><p>Select a conversation</p></div>
          }
        </div>
      </div>
    </div>
  );
}

// ── Chat List Card ────────────────────────────────────────────────
function ChatListCard({ chat, active, onClick }) {
  const color = STATUS_COLOR[chat.status] || '#888';
  const msgCount = chat.message_count || 0;
  return (
    <div className={`msg-list-card ${active ? 'active' : ''}`} onClick={onClick}
      style={{ '--card-accent': color }}>
      {/* Neon border top */}
      <div className="msg-lc-glow-top"/>
      <div className="msg-lc-row1">
        <div className="msg-lc-icon">
          {chat.is_group ? <Icon.Group/> : <Icon.Chat/>}
        </div>
        <div className="msg-lc-info">
          <div className="msg-lc-name">{chat.name || 'Direct Message'}</div>
          <div className="msg-lc-type">{chat.is_group ? 'GROUP' : 'DIRECT'}</div>
        </div>
        <div className="msg-lc-status-dot" style={{ background: color, boxShadow: `0 0 8px ${color}` }}/>
      </div>

      <div className="msg-lc-big">{msgCount > 0 ? msgCount : '—'}</div>
      <div className="msg-lc-big-label">messages</div>

      <div className="msg-lc-row2">
        <div className="msg-lc-preview">{chat.last_message?.content?.slice(0,38) || 'No messages yet'}</div>
        <div className="msg-lc-spark">
          <Sparkline data={fakeSpark(msgCount || 3)} color={color} width={55} height={22}/>
        </div>
      </div>

      <div className="msg-lc-footer">
        <span className="msg-lc-status-tag" style={{ color, borderColor: color }}>
          {chat.status}
        </span>
        {chat.unread_count > 0 && (
          <span className="msg-lc-unread">{chat.unread_count}</span>
        )}
      </div>
    </div>
  );
}

// ── Chat Window ───────────────────────────────────────────────────
function ChatWindow({ chat, chatId }) {
  const { messages, setMessages, loading, hasMore, deleteMessage, loadMore } = useChatMessages(chatId);
  const [text, setText] = useState('');
  const bottomRef   = useRef(null);
  const typingTimer    = useRef(null);
  const [attachments, setAttachments] = useState([]); // uploaded attachment objects
  const [showAttach,  setShowAttach]  = useState(false);

  const handleNewMessage = useCallback((wsMsg) => {
    const msg = {
      id: wsMsg.message_id, chat: wsMsg.chat_id,
      sender: { id: wsMsg.sender_id, username: wsMsg.sender_name },
      content: wsMsg.content, message_type: wsMsg.message_type,
      status: 'SENT', is_edited: false, attachments: Array.isArray(wsMsg.attachments) ? wsMsg.attachments : [], created_at: wsMsg.created_at,
    };
    setMessages(prev => prev.find(m => m.id === msg.id) ? prev : [...prev, msg]);
  }, [setMessages]);

  const { sendMessage: wsSend, sendTyping, state: wsState, typingUsers } = useChatWebSocket(chatId, {
    onNewMessage: handleNewMessage,
  });

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages.length]);

  const handleSend = async () => {
    if (!text.trim()) return;
    const msgAttachments = attachments.length ? attachments : [];
    const sent = wsSend(text.trim() || ' ', { attachments: msgAttachments });
    if (!sent) {
      const { chatApi } = await import('../api/endpoints/Messaging');
      const { data } = await chatApi.sendMessage(chatId, {
        content: text.trim() || ' ',
        message_type: 'TEXT',
        attachments: msgAttachments,
      });
      setMessages(prev => prev.find(m => m.id === data.id) ? prev : [...prev, data]);
    }
    setText(''); setAttachments([]); setShowAttach(false);
    sendTyping(false); clearTimeout(typingTimer.current);
  };

  const handleKey = (e) => {
    if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); return; }
    sendTyping(true);
    clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => sendTyping(false), 2000);
  };

  return (
    <div className="msg-chat-window">
      <div className="msg-chat-header">
        <div className="msg-avatar">{(chat?.name||'D').charAt(0).toUpperCase()}</div>
        <div style={{flex:1}}>
          <div className="msg-chat-title">{chat?.name||'Direct Message'}</div>
          <div className="msg-chat-sub">
            {chat?.is_group ? 'Group' : 'Direct'} ·{' '}
            <span style={{color: STATUS_COLOR[chat?.status]}}>{chat?.status}</span>
          </div>
        </div>
        <WSBadge state={wsState}/>
      </div>
      <div className="msg-messages-scroll">
        {hasMore && <button className="msg-load-more" onClick={loadMore} disabled={loading}>{loading ? 'Loading…' : 'Load older'}</button>}
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} onDelete={deleteMessage}/>)}
        <TypingIndicator users={typingUsers}/>
        <div ref={bottomRef}/>
      </div>
      <div className="msg-composer">
        {showAttach && (
          <MessageAttachments
            onAttachmentsReady={setAttachments}
            onClear={() => { setAttachments([]); setShowAttach(false); }}
          />
        )}
        <div className="msg-composer-row">
          <button
            className={`msg-attach-btn${showAttach ? ' active' : ''}`}
            onClick={() => setShowAttach(p => !p)}
            title="Attach files"
          >📎</button>
          <textarea className="msg-textarea" placeholder="Type a message… (Enter to send)"
            value={text} onChange={e => setText(e.target.value)} onKeyDown={handleKey} rows={2}/>
          <button
            className="msg-send-btn"
            onClick={handleSend}
            disabled={!text.trim() && attachments.length === 0}
          ><Icon.Send/></button>
        </div>
        {attachments.length > 0 && (
          <div className="msg-attach-ready">
            📎 {attachments.length} file{attachments.length > 1 ? 's' : ''} ready
          </div>
        )}
      </div>
    </div>
  );
}

function MessageBubble({ msg, onDelete }) {
  const isDeleted = msg.status === 'DELETED';
  if (msg.message_type === 'SYSTEM') return (
    <div className="msg-bubble system"><div className="msg-system-text">{msg.content}</div></div>
  );
  return (
    <div className={`msg-bubble ${isDeleted ? 'deleted' : ''}`}>
      <div className="msg-bubble-header">
        <span className="msg-sender">{msg.sender?.username||'Unknown'}</span>
        {msg.is_edited && <span className="msg-edited">edited</span>}
        <span className="msg-time">{new Date(msg.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
        {!isDeleted && <button className="msg-delete-btn" onClick={()=>onDelete(msg.id)}><Icon.Trash/></button>}
      </div>
      <div className="msg-bubble-content">{msg.content}</div>
      <AttachmentList attachments={msg.attachments}/>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// INBOX PANEL
// ═══════════════════════════════════════════════════════════════════
function InboxPanel() {
  const { items, unreadCount, loading, markRead, archive } = useInbox();
  const [filter, setFilter] = useState('all');

  const broadcastCount = items.filter(i => i.item_type==='BROADCAST').length;
  const supportCount   = items.filter(i => i.item_type==='SUPPORT').length;
  const chatCount      = items.filter(i => i.item_type==='CHAT').length;
  const archivedCount  = items.filter(i => i.is_archived).length;

  const filtered = items.filter(item => {
    if (filter==='unread')   return !item.is_read && !item.is_archived;
    if (filter==='archived') return item.is_archived;
    return !item.is_archived;
  });

  return (
    <div className="msg-panel-full">
      <div className="msg-stats-row">
        <StatCard icon={<Icon.Bell/>}     label="Total Items"  value={items.length}   color="#00f3ff" spark={fakeSpark(items.length)}   trend={3}/>
        <StatCard icon={<Icon.Mail/>}     label="Unread"       value={unreadCount}    color="#ff3355" spark={fakeSpark(unreadCount)}     sub="need attention"/>
        <StatCard icon={<Icon.Broadcast/>}label="Broadcasts"   value={broadcastCount} color="#ff00ff" spark={fakeSpark(broadcastCount)}  trend={1}/>
        <StatCard icon={<Icon.Archive/>}  label="Archived"     value={archivedCount}  color="#888"    spark={fakeSpark(archivedCount)}/>
      </div>

      <div className="msg-panel">
        <div className="msg-panel-header">
          <span className="msg-col-title">Inbox</span>
          {unreadCount > 0 && <span className="msg-unread-badge">{unreadCount} unread</span>}
          <div className="msg-header-actions">
            <button className="msg-btn-ghost" onClick={() => {
              const ids = items.filter(i=>!i.is_read).map(i=>i.id);
              if (ids.length) markRead(ids);
            }}>Mark all read</button>
          </div>
        </div>
        <div className="msg-filter-tabs">
          {['all','unread','archived'].map(f => (
            <button key={f} className={`msg-filter-tab ${filter===f?'active':''}`} onClick={()=>setFilter(f)}>
              {f.charAt(0).toUpperCase()+f.slice(1)}
            </button>
          ))}
        </div>
        <div className="msg-list-scroll" style={{flex:1}}>
          {loading && <div className="msg-loading"><div className="msg-spinner"/></div>}
          {!loading && filtered.length===0 && <div className="msg-empty">No items</div>}
          {filtered.map(item => <InboxCard key={item.id} item={item} onMarkRead={markRead} onArchive={archive}/>)}
        </div>
      </div>
    </div>
  );
}

function InboxCard({ item, onMarkRead, onArchive }) {
  const color = item.item_type==='BROADCAST' ? '#ff00ff' : item.item_type==='SUPPORT' ? '#ffd700' : '#00f3ff';
  const typeIcon = item.item_type==='BROADCAST' ? <Icon.Broadcast/> : item.item_type==='SUPPORT' ? <Icon.Ticket/> : <Icon.Chat/>;
  return (
    <div className={`msg-list-card ${!item.is_read?'active':''}`} style={{ '--card-accent': color }}>
      <div className="msg-lc-glow-top"/>
      <div className="msg-lc-row1">
        <div className="msg-lc-icon" style={{color}}>{typeIcon}</div>
        <div className="msg-lc-info">
          <div className="msg-lc-name">{item.title||'(No title)'}</div>
          <div className="msg-lc-type" style={{color}}>{item.item_type}</div>
        </div>
        {!item.is_read && <span className="msg-lc-unread">NEW</span>}
      </div>
      <div className="msg-lc-preview" style={{marginTop:'0.4rem'}}>{item.preview}</div>
      <div className="msg-lc-footer" style={{marginTop:'0.6rem'}}>
        <span className="msg-inbox-time">{new Date(item.created_at).toLocaleString()}</span>
        <div className="msg-inbox-actions">
          {!item.is_read && <button className="msg-icon-btn" onClick={()=>onMarkRead([item.id])}><Icon.Check/></button>}
          <button className="msg-icon-btn" onClick={()=>onArchive(item.id)}><Icon.Archive/></button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// SUPPORT PANEL
// ═══════════════════════════════════════════════════════════════════
function SupportPanel() {
  const { threads, loading, createThread, transitionThread } = useSupportThreads();
  const [activeThread, setActiveThread]   = useState(null);
  const [localMessages, setLocalMessages] = useState({});
  const [showNew, setShowNew]             = useState(false);
  const [newSubject, setNewSubject]       = useState('');
  const [newMessage, setNewMessage]       = useState('');
  const [replyText, setReplyText]         = useState('');
  const bottomRef = useRef(null);
  const thread = threads.find(t => t.id === activeThread);

  const openCount    = threads.filter(t => t.status==='OPEN').length;
  const inProgCount  = threads.filter(t => t.status==='IN_PROGRESS').length;
  const resolvedCount= threads.filter(t => t.status==='RESOLVED').length;
  const urgentCount  = threads.filter(t => t.priority==='URGENT').length;

  const handleNewSupportMsg = useCallback((wsMsg) => {
    const msg = { id: wsMsg.message_id, content: wsMsg.content, is_agent_reply: wsMsg.is_agent_reply, is_internal_note: wsMsg.is_internal_note, created_at: wsMsg.created_at };
    setLocalMessages(prev => {
      const existing = prev[wsMsg.thread_id] || [];
      return existing.find(m => m.id === msg.id) ? prev : { ...prev, [wsMsg.thread_id]: [...existing, msg] };
    });
  }, []);

  const { sendMessage: wsSend, state: wsState } = useSupportWebSocket(activeThread, { onNewMessage: handleNewSupportMsg });

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [localMessages, activeThread]);
  useEffect(() => {
    if (thread?.messages && !localMessages[thread.id]) {
      setLocalMessages(prev => ({ ...prev, [thread.id]: thread.messages }));
    }
  }, [thread]);

  const handleCreate = async () => {
    if (!newSubject.trim() || !newMessage.trim()) return;
    const t = await createThread(newSubject.trim(), newMessage.trim());
    if (t) { setActiveThread(t.id); setShowNew(false); setNewSubject(''); setNewMessage(''); }
  };

  const handleReply = async () => {
    if (!replyText.trim() || !activeThread) return;
    const sent = wsSend(replyText.trim());
    if (!sent) {
      const { supportApi } = await import('../api/endpoints/Messaging');
      const { data } = await supportApi.reply(activeThread, replyText.trim());
      setLocalMessages(prev => ({ ...prev, [activeThread]: [...(prev[activeThread]||[]), data] }));
    }
    setReplyText('');
  };

  const TRANSITIONS = {
    OPEN:['IN_PROGRESS','CLOSED'], IN_PROGRESS:['WAITING_USER','RESOLVED','CLOSED'],
    WAITING_USER:['IN_PROGRESS','RESOLVED','CLOSED'], RESOLVED:['OPEN','CLOSED'], CLOSED:[],
  };
  const threadMsgs = (activeThread && localMessages[activeThread]) || thread?.messages || [];

  return (
    <div className="msg-panel-full">
      <div className="msg-stats-row">
        <StatCard icon={<Icon.Ticket/>}   label="Open Tickets"  value={openCount}     color="#00f3ff" spark={fakeSpark(openCount)}     sub="awaiting"/>
        <StatCard icon={<Icon.Activity/>} label="In Progress"   value={inProgCount}   color="#ff00ff" spark={fakeSpark(inProgCount)}   trend={-1}/>
        <StatCard icon={<Icon.Check/>}    label="Resolved"      value={resolvedCount} color="#00ff88" spark={fakeSpark(resolvedCount)} trend={15}/>
        <StatCard icon={<Icon.Bell/>}     label="Urgent"        value={urgentCount}   color="#ff3355" spark={fakeSpark(urgentCount)}   sub="high priority"/>
      </div>

      <div className="msg-split">
        <div className="msg-list-col">
          <div className="msg-list-header">
            <span className="msg-col-title">Support Tickets</span>
            <button className="msg-icon-btn" onClick={() => setShowNew(v=>!v)}><Icon.Plus/></button>
          </div>
          {showNew && (
            <div className="msg-quick-form">
              <input className="msg-input" placeholder="Subject" value={newSubject} onChange={e => setNewSubject(e.target.value)}/>
              <textarea className="msg-textarea" placeholder="Describe your issue…" value={newMessage} onChange={e => setNewMessage(e.target.value)} rows={3}/>
              <button className="msg-btn-primary" onClick={handleCreate}>Submit Ticket</button>
            </div>
          )}
          <div className="msg-list-scroll">
            {loading && <div className="msg-loading"><div className="msg-spinner"/></div>}
            {threads.map(t => <SupportCard key={t.id} thread={t} active={activeThread===t.id} onClick={() => setActiveThread(t.id)}/>)}
          </div>
        </div>

        <div className="msg-chat-col">
          {thread ? (
            <div className="msg-chat-window">
              <div className="msg-chat-header">
                <div style={{flex:1}}>
                  <div className="msg-chat-title">{thread.subject}</div>
                  <div className="msg-chat-sub">
                    <span style={{color:STATUS_COLOR[thread.priority]}}>{thread.priority}</span>
                    {' · '}
                    <span style={{color:STATUS_COLOR[thread.status]}}>{thread.status.replace('_',' ')}</span>
                  </div>
                </div>
                <WSBadge state={wsState}/>
                <div className="msg-header-actions">
                  {(TRANSITIONS[thread.status]||[]).map(s => (
                    <button key={s} className="msg-btn-ghost" onClick={() => transitionThread(thread.id, s)}>{s.replace('_',' ')}</button>
                  ))}
                </div>
              </div>
              <div className="msg-messages-scroll">
                {threadMsgs.map((msg,i) => (
                  <div key={msg.id||i} className={`msg-support-msg ${msg.is_agent_reply?'agent':'user'} ${msg.is_internal_note?'internal':''}`}>
                    <div className="msg-bubble-header">
                      <span className="msg-sender">{msg.is_agent_reply?'🛡 Agent':'👤 User'}</span>
                      {msg.is_internal_note && <span className="msg-edited">internal note</span>}
                      <span className="msg-time">{new Date(msg.created_at).toLocaleString()}</span>
                    </div>
                    <div className="msg-bubble-content">{msg.content}</div>
                  </div>
                ))}
                <div ref={bottomRef}/>
              </div>
              {thread.status!=='CLOSED' && (
                <div className="msg-composer">
                  <textarea className="msg-textarea" placeholder="Write a reply… (Enter to send)" value={replyText}
                    onChange={e => setReplyText(e.target.value)}
                    onKeyDown={e => { if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); handleReply(); } }}
                    rows={2}/>
                  <button className="msg-send-btn" onClick={handleReply} disabled={!replyText.trim()}><Icon.Send/></button>
                </div>
              )}
            </div>
          ) : (
            <div className="msg-no-chat"><Icon.Support/><p>Select a ticket</p></div>
          )}
        </div>
      </div>
    </div>
  );
}

function SupportCard({ thread, active, onClick }) {
  const pColor = STATUS_COLOR[thread.priority] || '#888';
  const sColor = STATUS_COLOR[thread.status]   || '#888';
  return (
    <div className={`msg-list-card ${active?'active':''}`} onClick={onClick}
      style={{ '--card-accent': pColor }}>
      <div className="msg-lc-glow-top"/>
      <div className="msg-lc-row1">
        <div className="msg-lc-icon" style={{color: pColor}}><Icon.Ticket/></div>
        <div className="msg-lc-info">
          <div className="msg-lc-name">{thread.subject}</div>
          <div className="msg-lc-type" style={{color: pColor}}>{thread.priority}</div>
        </div>
        <div className="msg-lc-status-dot" style={{background:sColor, boxShadow:`0 0 8px ${sColor}`}}/>
      </div>
      <div className="msg-lc-big" style={{color: sColor}}>{thread.message_count||0}</div>
      <div className="msg-lc-big-label">replies</div>
      <div className="msg-lc-row2">
        <div className="msg-lc-spark"><Sparkline data={fakeSpark(thread.message_count||2)} color={pColor} width={55} height={22}/></div>
      </div>
      <div className="msg-lc-footer">
        <span className="msg-lc-status-tag" style={{color:sColor, borderColor:sColor}}>{thread.status.replace('_',' ')}</span>
        <span className="msg-inbox-time">{new Date(thread.created_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// BROADCAST PANEL
// ═══════════════════════════════════════════════════════════════════
function BroadcastPanel() {
  const { broadcasts, loading, createBroadcast, sendBroadcast, deleteBroadcast } = useBroadcasts();
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ title:'', body:'', audience_type:'ALL_USERS' });

  const sentCount      = broadcasts.filter(b => b.status==='SENT').length;
  const draftCount     = broadcasts.filter(b => b.status==='DRAFT').length;
  const totalRecip     = broadcasts.reduce((s,b) => s+(b.recipient_count||0), 0);
  const avgDelivery    = broadcasts.filter(b=>b.delivery_rate!=null).length
    ? Math.round(broadcasts.filter(b=>b.delivery_rate!=null).reduce((s,b)=>s+b.delivery_rate,0) / broadcasts.filter(b=>b.delivery_rate!=null).length)
    : 0;

  const handleCreate = async () => {
    if (!form.title.trim() || !form.body.trim()) return;
    await createBroadcast(form);
    setForm({ title:'', body:'', audience_type:'ALL_USERS' });
    setShowNew(false);
  };

  return (
    <div className="msg-panel-full">
      <div className="msg-stats-row">
        <StatCard icon={<Icon.Signal/>}    label="Total Sent"     value={sentCount}   color="#00ff88" spark={fakeSpark(sentCount)}   trend={22}/>
        <StatCard icon={<Icon.Broadcast/>} label="Drafts"         value={draftCount}  color="#ffd700" spark={fakeSpark(draftCount)}/>
        <StatCard icon={<Icon.Users/>}     label="Recipients"     value={totalRecip}  color="#00f3ff" spark={fakeSpark(totalRecip)}  trend={8}/>
        <StatCard icon={<Icon.Activity/>}  label="Avg. Delivery%" value={`${avgDelivery}%`} color="#ff00ff" spark={fakeSpark(avgDelivery)} sub="delivery rate"/>
      </div>

      <div className="msg-panel" style={{flex:1}}>
        <div className="msg-panel-header">
          <span className="msg-col-title">Admin Broadcasts</span>
          <button className="msg-btn-primary" onClick={() => setShowNew(v=>!v)}><Icon.Plus/> New Broadcast</button>
        </div>
        {showNew && (
          <div className="msg-broadcast-form">
            <input className="msg-input" placeholder="Title" value={form.title} onChange={e => setForm(f=>({...f,title:e.target.value}))}/>
            <select className="msg-select" value={form.audience_type} onChange={e => setForm(f=>({...f,audience_type:e.target.value}))}>
              <option value="ALL_USERS">All Users</option>
              <option value="ACTIVE_USERS">Active Users</option>
              <option value="USER_GROUP">User Group</option>
            </select>
            <textarea className="msg-textarea" placeholder="Broadcast message…" value={form.body}
              onChange={e => setForm(f=>({...f,body:e.target.value}))} rows={5}/>
            <div className="msg-form-actions">
              <button className="msg-btn-primary" onClick={handleCreate}>Save Draft</button>
              <button className="msg-btn-ghost" onClick={() => setShowNew(false)}>Cancel</button>
            </div>
          </div>
        )}
        <div className="msg-broadcast-grid">
          {loading && <div className="msg-loading"><div className="msg-spinner"/></div>}
          {broadcasts.map(b => <BroadcastCard key={b.id} b={b} onSend={sendBroadcast} onDelete={deleteBroadcast}/>)}
          {!loading && broadcasts.length===0 && <div className="msg-empty">No broadcasts yet</div>}
        </div>
      </div>
    </div>
  );
}

function BroadcastCard({ b, onSend, onDelete }) {
  const color = STATUS_COLOR[b.status] || '#888';
  return (
    <div className="msg-broadcast-card" style={{ '--card-color': color }}>
      <div className="msg-bc-header">
        <div className="msg-bc-icon" style={{color}}><Icon.Broadcast/></div>
        <div className="msg-bc-status" style={{color}}>{b.status}</div>
      </div>
      <div className="msg-bc-title">{b.title}</div>
      <div className="msg-bc-audience">{b.audience_type.replace('_',' ')}</div>

      {b.status==='SENT' && (
        <>
          <div className="msg-bc-bignum" style={{color}}>{b.delivered_count||0}</div>
          <div className="msg-bc-bignumlabel">delivered</div>
          <div className="msg-bc-sparkrow">
            <Sparkline data={fakeSpark(b.delivered_count||5)} color={color} width={100} height={30}/>
            {b.delivery_rate!=null && <span className="msg-bc-rate" style={{color}}>{b.delivery_rate}%</span>}
          </div>
          <div className="msg-bc-stats">
            <span>📨 {b.recipient_count}</span>
            <span>✅ {b.delivered_count}</span>
          </div>
        </>
      )}

      {b.status!=='SENT' && (
        <div className="msg-bc-body">{b.body.slice(0,100)}{b.body.length>100?'…':''}</div>
      )}

      <div className="msg-bc-actions">
        {['DRAFT','FAILED'].includes(b.status) && (
          <>
            <button className="msg-btn-primary" onClick={() => onSend(b.id)}>Send Now</button>
            <button className="msg-btn-ghost"   onClick={() => onSend(b.id,true)}>Queue</button>
          </>
        )}
        {['DRAFT','FAILED','CANCELLED'].includes(b.status) && (
          <button className="msg-btn-danger" onClick={() => onDelete(b.id)}><Icon.Trash/></button>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════
export default function Messaging() {
  const [activeTab, setActiveTab] = useState('chats');
  return (
    <div className="msg-root">
      <div className="msg-scanlines" aria-hidden/>
      <div className="msg-orb msg-orb-1" aria-hidden/>
      <div className="msg-orb msg-orb-2" aria-hidden/>
      <div className="msg-orb msg-orb-3" aria-hidden/>

      <div className="msg-header">
        <h1 className="msg-title">
          <span className="msg-title-accent">MSG</span>
          <span className="msg-title-main">SYSTEM</span>
        </h1>
        <div className="msg-tabs">
          {TABS.map(tab => (
            <button key={tab.key} className={`msg-tab ${activeTab===tab.key?'active':''}`} onClick={() => setActiveTab(tab.key)}>
              <tab.icon/><span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="msg-content">
        {activeTab==='chats'     && <ChatsPanel/>}
        {activeTab==='inbox'     && <InboxPanel/>}
        {activeTab==='support'   && <SupportPanel/>}
        {activeTab==='broadcast' && <BroadcastPanel/>}
      </div>
    </div>
  );
}