import React, { useRef, useEffect, useState } from 'react'
import * as NGL from 'ngl'
import { useTheme } from '../theme.js'
import { fileUrl, fetchMapInfo } from '../api/http.js'
import { pickBestMap, addBoundingBox } from './Volume3DViewer.jsx'

// NGL slice uses `dimension` (not `axis`) and `position` as 1–100 percent
const DIMS = [
  { key: 'z', label: 'XY' },
  { key: 'y', label: 'XZ' },
  { key: 'x', label: 'YZ' },
]

// Convert our 0–1 UI fraction to NGL's 1–100 percent range
const toNglPos = (frac) => Math.max(1, Math.min(100, Math.round(frac * 100)))

export default function Slice2DViewer({ jobId, jobType, files }) {
  const T = useTheme()

  const containerRef = useRef(null)
  const stageRef     = useRef(null)
  const compRef      = useRef(null)
  const boxCompRef   = useRef(null)
  const prevDimRef   = useRef(null)   // track axis changes for autoView

  // Live refs so async callbacks see current values
  const dimRef    = useRef('z')
  const posRef    = useRef(0.5)
  const minValRef = useRef(null)
  const maxValRef = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [mapInfo,      setMapInfo]      = useState(null)
  const [dim,          setDim]          = useState('z')
  const [pos,          setPos]          = useState(0.5)       // 0–1 fraction
  const [minVal,       setMinVal]       = useState(null)
  const [maxVal,       setMaxVal]       = useState(null)
  const [showBox,      setShowBox]      = useState(true)      // on by default
  const [status,       setStatus]       = useState('idle')

  dimRef.current    = dim
  posRef.current    = pos
  minValRef.current = minVal
  maxValRef.current = maxVal

  // Pick best file on job change, reset controls
  useEffect(() => {
    setSelectedFile(pickBestMap(files, jobType))
    setDim('z')
    setPos(0.5)
    setMinVal(null)
    setMaxVal(null)
    setShowBox(true)
    prevDimRef.current = null
  }, [files, jobType])

  // Fetch map info; set initial Min/Max from header dmin/dmax
  useEffect(() => {
    if (!selectedFile || !jobId) { setMapInfo(null); return }
    fetchMapInfo(`${jobId}/${selectedFile}`).then(info => {
      setMapInfo(info)
      if (info) {
        const newMin = parseFloat((info.dmin).toPrecision(3))
        const newMax = parseFloat((info.dmax).toPrecision(3))
        setMinVal(newMin)
        setMaxVal(newMax)
        minValRef.current = newMin
        maxValRef.current = newMax
      }
    }).catch(() => setMapInfo(null))
  }, [selectedFile, jobId])

  // ── Stage lifecycle: created once, destroyed only on unmount or theme change ──
  useEffect(() => {
    if (!containerRef.current) return

    const stage = new NGL.Stage(containerRef.current, { backgroundColor: T.bg })
    stageRef.current = stage

    const ro = new ResizeObserver(() => stage.handleResize())
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      stage.dispose()
      stageRef.current   = null
      compRef.current    = null
      boxCompRef.current = null
    }
  }, [T.bg]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── File loading: reuses the existing stage ───────────────────────────────
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !selectedFile || !jobId) return

    let cancelled = false

    stage.removeAllComponents()
    compRef.current    = null
    boxCompRef.current = null
    setStatus('loading')

    stage.loadFile(fileUrl(`${jobId}/${selectedFile}`), { ext: 'mrc' })
      .then(comp => {
        if (cancelled) return
        compRef.current = comp
        prevDimRef.current = dimRef.current
        comp.addRepresentation('slice', {
          dimension:   dimRef.current,
          colorScheme: 'density',
          position:    toNglPos(posRef.current),
          ...(minValRef.current !== null && maxValRef.current !== null
            ? { colorDomain: [minValRef.current, maxValRef.current] }
            : {}),
        })
        comp.autoView()
        setStatus('ready')
      })
      .catch(() => { if (!cancelled) setStatus('error') })

    return () => { cancelled = true }
  }, [selectedFile, jobId, T.bg]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Rebuild when dimension or colorDomain changes ────────────────────────
  // Position is handled live via setParameters (see below).
  useEffect(() => {
    const comp = compRef.current
    if (!comp) return
    const dimChanged = dim !== prevDimRef.current
    prevDimRef.current = dim

    comp.removeAllRepresentations()
    comp.addRepresentation('slice', {
      dimension:   dim,
      colorScheme: 'density',
      position:    toNglPos(posRef.current),
      ...(minVal !== null && maxVal !== null
        ? { colorDomain: [minVal, maxVal] }
        : {}),
    })
    if (dimChanged) comp.autoView()
  }, [dim, minVal, maxVal]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Slice position: live update via setParameters ────────────────────────
  // NGL position is 1–100 (percent of voxels); position has rebuild:true so
  // setParameters triggers an internal geometry rebuild efficiently.
  useEffect(() => {
    if (!compRef.current?.reprList[0]) return
    compRef.current.reprList[0].setParameters({ position: toNglPos(pos) })
  }, [pos])

  // ── Bounding box ─────────────────────────────────────────────────────────
  // Depends on status so it fires once the stage is ready (needed for default-on).
  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    if (showBox) {
      if (boxCompRef.current) stage.removeComponent(boxCompRef.current)
      boxCompRef.current = addBoundingBox(stage, mapInfo)
    } else {
      if (boxCompRef.current) {
        stage.removeComponent(boxCompRef.current)
        boxCompRef.current = null
      }
    }
  }, [showBox, mapInfo, status])

  // ── UI ───────────────────────────────────────────────────────────────────
  const mrcFiles = files?.filter(f => f.endsWith('.mrc')) ?? []
  if (!mrcFiles.length) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: T.textMuted, fontSize: 13 }}>
        No MRC files found for this job.
      </div>
    )
  }

  const rms = mapInfo?.rms ?? 1.0
  const sliderMin  = parseFloat((-rms * 3).toPrecision(2))
  const sliderMax  = parseFloat((rms * 12).toPrecision(2))
  const sliderStep = parseFloat((rms * 0.05).toPrecision(2)) || 0.001

  const btnStyle = (active) => ({
    fontSize: 11, padding: '2px 8px', cursor: 'pointer',
    background: active ? T.accent + '33' : T.surface2,
    border: `1px solid ${active ? T.accent : T.border}`,
    borderRadius: 4,
    color: active ? T.accent : T.textMuted,
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: T.bg }}>

      {/* ── Controls ── */}
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

        {/* Axis / dimension buttons */}
        <div style={{ display: 'flex', gap: 3 }}>
          {DIMS.map(({ key, label }) => (
            <button key={key} onClick={() => setDim(key)} style={btnStyle(dim === key)}>
              {label}
            </button>
          ))}
        </div>

        {/* Slice position — stored as 0–1 fraction, displayed as 1–100% */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: T.textMuted }}>Slice</span>
          <input
            type="range" min={0} max={1} step={0.01}
            value={pos}
            onChange={e => setPos(parseFloat(e.target.value))}
            style={{ width: 100 }}
          />
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text, minWidth: 36 }}>
            {toNglPos(pos)}%
          </span>
        </div>

        {/* Min density (black point) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: T.textMuted }}>Min</span>
          <input
            type="range" min={sliderMin} max={sliderMax} step={sliderStep}
            value={minVal !== null ? Math.min(Math.max(minVal, sliderMin), sliderMax) : sliderMin}
            onChange={e => setMinVal(parseFloat(e.target.value))}
            style={{ width: 80 }}
          />
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text, minWidth: 54 }}>
            {minVal !== null ? Number(minVal).toPrecision(3) : '—'}
          </span>
        </div>

        {/* Max density (white point) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: T.textMuted }}>Max</span>
          <input
            type="range" min={sliderMin} max={sliderMax} step={sliderStep}
            value={maxVal !== null ? Math.min(Math.max(maxVal, sliderMin), sliderMax) : sliderMax}
            onChange={e => setMaxVal(parseFloat(e.target.value))}
            style={{ width: 80 }}
          />
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text, minWidth: 54 }}>
            {maxVal !== null ? Number(maxVal).toPrecision(3) : '—'}
          </span>
        </div>

        {/* Bounding box toggle */}
        <button onClick={() => setShowBox(v => !v)} style={btnStyle(showBox)}>box</button>

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
