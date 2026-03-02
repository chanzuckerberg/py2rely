import React, { useEffect, useState } from 'react'
import { useTheme, TYPE_COLOR, STATUS_COLOR } from '../theme.js'
import { fetchJob, fetchFiles } from '../api/http.js'
import LogViewer from './LogViewer.jsx'
import ResultsViewer from './ResultsViewer.jsx'
import Volume3DViewer from './Volume3DViewer.jsx'
import Slice2DViewer from './Slice2DViewer.jsx'
import AnalysisPanel from './AnalysisPanel.jsx'

const TABS = ['Params', 'Analysis', 'Log', 'Outputs', '3D Map', '2D Slices']
const HAS_3D_TYPES      = new Set(['Refine3D', 'Class3D', 'PostProcess', 'Reconstruct', 'MaskCreate', 'InitialModel'])
const HAS_ANALYSIS_TYPES = new Set(['Refine3D', 'Class3D', 'InitialModel', 'PostProcess', 'CtfFind', 'Polish', 'CtfRefine'])

function ParamsTable({ job, theme }) {
  if (!job) return null
  const params = Object.entries(job.parameters)

  return (
    <div style={{ padding: '12px 16px', overflowY: 'auto', height: '100%' }}>
      {job.command_history.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 11, color: theme.textMuted, marginBottom: 6, fontWeight: 600 }}>Command</p>
          <pre style={{
            fontSize: 10, fontFamily: 'monospace', color: theme.text,
            background: theme.surface2, padding: '8px 10px', borderRadius: 6,
            whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0,
            border: `1px solid ${theme.border}`,
          }}>
            {job.command_history[job.command_history.length - 1]?.replace(/^[\d\-: .]+: /, '')}
          </pre>
        </div>
      )}

      <p style={{ fontSize: 11, color: theme.textMuted, marginBottom: 6, fontWeight: 600 }}>Parameters</p>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <tbody>
          {params.map(([k, v]) => (
            <tr key={k} style={{ borderBottom: `1px solid ${theme.border}` }}>
              <td style={{ padding: '4px 8px 4px 0', color: theme.textMuted, whiteSpace: 'nowrap', verticalAlign: 'top', width: '40%' }}>{k}</td>
              <td style={{ padding: '4px 0', color: theme.text, fontFamily: 'monospace', wordBreak: 'break-all' }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function DetailPanel({ nodeId, pipeline, wsMessage }) {
  const theme = useTheme()
  const [tab,     setTab]     = useState('Params')
  const [job,     setJob]     = useState(null)
  const [files,   setFiles]   = useState(null)
  const [loading, setLoading] = useState(false)

  const node = pipeline?.nodes.find(n => n.id === nodeId)

  // Fetch job detail + file list whenever selection changes
  useEffect(() => {
    if (!nodeId) { setJob(null); setFiles(null); return }
    setLoading(true)
    Promise.all([
      fetchJob(nodeId).catch(() => null),
      fetchFiles(nodeId).then(d => d.files).catch(() => []),
    ]).then(([jobData, fileList]) => {
      setJob(jobData)
      setFiles(fileList)
    }).finally(() => setLoading(false))
  }, [nodeId])

  // Reset to Params tab on new selection
  useEffect(() => { setTab('Params') }, [nodeId])

  if (!nodeId) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: theme.textMuted, fontSize: 13 }}>
        Select a job to inspect
      </div>
    )
  }

  const typeColor    = TYPE_COLOR[node?.type]    ?? theme.textMuted
  const statusColor  = STATUS_COLOR[node?.status] ?? theme.textMuted
  const show3D       = HAS_3D_TYPES.has(node?.type) && node?.has_3d
  const showAnalysis = HAS_ANALYSIS_TYPES.has(node?.type)

  // overlayPath for MaskCreate: the input map (fn_in parameter)
  const overlayPath = node?.type === 'MaskCreate' ? job?.parameters?.fn_in : undefined

  const visibleTabs = TABS.filter(t => {
    if (t === '3D Map') return show3D
    if (t === '2D Slices') return show3D && node?.type !== 'MaskCreate'
    if (t === 'Analysis') return showAnalysis
    return true
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: theme.surface }}>

      {/* Header */}
      <div style={{ padding: '8px 16px', borderBottom: `1px solid ${theme.border}`, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'monospace', fontSize: 13, color: theme.text }}>{nodeId}</span>
          <span style={{ fontSize: 11, color: typeColor }}>{node?.type}</span>
          <span style={{ fontSize: 11, color: statusColor, marginLeft: 4 }}>● {node?.status}</span>
          {node?.timestamp && (
            <span style={{ fontSize: 10, color: theme.textMuted, marginLeft: 'auto' }}>{node.timestamp}</span>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${theme.border}`, flexShrink: 0 }}>
        {visibleTabs.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '6px 16px', fontSize: 12,
              background: 'none', border: 'none',
              borderBottom: tab === t ? `2px solid ${theme.accent}` : '2px solid transparent',
              color: tab === t ? theme.accent : theme.textMuted,
              cursor: 'pointer', marginBottom: -1,
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {loading
          ? <div style={{ padding: 16, color: theme.textMuted, fontSize: 12 }}>Loading…</div>
          : (
            <>
              {tab === 'Params'   && <ParamsTable job={job} theme={theme} />}
              {tab === 'Log'      && <LogViewer jobId={nodeId} jobStatus={node?.status} wsMessage={wsMessage} />}
              {tab === 'Outputs'  && <ResultsViewer job={job} files={files} />}
              {tab === 'Analysis' && <AnalysisPanel job={job} nodeId={nodeId} />}
              {tab === '3D Map'   && (
                <Volume3DViewer
                  jobId={nodeId}
                  jobType={node?.type}
                  files={files}
                  overlayPath={overlayPath}
                />
              )}
              {tab === '2D Slices' && (
                <Slice2DViewer
                  jobId={nodeId}
                  jobType={node?.type}
                  files={files}
                />
              )}
            </>
          )
        }
      </div>
    </div>
  )
}
