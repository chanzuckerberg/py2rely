import React, { useState, useEffect, useCallback, useRef } from 'react'
import { ThemeContext, themes } from './theme.js'
import { fetchPipeline } from './api/http.js'
import { createSocket } from './api/socket.js'
import Topbar from './components/Topbar.jsx'
import Sidebar from './components/Sidebar.jsx'
import DAGCanvas from './components/DAGCanvas.jsx'
import DetailPanel from './components/DetailPanel.jsx'

const SPLIT_KEY    = 'relionui-split'
const DEFAULT_SPLIT = 55   // % of right panel height for DAG canvas

export default function App() {
  const [themeName,  setThemeName]  = useState(() => localStorage.getItem('theme') ?? 'dark')
  const theme = themes[themeName]

  const [pipeline,   setPipeline]   = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [wsStatus,   setWsStatus]   = useState('disconnected')
  const [wsMessage,  setWsMessage]  = useState(null)
  const [error,      setError]      = useState(null)

  // Draggable split state (% of right panel for DAG)
  const [splitPct, setSplitPct] = useState(() => {
    const saved = parseFloat(localStorage.getItem(SPLIT_KEY))
    return isNaN(saved) ? DEFAULT_SPLIT : saved
  })
  const splitRef   = useRef(null)   // right-panel container
  const draggingRef = useRef(false)

  const loadPipeline = useCallback(async () => {
    try {
      const data = await fetchPipeline()
      setPipeline(data)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => { loadPipeline() }, [loadPipeline])

  useEffect(() => {
    const sock = createSocket(
      msg => {
        setWsMessage(msg)
        if (msg.type === 'pipeline_refresh' || msg.type === 'status_update') {
          loadPipeline()
        }
      },
      setWsStatus
    )
    return () => sock.close()
  }, [loadPipeline])

  // ── Draggable split ──────────────────────────────────────────────────────
  const onDividerMouseDown = useCallback(e => {
    e.preventDefault()
    draggingRef.current = true

    const onMove = mv => {
      if (!draggingRef.current || !splitRef.current) return
      const rect = splitRef.current.getBoundingClientRect()
      const pct  = Math.max(15, Math.min(85, ((mv.clientY - rect.top) / rect.height) * 100))
      setSplitPct(pct)
    }

    const onUp = () => {
      draggingRef.current = false
      setSplitPct(prev => {
        localStorage.setItem(SPLIT_KEY, prev)
        return prev
      })
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [])

  const toggleTheme = () => {
    const next = themeName === 'dark' ? 'light' : 'dark'
    setThemeName(next)
    localStorage.setItem('theme', next)
  }

  return (
    <ThemeContext.Provider value={theme}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: theme.bg, color: theme.text }}>
        <Topbar
          pipeline={pipeline}
          wsStatus={wsStatus}
          themeName={themeName}
          onToggleTheme={toggleTheme}
        />

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <Sidebar
            pipeline={pipeline}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />

          {/* Right panel: DAG (top) + divider + detail (bottom) */}
          <div ref={splitRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* DAG canvas */}
            <div style={{ height: `${splitPct}%`, overflow: 'hidden', position: 'relative', flexShrink: 0 }}>
              {error
                ? <div style={{ padding: 32, color: '#ef4444', fontFamily: 'monospace', fontSize: 13 }}>Error: {error}</div>
                : <DAGCanvas pipeline={pipeline} selectedId={selectedId} onSelect={setSelectedId} />
              }
            </div>

            {/* Draggable divider */}
            <div
              onMouseDown={onDividerMouseDown}
              style={{
                height: 5,
                background: theme.border,
                cursor: 'row-resize',
                flexShrink: 0,
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = theme.accent}
              onMouseLeave={e => e.currentTarget.style.background = theme.border}
            />

            {/* Detail panel */}
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <DetailPanel
                nodeId={selectedId}
                pipeline={pipeline}
                wsMessage={wsMessage}
              />
            </div>
          </div>
        </div>
      </div>
    </ThemeContext.Provider>
  )
}
