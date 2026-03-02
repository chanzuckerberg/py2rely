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
