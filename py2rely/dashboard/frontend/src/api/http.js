export async function fetchPipeline() {
  const res = await fetch('/api/pipeline')
  if (!res.ok) throw new Error(`Pipeline fetch failed: ${res.status}`)
  return res.json()
}

export async function fetchJob(jobId) {
  const res = await fetch(`/api/job/${jobId}`)
  if (!res.ok) throw new Error(`Job fetch failed: ${res.status}`)
  return res.json()
}

export async function fetchLog(jobId) {
  const res = await fetch(`/api/log/${jobId}`)
  if (!res.ok) throw new Error(`Log fetch failed: ${res.status}`)
  return res.text()
}

export async function fetchFiles(jobId) {
  const res = await fetch(`/api/files/${jobId}`)
  if (!res.ok) throw new Error(`Files fetch failed: ${res.status}`)
  return res.json()
}

export function fileUrl(filepath) {
  return `/api/file/${filepath}`
}

export async function fetchMapInfo(filepath) {
  const res = await fetch(`/api/mapinfo/${filepath}`)
  if (!res.ok) return null
  return res.json()
}

// ── Mask Tuner ──────────────────────────────────────────────────────────────

export async function fetchMaps() {
  const res = await fetch('/api/maps')
  if (!res.ok) throw new Error(`Maps fetch failed: ${res.status}`)
  return res.json()
}

export async function generateMask(params) {
  const res = await fetch('/api/mask/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `Mask generation failed: ${res.status}`)
  }
  return res.json()
}

export async function filterMap(params) {
  const res = await fetch('/api/mask/filter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `Lowpass filter failed: ${res.status}`)
  }
  return res.json()
}

export async function saveMask(destPath) {
  const res = await fetch('/api/mask/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest_path: destPath }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `Mask save failed: ${res.status}`)
  }
  return res.json()
}
