import React, { useRef, useEffect, useState } from 'react'
import * as NGL from 'ngl'
import { useTheme } from '../theme.js'
import { fileUrl, fetchMapInfo } from '../api/http.js'
import { addBoundingBox } from './Volume3DViewer.jsx'

const INPUT_COLOR = '#eab308'   // gold — the reference density map
const MASK_COLOR  = '#a78bfa'   // purple — the generated mask

// Cache-bust a project path so NGL/browser re-fetch a regenerated preview file.
const bust = (path, token) => (token ? `${path}?v=${token}` : path)

/**
 * Renders a reference density map (`basePath` — either the raw input map or a
 * low-pass-filtered preview) with the generated mask overlaid on top.
 *
 * Both surfaces use `isolevelType: 'value'`, so the contour slider reads in raw
 * density units — exactly the value RELION's `--ini_threshold` accepts. The
 * "use as threshold" button feeds the current contour back to the parameter
 * panel.
 */
export default function MaskTuneViewer({
  basePath, baseToken = 0, baseLabel, maskPath, maskToken, onUseAsThreshold,
}) {
  const T = useTheme()

  const containerRef = useRef(null)
  const stageRef     = useRef(null)
  const inputCompRef = useRef(null)
  const maskCompRef  = useRef(null)
  const boxCompRef   = useRef(null)

  const [inputInfo,     setInputInfo]     = useState(null)
  const [inputContour,  setInputContour]  = useState(0)
  const [inputOpacity,  setInputOpacity]  = useState(0.85)
  const [inputWire,     setInputWire]     = useState(false)
  const [maskContour,   setMaskContour]   = useState(0.5)
  const [maskOpacity,   setMaskOpacity]   = useState(0.4)
  const [maskWire,      setMaskWire]      = useState(true)
  const [showBox,       setShowBox]       = useState(true)
  const [status,        setStatus]        = useState('idle')

  // Live refs for async load callbacks (avoid stale closures)
  const inputContourRef = useRef(inputContour); inputContourRef.current = inputContour
  const inputOpacityRef = useRef(inputOpacity); inputOpacityRef.current = inputOpacity
  const inputWireRef    = useRef(inputWire);    inputWireRef.current    = inputWire
  const maskContourRef  = useRef(maskContour);  maskContourRef.current  = maskContour
  const maskOpacityRef  = useRef(maskOpacity);  maskOpacityRef.current  = maskOpacity
  const maskWireRef     = useRef(maskWire);     maskWireRef.current     = maskWire

  const rms = inputInfo?.rms ?? 0
  const mean = inputInfo?.dmean ?? 0
  const sigmaLabel = rms > 0 ? ` (${((inputContour - mean) / rms).toFixed(1)}σ)` : ''
  // Slider range from the map's real density span (fallback to a sane window).
  const sMin = inputInfo ? inputInfo.dmin : 0
  const sMax = inputInfo ? inputInfo.dmax : 1
  const sStep = sMax > sMin ? (sMax - sMin) / 1000 : 0.0001

  // ── Stage lifecycle: created once, destroyed only on unmount ────────────────
  // The background colour is updated in-place on theme change (see below) so we
  // never dispose/recreate the stage — that would drop the loaded volumes and
  // leave stale component refs behind.
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
      inputCompRef.current = null
      maskCompRef.current  = null
      boxCompRef.current   = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Update background colour in place when the theme changes.
  useEffect(() => {
    stageRef.current?.setParameters({ backgroundColor: T.bg })
  }, [T.bg])

  // ── Base map: load when path/token changes; data-driven initial contour ─────
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !basePath) return
    let cancelled = false

    if (inputCompRef.current) { stage.removeComponent(inputCompRef.current); inputCompRef.current = null }
    setStatus('loading')

    fetchMapInfo(bust(basePath, baseToken)).then(info => {
      if (cancelled) return
      setInputInfo(info)
      // Default contour ~2σ above the mean — a visible surface in raw units.
      const iso = info?.rms > 0
        ? parseFloat(((info.dmean ?? 0) + 2 * info.rms).toPrecision(4))
        : 0.5
      inputContourRef.current = iso
      setInputContour(iso)

      stage.loadFile(fileUrl(bust(basePath, baseToken)), { ext: 'mrc', name: `base-${baseToken}` })
        .then(comp => {
          if (cancelled) return
          inputCompRef.current = comp
          comp.addRepresentation('surface', {
            isolevelType: 'value', isolevel: iso, colorScheme: 'uniform', color: INPUT_COLOR,
            opacity: inputOpacityRef.current, wireframe: inputWireRef.current, opaqueBack: false,
          })
          comp.autoView()
          setStatus('ready')
        })
        .catch(err => { if (!cancelled) { console.error('NGL base load error', err); setStatus('error') } })
    })

    return () => { cancelled = true }
  }, [basePath, baseToken]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Mask: (re)load whenever a new mask is generated ─────────────────────────
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !maskPath || !maskToken) return
    let cancelled = false

    if (maskCompRef.current) { stage.removeComponent(maskCompRef.current); maskCompRef.current = null }

    stage.loadFile(fileUrl(bust(maskPath, maskToken)), { ext: 'mrc', name: `mask-${maskToken}` })
      .then(comp => {
        if (cancelled) return
        maskCompRef.current = comp
        comp.addRepresentation('surface', {
          isolevelType: 'value', isolevel: maskContourRef.current, colorScheme: 'uniform', color: MASK_COLOR,
          opacity: maskOpacityRef.current, wireframe: maskWireRef.current, opaqueBack: false,
        })
      })
      .catch(err => { if (!cancelled) console.error('NGL mask load error', err) })

    return () => { cancelled = true }
  }, [maskPath, maskToken]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Live parameter updates (no remount) ─────────────────────────────────────
  useEffect(() => {
    inputCompRef.current?.reprList[0]?.setParameters({
      isolevel: inputContour, opacity: inputOpacity, wireframe: inputWire,
    })
  }, [inputContour, inputOpacity, inputWire])

  useEffect(() => {
    maskCompRef.current?.reprList[0]?.setParameters({
      isolevel: maskContour, opacity: maskOpacity, wireframe: maskWire,
    })
  }, [maskContour, maskOpacity, maskWire])

  // ── Bounding box ────────────────────────────────────────────────────────────
  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    if (boxCompRef.current) { stage.removeComponent(boxCompRef.current); boxCompRef.current = null }
    if (showBox && inputInfo) boxCompRef.current = addBoundingBox(stage, inputInfo)
  }, [showBox, inputInfo, status])

  const btn = (active) => ({
    fontSize: 11, padding: '2px 8px', cursor: 'pointer',
    background: active ? T.accent + '33' : T.surface2,
    border: `1px solid ${active ? T.accent : T.border}`,
    borderRadius: 4, color: active ? T.accent : T.textMuted,
  })
  const row = { display: 'flex', alignItems: 'center', gap: 6 }
  const lbl = { fontSize: 11, color: T.textMuted, minWidth: 44 }
  const val = { fontSize: 11, fontFamily: 'monospace', color: T.text }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: T.bg }}>
      {/* Controls */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 16,
        padding: '8px 14px', borderBottom: `1px solid ${T.border}`, background: T.surface, flexShrink: 0,
      }}>
        {/* Base map (input / filtered) controls */}
        <div style={{ ...row, gap: 8 }}>
          <span style={{ ...lbl, color: INPUT_COLOR, fontWeight: 600 }}>{baseLabel ?? 'map'}</span>
          <div style={row} title="Raw density value — this is the --ini_threshold value RELION accepts">
            <span style={{ fontSize: 11, color: T.textMuted }}>thr</span>
            <input type="range" min={sMin} max={sMax} step={sStep}
              value={Math.min(Math.max(inputContour, sMin), sMax)}
              onChange={e => setInputContour(parseFloat(e.target.value))} style={{ width: 96 }} />
            <span style={{ ...val, minWidth: 110 }}>{inputContour.toPrecision(4)}{sigmaLabel}</span>
          </div>
          <button
            onClick={() => onUseAsThreshold?.(parseFloat(inputContour.toPrecision(4)))}
            style={btn(false)}
            title="Copy this contour value into the binarization threshold parameter"
          >→ threshold</button>
          <div style={row}>
            <span style={{ fontSize: 11, color: T.textMuted }}>α</span>
            <input type="range" min={0} max={1} step={0.05}
              value={inputOpacity} onChange={e => setInputOpacity(parseFloat(e.target.value))} style={{ width: 56 }} />
          </div>
          <button onClick={() => setInputWire(v => !v)} style={btn(inputWire)}>{inputWire ? 'wire' : 'solid'}</button>
        </div>

        {/* Mask controls */}
        <div style={{ ...row, gap: 8 }}>
          <span style={{ ...lbl, color: MASK_COLOR, fontWeight: 600 }}>mask</span>
          <div style={row}>
            <span style={{ fontSize: 11, color: T.textMuted }}>iso</span>
            <input type="range" min={0.01} max={1} step={0.01}
              value={maskContour} onChange={e => setMaskContour(parseFloat(e.target.value))} style={{ width: 80 }} />
            <span style={{ ...val, minWidth: 32 }}>{maskContour.toFixed(2)}</span>
          </div>
          <div style={row}>
            <span style={{ fontSize: 11, color: T.textMuted }}>α</span>
            <input type="range" min={0} max={1} step={0.05}
              value={maskOpacity} onChange={e => setMaskOpacity(parseFloat(e.target.value))} style={{ width: 56 }} />
          </div>
          <button onClick={() => setMaskWire(v => !v)} style={btn(maskWire)}>{maskWire ? 'wire' : 'solid'}</button>
        </div>

        <button onClick={() => setShowBox(v => !v)} style={btn(showBox)}>box</button>
        <button
          onClick={() => {
            if (!stageRef.current) return
            stageRef.current.makeImage({ factor: 2, antialias: true, transparent: false }).then(blob => {
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url; a.download = 'mask-preview.png'; a.click()
              URL.revokeObjectURL(url)
            })
          }}
          style={btn(false)} disabled={status !== 'ready'}
        >save png</button>

        {inputInfo && (
          <span style={{ fontSize: 10, color: T.textMuted, marginLeft: 'auto', fontFamily: 'monospace' }}>
            {inputInfo.nx}×{inputInfo.ny}×{inputInfo.nz} · {inputInfo.voxel_size?.toFixed(3)} Å/px
          </span>
        )}
      </div>

      {/* Viewport */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {status !== 'ready' && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 10, background: T.bg, color: status === 'error' ? '#ef4444' : T.textMuted, fontSize: 13,
          }}>
            {status === 'loading' ? 'Loading map…' : status === 'error' ? 'Failed to load input map.'
              : 'Select an input map to begin.'}
          </div>
        )}
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  )
}
