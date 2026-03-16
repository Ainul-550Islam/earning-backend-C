const API_BASE = '/api/withdrawals/'

function getAuthHeader() {
  const token = localStorage.getItem('token') || localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchWithdrawals(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const url = qs ? `${API_BASE}?${qs}` : API_BASE
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json', ...getAuthHeader() } })
  if (!res.ok) throw res
  return res.json()
}

export async function processWithdrawal(id) {
  const url = `${API_BASE}${id}/process/`
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...getAuthHeader() } })
  if (!res.ok) throw res
  return res.json()
}

export async function rejectWithdrawal(id, reason='Rejected by admin') {
  const url = `${API_BASE}${id}/reject/`
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...getAuthHeader() }, body: JSON.stringify({ reason }) })
  if (!res.ok) throw res
  return res.json()
}

export default { fetchWithdrawals, processWithdrawal, rejectWithdrawal }
