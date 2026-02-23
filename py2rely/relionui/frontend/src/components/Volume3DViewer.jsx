import React, { useRef, useEffect, useState } from 'react'
import * as NGL from 'ngl'
import { useTheme } from '../theme.js'
import { fileUrl, fetchMapInfo } from '../api/http.js'

// Pick the most informative MRC file for a given job type
function pickBestMap(files, jobType) {
  const mrc = files?.filter(f => f.endsWith('.mrc')) ?? []
  if (!mrc.length) return null

  const priorities = {
    Refine3D:    ['run_class001.mrc', 'run_half1_class001_unfil.mrc'],
    PostProcess: ['postprocess_masked.mrc', 'postprocess.mrc'],
    Reconstruct: ['merged.mrc', 'half1.mrc'],
    MaskCreate:  ['mask.mrc'],
  }

  for (const name of (priorities[jobType] ?? [])) {
    if (mrc.includes(name)) return name
  }

  // Class3D / Class2D: highest-iteration class001
  if (jobType === 'Class3D' || jobType === 'Class2D') {
    const cls = mrc.filter(f => /run_it\d+_class001\.mrc$/.test(f))
    if (cls.length) {
      return cls.sort((a, b) => {
        const n = f => parseInt(f.match(/it(\d+)/)[1])
        return n(b) - n(a)
      })[0]
    }
  }

  return mrc[0]
}

const COLORS = {
  purple: '#a78bfa',
  cyan:   '#06b6d4',
  white:  '#e2e8f0',
  gold:   '#eab308',
  green:  '#10b981',
}

const VIEWS = ['3D', 'XY', 'XZ', 'YZ']
const AXIS  = { XY: 'z', XZ: 'y', YZ: 'x' }

export default function Volume3DViewer({ jobId, jobType, files }) {
  const theme        = useRef(null)   // avoid re-running NGL effect on theme toggle
  theme.current = useTheme()
  const T = useTheme()

  const containerRef = useRef(null)
  const stageRef     = useRef(null)
  const compRef      = useRef(null)

  // Live refs so view-switch effect reads current values without stale closure
  const contourRef   = useRef(0.5)
  const colorRef     = useRef('purple')
  const invertRef    = useRef(false)

  const [contour,      setContour]      = useState(0.5)
  const [color,        setColor]        = useState('purple')
  const [viewMode,     setViewMode]     = useState('3D')
  const [invert,       setInvert]       = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [mapInfo,      setMapInfo]      = useState(null)
  const [status,       setStatus]       = useState('idle')  // idle | loading | ready | error

  // Keep live refs in sync with state
  contourRef.current = contour
  colorRef.current   = color
  invertRef.current  = invert

  // Fixed wide range — contour is always an absolute density value
  const sliderMin  = 0.001
  const sliderMax  = 10.0
  const sliderStep = 0.001
  // σ label next to the value: how many RMS units the current contour represents
  const sigmaLabel = mapInfo && mapInfo.rms > 0
    ? ` (${(contour / mapInfo.rms).toFixed(1)}σ)`
    : ''

  // Pick best file when the job changes
  useEffect(() => {
    setSelectedFile(pickBestMap(files, jobType))
    setViewMode('3D')
  }, [files, jobType])

  // Fetch MRC header info and use it to set a data-driven initial contour
  useEffect(() => {
    if (!selectedFile || !jobId) { setMapInfo(null); return }
    fetchMapInfo(`${jobId}/${selectedFile}`).then(info => {
      setMapInfo(info)
      if (info?.rms > 0) {
        const initial = parseFloat((info.rms * 2).toPrecision(3))
        setContour(initial)
        contourRef.current = initial
      }
    }).catch(() => setMapInfo(null))
  }, [selectedFile, jobId])

  // Mount NGL stage — only re-runs when the file or theme background changes
  useEffect(() => {
    if (!containerRef.current || !selectedFile || !jobId) return

    setStatus('loading')

    const stage = new NGL.Stage(containerRef.current, { backgroundColor: T.bg })
    stageRef.current = stage

    const ro = new ResizeObserver(() => stage.handleResize())
    ro.observe(containerRef.current)

    const url = fileUrl(`${jobId}/${selectedFile}`)
    stage.loadFile(url, { ext: 'mrc' })
      .then(comp => {
        compRef.current = comp
        comp.addRepresentation('surface', {
          contour:     true,
          isolevel:    invertRef.current ? -contourRef.current : contourRef.current,
          colorScheme: 'uniform',
          color:       COLORS[colorRef.current],
          opacity:     1.0,
          opaqueBack:  false,
        })
        comp.autoView()
        setStatus('ready')
      })
      .catch(err => {
        console.error('NGL load error', err)
        setStatus('error')
      })

    return () => {
      ro.disconnect()
      stage.dispose()
      stageRef.current = null
      compRef.current  = null
    }
  }, [selectedFile, jobId, T.bg])

  // Contour + invert: update without remounting
  useEffect(() => {
    if (viewMode !== '3D' || !compRef.current?.reprList[0]) return
    compRef.current.reprList[0].setParameters({
      isolevel: invert ? -contour : contour,
    })
  }, [contour, invert, viewMode])

  // Color: update without remounting
  useEffect(() => {
    if (!compRef.current?.reprList[0]) return
    compRef.current.reprList[0].setParameters({ color: COLORS[color] })
  }, [color])

  // View mode: swap representation type
  useEffect(() => {
    const comp  = compRef.current
    const stage = stageRef.current
    if (!comp || !stage) return

    comp.removeAllRepresentations()

    if (viewMode === '3D') {
      comp.addRepresentation('surface', {
        contour:     true,
        isolevel:    invertRef.current ? -contourRef.current : contourRef.current,
        colorScheme: 'uniform',
        color:       COLORS[colorRef.current],
        opacity:     1.0,
      })
    } else {
      comp.addRepresentation('slice', {
        axis:        AXIS[viewMode],
        colorScheme: 'density',
      })
    }
    comp.autoView()
  }, [viewMode])

  // ── UI helpers ───────────────────────────────────────────────────────────
  const mrcFiles = files?.filter(f => f.endsWith('.mrc')) ?? []

  if (!mrcFiles.length) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: T.textMuted, fontSize: 13 }}>
        No MRC files found for this job.
      </div>
    )
  }

  const btnStyle = (active) => ({
    fontSize: 11, padding: '2px 8px', cursor: 'pointer',
    background: active ? T.accent + '33' : T.surface2,
    border: `1px solid ${active ? T.accent : T.border}`,
    borderRadius: 4,
    color: active ? T.accent : T.textMuted,
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: T.bg }}>

      {/* ── Controls bar ── */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10,
        padding: '7px 14px', borderBottom: `1px solid ${T.border}`,
        background: T.surface, flexShrink: 0,
      }}>

        {/* File selector */}
        <select
          value={selectedFile ?? ''}
          onChange={e => setSelectedFile(e.target.value)}
          style={{ fontSize: 11, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 4, color: T.text, padding: '3px 6px', maxWidth: 220 }}
        >
          {mrcFiles.map(f => <option key={f} value={f}>{f}</option>)}
        </select>

        {/* Contour slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: T.textMuted }}>σ</span>
          <input
            type="range" min={sliderMin} max={sliderMax} step={sliderStep}
            value={Math.min(contour, sliderMax)}
            onChange={e => setContour(parseFloat(e.target.value))}
            style={{ width: 88 }}
          />
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text, minWidth: 64 }}>
            {contour.toPrecision(3)}{sigmaLabel}
          </span>
        </div>

        {/* Color swatches */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {Object.entries(COLORS).map(([name, hex]) => (
            <div
              key={name}
              title={name}
              onClick={() => setColor(name)}
              style={{
                width: 16, height: 16, borderRadius: '50%', background: hex, cursor: 'pointer',
                boxShadow: color === name ? `0 0 0 2px ${T.bg}, 0 0 0 4px ${hex}` : 'none',
              }}
            />
          ))}
        </div>

        {/* View mode */}
        <div style={{ display: 'flex', gap: 3 }}>
          {VIEWS.map(v => (
            <button key={v} onClick={() => setViewMode(v)} style={btnStyle(viewMode === v)}>{v}</button>
          ))}
        </div>

        {/* Invert */}
        <button onClick={() => setInvert(v => !v)} style={btnStyle(invert)}>invert</button>

        {/* Map info */}
        {mapInfo && (
          <span style={{ fontSize: 10, color: T.textMuted, marginLeft: 'auto', fontFamily: 'monospace' }}>
            {mapInfo.nx}×{mapInfo.ny}×{mapInfo.nz} · {mapInfo.voxel_size?.toFixed(3)} Å/px
          </span>
        )}
      </div>

      {/* ── NGL viewport ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {status !== 'ready' && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
            justifyContent: 'center', zIndex: 10, background: T.bg,
            color: status === 'error' ? '#ef4444' : T.textMuted, fontSize: 13,
          }}>
            {status === 'loading' ? 'Loading map…' : status === 'error' ? 'Failed to load MRC file.' : ''}
          </div>
        )}
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  )
}
