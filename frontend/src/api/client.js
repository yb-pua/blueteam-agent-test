const BASE = '/api/v1'

export async function apiGet(path) {
  const resp = await fetch(`${BASE}${path}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function apiPost(path, body) {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function apiDelete(path) {
  const resp = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function apiUpload(path, file) {
  const fd = new FormData()
  fd.append('file', file)
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    body: fd,
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}