// src/api/endpoints/Messaging.js
import client from '../client';

// ── InternalChat ─────────────────────────────────────────────────────────────
export const chatApi = {
  list:          (params = {})              => client.get('messaging/chats/', { params }),
  get:           (id)                       => client.get(`messaging/chats/${id}/`),
  createDirect:  (userId)                   => client.post('messaging/chats/direct/', { user_id: userId }),
  createGroup:   (name, memberIds)          => client.post('messaging/chats/group/', { name, member_ids: memberIds }),
  getMessages:   (chatId, params = {})      => client.get(`messaging/chats/${chatId}/messages/`, { params }),
  sendMessage:   (chatId, payload)          => client.post(`messaging/chats/${chatId}/send/`, payload),
  deleteMessage: (chatId, messageId)        => client.delete(`messaging/chats/${chatId}/messages/${messageId}/`),
};

// ── AdminBroadcast ────────────────────────────────────────────────────────────
export const broadcastApi = {
  list:      (params = {}) => client.get('messaging/broadcasts/', { params }),
  get:       (id)          => client.get(`messaging/broadcasts/${id}/`),
  create:    (payload)     => client.post('messaging/broadcasts/', payload),
  update:    (id, payload) => client.patch(`messaging/broadcasts/${id}/`, payload),
  delete:    (id)          => client.delete(`messaging/broadcasts/${id}/`),
  send:      (id)          => client.post(`messaging/broadcasts/${id}/send/`),
  sendAsync: (id)          => client.post(`messaging/broadcasts/${id}/send-async/`),
};

// ── SupportThread ─────────────────────────────────────────────────────────────
export const supportApi = {
  list:       (params = {})                              => client.get('messaging/support/', { params }),
  get:        (id)                                       => client.get(`messaging/support/${id}/`),
  create:     (subject, initial_message, priority)       => client.post('messaging/support/create/', { subject, initial_message, priority }),
  reply:      (threadId, content, attachments = [], is_internal_note = false) => client.post(`messaging/support/${threadId}/reply/`, { content, attachments, is_internal_note }),
  transition: (threadId, status)                         => client.post(`messaging/support/${threadId}/transition/`, { status }),
  assign:     (threadId, agentId)                        => client.post(`messaging/support/${threadId}/assign/`, { agent_id: agentId }),
};

// ── UserInbox ─────────────────────────────────────────────────────────────────
export const inboxApi = {
  list:        (params = {}) => client.get('messaging/inbox/', { params }),
  unreadCount: ()            => client.get('messaging/inbox/unread-count/'),
  markRead:    (itemIds)     => client.post('messaging/inbox/mark-read/', { item_ids: itemIds }),
  archive:     (id)          => client.post(`messaging/inbox/${id}/archive/`),
};