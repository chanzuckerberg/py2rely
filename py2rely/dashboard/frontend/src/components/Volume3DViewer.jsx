import React, { useRef, useEffect, useState } from 'react'
import * as NGL from 'ngl'
import { useTheme } from '../theme.js'
import { fileUrl, fetchMapInfo } from '../api/http.js'

// Pick the most informative MRC file for a given job type
export function pickBestMap(files, jobType) {
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

// Draw a bounding box as 12 cylinder edges using NGL.Shape.
// Corners are placed at the volume's actual world coordinates (origin to origin+extent).
export function addBoundingBox(stage, mapInfo) {
  if (!stage || !mapInfo) return null
  const { nx, ny, nz, voxel_size, originX = 0, originY = 0, originZ = 0 } = mapInfo
  const lx = nx * voxel_size
  const ly = ny * voxel_size
  const lz = nz * voxel_size
  const ox = originX, oy = originY, oz = originZ
  const corners = [
    [ox,    oy,    oz   ], [ox+lx, oy,    oz   ],
    [ox+lx, oy+ly, oz   ], [ox,    oy+ly, oz   ],
    [ox,    oy,    oz+lz], [ox+lx, oy,    oz+lz],
    [ox+lx, oy+ly, oz+lz], [ox,    oy+ly, oz+lz],
  ]
  const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]]
  const shape = new NGL.Shape('bbox')
  edges.forEach(([a, b]) => shape.addCylinder(corners[a], corners[b], [1, 1, 1], 0.5))
  const comp = stage.addComponentFromObject(shape)
  comp.addRepresentation('buffer')
  return comp
}

export default function Volume3DViewer({ jobId, jobType, files, overlayPath }) {
  const T = useTheme()

  const containerRef   = useRef(null)
  const stageRef       = useRef(null)
  const compRef        = useRef(null)
  const boxCompRef     = useRef(null)
  const overlayCompRef = useRef(null)

  // Live refs for NGL callbacks (avoid stale closures)
  const contourRef          = useRef(0.5)
  const colorRef            = useRef('purple')
  const invertRef           = useRef(false)
  const wireframeRef        = useRef(false)
  const opacityRef          = useRef(1.0)
  const overlayOpacityRef   = useRef(0.5)
  const overlayWireframeRef = useRef(false)
  const overlayContourRef   = useRef(0.5)

  const [contour,          setContour]          = useState(0.5)
  const [color,            setColor]            = useState('purple')
  const [invert,           setInvert]           = useState(false)
  const [wireframe,        setWireframe]        = useState(false)
  const [opacity,          setOpacity]          = useState(1.0)
  const [showBox,          setShowBox]          = useState(true)
  const [overlayOpacity,   setOverlayOpacity]   = useState(0.5)
  const [overlayWireframe, setOverlayWireframe] = useState(false)
  const [overlayContour,   setOverlayContour]   = useState(0.5)
  const [selectedFile,     setSelectedFile]     = useState(null)
  const [mapInfo,          setMapInfo]          = useState(null)
  const [status,           setStatus]           = useState('idle')

  // Keep live refs in sync
  contourRef.current          = contour
  colorRef.current            = color
  invertRef.current           = invert
  wireframeRef.current        = wireframe
  opacityRef.current          = opacity
  overlayOpacityRef.current   = overlayOpacity
  overlayWireframeRef.current = overlayWireframe
  overlayContourRef.current   = overlayContour

  const sliderMin  = 0.001
  const sliderMax  = 10.0
  const sliderStep = 0.001
  const sigmaLabel = mapInfo && mapInfo.rms > 0
    ? ` (${(contour / mapInfo.rms).toFixed(1)}σ)`
    : ''

  // Pick best file when job changes; reset view controls
  useEffect(() => {
    setSelectedFile(pickBestMap(files, jobType))
    setShowBox(true)
    setWireframe(false)
    setOpacity(1.0)
  }, [files, jobType])

  // Fetch primary map header and set data-driven initial contour
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

  // ── Stage lifecycle: created once, destroyed only on unmount or theme change ──
  // Keeping the stage alive across file switches avoids stacking orphaned WebGL
  // canvases (NGL.dispose() does NOT remove its canvas from the DOM).
  useEffect(() => {
    if (!containerRef.current) return

    const stage = new NGL.Stage(containerRef.current, { backgroundColor: T.bg })
    stageRef.current = stage

    const ro = new ResizeObserver(() => stage.handleResize())
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      stage.dispose()
      stageRef.current       = null
      compRef.current        = null
      boxCompRef.current     = null
      overlayCompRef.current = null
    }
  }, [T.bg]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── File loading: reuses the existing stage, no stage recreaton ───────────
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !selectedFile || !jobId) return

    let cancelled = false

    // Clear previous components without destroying the stage or its canvas
    stage.removeAllComponents()
    compRef.current        = null
    boxCompRef.current     = null
    overlayCompRef.current = null
    setStatus('loading')

    stage.loadFile(fileUrl(`${jobId}/${selectedFile}`), { ext: 'mrc' })
      .then(comp => {
        if (cancelled) return
        compRef.current = comp
        comp.addRepresentation('surface', {
          isolevel:    invertRef.current ? -contourRef.current : contourRef.current,
          colorScheme: 'uniform',
          color:       COLORS[colorRef.current],
          opacity:     opacityRef.current,
          wireframe:   wireframeRef.current,
          opaqueBack:  false,
        })
        comp.autoView()

        // Load overlay if provided (e.g. input map for MaskCreate)
        if (overlayPath) {
          stage.loadFile(fileUrl(overlayPath), { ext: 'mrc' })
            .then(oComp => {
              if (cancelled) return
              overlayCompRef.current = oComp
              fetchMapInfo(overlayPath).then(info => {
                if (cancelled) return
                const iso = info?.rms > 0 ? parseFloat((info.rms * 2).toPrecision(3)) : 0.5
                overlayContourRef.current = iso
                setOverlayContour(iso)
                oComp.addRepresentation('surface', {
                  isolevel:    iso,
                  colorScheme: 'uniform',
                  color:       COLORS['gold'],
                  opacity:     overlayOpacityRef.current,
                  wireframe:   overlayWireframeRef.current,
                  opaqueBack:  false,
                })
              }).catch(() => {
                if (cancelled) return
                oComp.addRepresentation('surface', {
                  isolevel: 0.5,
                  colorScheme: 'uniform', color: COLORS['gold'],
                  opacity: overlayOpacityRef.current,
                  wireframe: overlayWireframeRef.current,
                  opaqueBack: false,
                })
              })
            })
            .catch(err => { if (!cancelled) console.warn('NGL overlay load error', err) })
        }

        setStatus('ready')
      })
      .catch(err => {
        if (cancelled) return
        console.error('NGL load error', err)
        setStatus('error')
      })

    return () => { cancelled = true }
  }, [selectedFile, jobId, T.bg]) // eslint-disable-line react-hooks/exhaustive-deps

  // Contour + invert + wireframe + opacity → update surface without remount
  useEffect(() => {
    if (!compRef.current?.reprList[0]) return
    compRef.current.reprList[0].setParameters({
      isolevel:  invert ? -contour : contour,
      wireframe,
      opacity,
    })
  }, [contour, invert, wireframe, opacity])

  // Color
  useEffect(() => {
    if (!compRef.current?.reprList[0]) return
    compRef.current.reprList[0].setParameters({ color: COLORS[color] })
  }, [color])

  // Bounding box toggle — status in deps ensures it fires once stage is ready
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

  // Overlay opacity + wireframe
  useEffect(() => {
    if (!overlayCompRef.current?.reprList[0]) return
    overlayCompRef.current.reprList[0].setParameters({
      opacity:   overlayOpacity,
      wireframe: overlayWireframe,
    })
  }, [overlayOpacity, overlayWireframe])

  // Overlay contour
  useEffect(() => {
    if (!overlayCompRef.current?.reprList[0]) return
    overlayCompRef.current.reprList[0].setParameters({ isolevel: overlayContour })
  }, [overlayContour])

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

        {/* Surface controls */}
        <button onClick={() => setInvert(v => !v)} style={btnStyle(invert)}>invert</button>
        <button onClick={() => setWireframe(v => !v)} style={btnStyle(wireframe)}>
          {wireframe ? 'wire' : 'solid'}
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: T.textMuted }}>α</span>
          <input
            type="range" min={0} max={1} step={0.05}
            value={opacity}
            onChange={e => setOpacity(parseFloat(e.target.value))}
            style={{ width: 60 }}
          />
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

      {/* ── Overlay controls (MaskCreate dual-volume) ── */}
      {overlayPath && (() => {
        const oSliderMax  = 10.0
        const oSliderStep = 0.001
        const overlayFileName = overlayPath.split('/').pop()
        return (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '5px 14px', borderBottom: `1px solid ${T.border}`,
            background: T.surface, flexShrink: 0, flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 11, color: T.textMuted, fontWeight: 600 }}>Overlay:</span>
            <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text }}>{overlayFileName}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontSize: 11, color: T.textMuted }}>σ</span>
              <input
                type="range" min={0.001} max={oSliderMax} step={oSliderStep}
                value={Math.min(overlayContour, oSliderMax)}
                onChange={e => setOverlayContour(parseFloat(e.target.value))}
                style={{ width: 88 }}
              />
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text, minWidth: 48 }}>
                {overlayContour.toPrecision(3)}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontSize: 11, color: T.textMuted }}>α</span>
              <input
                type="range" min={0} max={1} step={0.05}
                value={overlayOpacity}
                onChange={e => setOverlayOpacity(parseFloat(e.target.value))}
                style={{ width: 70 }}
              />
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: T.text }}>
                {overlayOpacity.toFixed(2)}
              </span>
            </div>
            <button onClick={() => setOverlayWireframe(v => !v)} style={btnStyle(overlayWireframe)}>
              {overlayWireframe ? 'wire' : 'solid'}
            </button>
          </div>
        )
      })()}

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
