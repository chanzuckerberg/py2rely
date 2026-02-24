import React, { useEffect, useState } from 'react'
import { useTheme } from '../theme.js'
import Refine3DAnalysis from './Refine3DAnalysis.jsx'
import Class3DAnalysis from './Class3DAnalysis.jsx'
import PostProcessAnalysis from './PostProcessAnalysis.jsx'
import CtfFindAnalysis from './CtfFindAnalysis.jsx'
import PolishAnalysis from './PolishAnalysis.jsx'
import CtfRefineAnalysis from './CtfRefineAnalysis.jsx'

export default function AnalysisPanel({ job, nodeId }) {
  const theme = useTheme()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    if (!nodeId) return
    setData(null)
    setLoading(true)
    setError(null)
    fetch(`/api/analysis/${nodeId}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d  => { setData(d);       setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [nodeId])

  if (loading) {
    return <div style={{ padding: 16, color: theme.textMuted, fontSize: 12 }}>Loading analysis…</div>
  }
  if (error) {
    return <div style={{ padding: 16, color: '#ef4444', fontSize: 12 }}>Error: {error}</div>
  }
  if (!data) return null
  if (data.available === false) {
    const msg = data.error ? `Error: ${data.error}` : 'No analysis available for this job type.'
    return <div style={{ padding: 16, color: theme.textMuted, fontSize: 12 }}>{msg}</div>
  }

  switch (job?.type) {
    case 'Refine3D':    return <Refine3DAnalysis    data={data} />
    case 'Class3D':     return <Class3DAnalysis     data={data} />
    case 'PostProcess': return <PostProcessAnalysis data={data} />
    case 'CtfFind':     return <CtfFindAnalysis     data={data} />
    case 'Polish':      return <PolishAnalysis      data={data} />
    case 'CtfRefine':   return <CtfRefineAnalysis   data={data} />
    default:
      return <div style={{ padding: 16, color: theme.textMuted, fontSize: 12 }}>No analysis available.</div>
  }
}
