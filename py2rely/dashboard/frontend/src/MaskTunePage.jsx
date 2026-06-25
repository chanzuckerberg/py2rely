import React, { useState, useEffect, useCallback, useRef } from 'react'
import { ThemeContext, themes, useTheme } from './theme.js'
import { fetchMaps, generateMask, saveMask, filterMap } from './api/http.js'
import MaskTuneViewer from './components/MaskTuneViewer.jsx'

// Parameter definitions mirror the RELION MaskCreate job options.
const PARAM_DEFS = [
  { key: 'lowpass',       label: 'Lowpass filter (Å)',     step: 1,    min: -1,  help: 'Lowpass applied before binarization. -1 disables.' },
  { key: 'angpix',        label: 'Pixel size (Å)',         step: 0.1,  min: -1,  help: 'Pixel size for the lowpass filter. -1 uses the map header value.' },
  { key: 'ini_threshold', label: 'Binarization threshold', step: 0.01, min: 0,   help: 'Density threshold for the initial binary mask.' },
  { key: 'extend_inimask',label: 'Extend mask (px)',       step: 1,    min: -50, help: 'Grow (>0) or shrink (<0) the binary mask by this many pixels.' },
  { key: 'width_soft_edge',label: 'Soft edge width (px)',  step: 1,    min: 0,   help: 'Width of the raised-cosine soft edge.' },
]

const DEFAULTS = {
  lowpass: 15,
  angpix: -1,
  ini_threshold: 0.02,
  extend_inimask: 3,
  width_soft_edge: 3,
  invert: false,
}

// Collapsible grouped map picker — groups by job_id, expands on click.
function MapGroupSelect({ maps, value, onChange }) {
  const T = useTheme()
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState({})
  const ref = useRef(null)

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const groups = Object.entries(
    maps.reduce((acc, m) => {
      (acc[m.job_id] = acc[m.job_id] || { job_type: m.job_type, items: [] }).items.push(m)
      return acc
    }, {})
  )

  const selectedMap = maps.find(m => m.path === value)
  const label = selectedMap ? selectedMap.file : '— select a pipeline map —'

  const toggleGroup = (job_id) =>
    setExpanded(prev => ({ ...prev, [job_id]: !prev[job_id] }))

  const select = (path) => { onChange(path); setOpen(false) }

  return (
    <div ref={ref} style={{ position: 'relative', marginBottom: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', textAlign: 'left', fontSize: 12,
          background: T.surface2, border: `1px solid ${T.border}`,
          borderRadius: 4, color: value ? T.text : T.textMuted,
          padding: '5px 28px 5px 8px', cursor: 'pointer', boxSizing: 'border-box',
          position: 'relative',
        }}
      >
        {label}
        <span style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', fontSize: 10, color: T.textMuted }}>▼</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 4,
          maxHeight: 320, overflowY: 'auto', boxShadow: '0 6px 20px rgba(0,0,0,0.35)',
        }}>
          <div
            onClick={() => select('')}
            style={{ padding: '6px 10px', fontSize: 12, cursor: 'pointer', color: T.textMuted,
              background: !value ? T.accent + '33' : 'transparent' }}
            onMouseEnter={e => e.currentTarget.style.background = T.border}
            onMouseLeave={e => e.currentTarget.style.background = !value ? T.accent + '33' : 'transparent'}
          >
            — select a pipeline map —
          </div>

          {groups.map(([job_id, { job_type, items }]) => (
            <div key={job_id}>
              <div
                onClick={() => toggleGroup(job_id)}
                style={{
                  padding: '6px 10px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  color: T.text, borderTop: `1px solid ${T.border}`,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
                onMouseEnter={e => e.currentTarget.style.background = T.border}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <span style={{ fontSize: 9, color: T.textMuted }}>{expanded[job_id] ? '▼' : '▶'}</span>
                {job_type}: {job_id}
              </div>

              {expanded[job_id] && items.map(m => (
                <div
                  key={m.path}
                  onClick={() => select(m.path)}
                  style={{
                    padding: '5px 10px 5px 26px', fontSize: 12, cursor: 'pointer',
                    color: T.text, fontFamily: 'monospace',
                    background: value === m.path ? T.accent + '33' : 'transparent',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = T.border}
                  onMouseLeave={e => e.currentTarget.style.background = value === m.path ? T.accent + '33' : 'transparent'}
                >
                  {m.file}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// A small "?" badge that reveals a help popup while the cursor hovers over it.
function HelpTip({ text }) {
  const T = useTheme()
  const [open, setOpen] = useState(false)
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', flexShrink: 0 }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <span style={{
        width: 14, height: 14, borderRadius: '50%', border: `1px solid ${T.border2}`,
        color: T.textMuted, fontSize: 10, lineHeight: '13px', textAlign: 'center',
        cursor: 'help', display: 'inline-block', userSelect: 'none', fontWeight: 700,
      }}>?</span>
      {open && (
        <span style={{
          position: 'absolute', top: '130%', left: 0, zIndex: 50, width: 220,
          background: T.surface2, color: T.text, border: `1px solid ${T.border2}`,
          borderRadius: 6, padding: '8px 10px', fontSize: 11, lineHeight: 1.45,
          fontWeight: 400, whiteSpace: 'normal', boxShadow: '0 6px 20px rgba(0,0,0,0.45)',
        }}>{text}</span>
      )}
    </span>
  )
}

function Header({ themeName, onToggleTheme }) {
  const T = useTheme()
  return (
    <div style={{
      height: 48, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16,
      background: T.surface, borderBottom: `1px solid ${T.border}`, flexShrink: 0,
    }}>
      <span style={{ fontWeight: 700, letterSpacing: '0.05em', color: T.accent, fontSize: 14 }}>
        py2rely · Mask Create
      </span>
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <a href="#/" style={{ fontSize: 12, color: T.textMuted, textDecoration: 'none' }}>← Dashboard</a>
        <button onClick={onToggleTheme} style={{
          background: 'none', border: `1px solid ${T.border}`, borderRadius: 6,
          color: T.text, cursor: 'pointer', padding: '3px 8px', fontSize: 14, lineHeight: 1.4,
        }}>{themeName === 'dark' ? '☀' : '☽'}</button>
      </div>
    </div>
  )
}

function ParamPanel({
  maps, inputPath, setInputPath, customPath, setCustomPath,
  params, setParam, onGenerate, generating, error,
  result, savePath, setSavePath, onSave, saveMsg,
  onPreviewFiltered, filtering, filterErr, filtered, showFiltered, setShowFiltered,
}) {
  const T = useTheme()

  const fieldStyle = {
    fontSize: 12, background: T.surface2, border: `1px solid ${T.border}`,
    borderRadius: 4, color: T.text, padding: '5px 8px', width: '100%', boxSizing: 'border-box',
  }
  const sectionTitle = {
    fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
    color: T.textMuted, margin: '0 0 8px',
  }

  return (
    <div style={{
      width: 340, flexShrink: 0, overflowY: 'auto', padding: 16,
      borderRight: `1px solid ${T.border}`, background: T.surface, display: 'flex', flexDirection: 'column', gap: 20,
    }}>
      {/* Input map */}
      <div>
        <p style={sectionTitle}>Input map</p>
        <MapGroupSelect
          maps={maps}
          value={maps.some(m => m.path === inputPath) ? inputPath : ''}
          onChange={v => { setInputPath(v); setCustomPath('') }}
        />
        <input
          type="text" placeholder="…or paste a project-relative .mrc path"
          value={customPath}
          onChange={e => setCustomPath(e.target.value)}
          onBlur={e => { if (e.target.value.trim()) setInputPath(e.target.value.trim()) }}
          onKeyDown={e => { if (e.key === 'Enter' && e.target.value.trim()) setInputPath(e.target.value.trim()) }}
          style={fieldStyle}
        />
        {inputPath && (
          <p style={{ fontSize: 11, fontFamily: 'monospace', color: T.textMuted, margin: '6px 0 0', wordBreak: 'break-all' }}>
            {inputPath}
          </p>
        )}
      </div>

      {/* Parameters */}
      <div>
        <p style={sectionTitle}>MaskCreate parameters</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {PARAM_DEFS.map(p => (
            <React.Fragment key={p.key}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: T.text }}>
                  {p.label}
                  <HelpTip text={p.help} />
                </span>
                <input
                  type="number" step={p.step}
                  value={params[p.key]}
                  onChange={e => setParam(p.key, e.target.value === '' ? '' : parseFloat(e.target.value))}
                  style={fieldStyle}
                />
              </label>

              {/* Lowpass visualization preview sits directly under the lowpass field */}
              {p.key === 'lowpass' && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      onClick={onPreviewFiltered}
                      disabled={filtering || !inputPath}
                      style={{
                        flex: 1, fontSize: 12, padding: '7px 12px', borderRadius: 6,
                        cursor: (filtering || !inputPath) ? 'default' : 'pointer',
                        background: T.surface2, color: T.text, border: `1px solid ${T.border2}`,
                      }}
                    >
                      {filtering ? 'Filtering…' : 'Preview lowpass-filtered map'}
                    </button>
                    <HelpTip text="Low-pass filter the input map at the value above and show it in the viewer. RELION applies the binarization threshold to this filtered map, so the viewer's contour slider (in raw density units) reads the exact --ini_threshold value — use “→ threshold” there to copy it." />
                  </div>
                  {filtered && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: T.text, cursor: 'pointer', marginTop: 8 }}>
                      <input type="checkbox" checked={showFiltered} onChange={e => setShowFiltered(e.target.checked)} />
                      Show filtered map in viewer
                    </label>
                  )}
                  {filterErr && (
                    <p style={{ fontSize: 11, color: '#ef4444', fontFamily: 'monospace', margin: '8px 0 0' }}>{filterErr}</p>
                  )}
                </div>
              )}
            </React.Fragment>
          ))}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: T.text, cursor: 'pointer' }}>
            <input type="checkbox" checked={params.invert} onChange={e => setParam('invert', e.target.checked)} />
            Invert final mask
            <HelpTip text="Invert the final mask (1 − mask): the masked-in and masked-out regions are swapped." />
          </label>
        </div>
      </div>

      <button
        onClick={onGenerate}
        disabled={generating || !inputPath}
        style={{
          fontSize: 13, fontWeight: 600, padding: '9px 12px', borderRadius: 6, cursor: (generating || !inputPath) ? 'default' : 'pointer',
          background: (generating || !inputPath) ? T.surface2 : T.accent,
          color: (generating || !inputPath) ? T.textMuted : '#0b0b14',
          border: `1px solid ${(generating || !inputPath) ? T.border : T.accent}`,
        }}
      >
        {generating ? 'Generating…' : 'Generate Mask'}
      </button>

      {error && (
        <p style={{ fontSize: 12, color: '#ef4444', fontFamily: 'monospace', margin: 0 }}>{error}</p>
      )}

      {/* Result + save */}
      {result && (
        <div>
          <p style={sectionTitle}>Result</p>
          <div style={{ fontSize: 11, fontFamily: 'monospace', color: T.textMuted, lineHeight: 1.6, marginBottom: 12 }}>
            <div>{result.nx}×{result.ny}×{result.nz} · {result.angpix.toFixed(3)} Å/px</div>
            <div>occupancy: {(result.fraction * 100).toFixed(1)}% of box</div>
          </div>

          <label style={{ fontSize: 12, color: T.text, display: 'block', marginBottom: 4 }}>Save mask to:</label>
          <input
            type="text" value={savePath} onChange={e => setSavePath(e.target.value)}
            style={{ ...fieldStyle, marginBottom: 8 }}
          />
          <button
            onClick={onSave}
            style={{
              fontSize: 12, fontWeight: 600, padding: '7px 12px', borderRadius: 6, cursor: 'pointer', width: '100%',
              background: T.surface2, color: T.text, border: `1px solid ${T.border2}`,
            }}
          >Save mask.mrc</button>
          {saveMsg && (
            <p style={{ fontSize: 11, color: saveMsg.ok ? '#10b981' : '#ef4444', fontFamily: 'monospace', margin: '8px 0 0', wordBreak: 'break-all' }}>
              {saveMsg.text}
            </p>
          )}

          <details style={{ marginTop: 14 }}>
            <summary style={{ fontSize: 11, color: T.textMuted, cursor: 'pointer' }}>equivalent RELION command</summary>
            <code style={{
              display: 'block', fontSize: 10.5, color: T.text, background: T.surface2, border: `1px solid ${T.border}`,
              borderRadius: 4, padding: 8, marginTop: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            }}>{result.command}</code>
          </details>
        </div>
      )}
    </div>
  )
}

export default function MaskTunePage() {
  const [themeName, setThemeName] = useState(() => localStorage.getItem('theme') ?? 'dark')
  const theme = themes[themeName]

  const [maps,       setMaps]       = useState([])
  const [inputPath,  setInputPath]  = useState('')
  const [customPath, setCustomPath] = useState('')
  const [params,     setParams]     = useState(DEFAULTS)
  const [generating, setGenerating] = useState(false)
  const [error,      setError]      = useState(null)
  const [result,     setResult]     = useState(null)
  const [savePath,   setSavePath]   = useState('mask.mrc')
  const [saveMsg,    setSaveMsg]    = useState(null)

  // Lowpass-filtered visualization of the input map
  const [filtered,     setFiltered]     = useState(null)   // { path, token }
  const [showFiltered, setShowFiltered] = useState(false)
  const [filtering,    setFiltering]    = useState(false)
  const [filterErr,    setFilterErr]    = useState(null)

  useEffect(() => {
    fetchMaps().then(setMaps).catch(() => setMaps([]))
    fetch('/api/mask/init')
      .then(r => r.json())
      .then(d => { if (d.input_path) setInputPath(d.input_path) })
      .catch(() => {})
  }, [])

  const setParam = useCallback((key, value) => {
    setParams(prev => ({ ...prev, [key]: value }))
  }, [])

  // Reset the filtered preview when the input map changes.
  useEffect(() => { setFiltered(null); setShowFiltered(false) }, [inputPath])

  const numParam = useCallback(
    (k) => (params[k] === '' || params[k] === undefined ? DEFAULTS[k] : Number(params[k])),
    [params],
  )

  const onPreviewFiltered = useCallback(async () => {
    if (!inputPath) return
    const lowpass = numParam('lowpass')
    if (!(lowpass > 0)) { setFilterErr('Set a lowpass value (Å) > 0 first.'); return }
    setFiltering(true)
    setFilterErr(null)
    try {
      const res = await filterMap({ input_path: inputPath, lowpass, angpix: numParam('angpix') })
      setFiltered({ path: res.path, token: res.token })
      setShowFiltered(true)
    } catch (e) {
      setFilterErr(e.message)
    } finally {
      setFiltering(false)
    }
  }, [inputPath, numParam])

  const onGenerate = useCallback(async () => {
    if (!inputPath) return
    setGenerating(true)
    setError(null)
    setSaveMsg(null)
    try {
      const res = await generateMask({
        input_path: inputPath,
        lowpass: numParam('lowpass'),
        angpix: numParam('angpix'),
        ini_threshold: numParam('ini_threshold'),
        extend_inimask: numParam('extend_inimask'),
        width_soft_edge: numParam('width_soft_edge'),
        invert: !!params.invert,
      })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }, [inputPath, params, numParam])

  const onUseAsThreshold = useCallback((value) => {
    setParam('ini_threshold', value)
  }, [setParam])

  const onSave = useCallback(async () => {
    try {
      const res = await saveMask(savePath)
      setSaveMsg({ ok: true, text: `Saved → ${res.saved_path}` })
    } catch (e) {
      setSaveMsg({ ok: false, text: e.message })
    }
  }, [savePath])

  const toggleTheme = () => {
    const next = themeName === 'dark' ? 'light' : 'dark'
    setThemeName(next)
    localStorage.setItem('theme', next)
  }

  return (
    <ThemeContext.Provider value={theme}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: theme.bg, color: theme.text }}>
        <Header themeName={themeName} onToggleTheme={toggleTheme} />
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <ParamPanel
            maps={maps}
            inputPath={inputPath} setInputPath={setInputPath}
            customPath={customPath} setCustomPath={setCustomPath}
            params={params} setParam={setParam}
            onGenerate={onGenerate} generating={generating} error={error}
            result={result}
            savePath={savePath} setSavePath={setSavePath} onSave={onSave} saveMsg={saveMsg}
            onPreviewFiltered={onPreviewFiltered} filtering={filtering} filterErr={filterErr}
            filtered={filtered} showFiltered={showFiltered} setShowFiltered={setShowFiltered}
          />
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <MaskTuneViewer
              basePath={showFiltered && filtered ? filtered.path : inputPath}
              baseToken={showFiltered && filtered ? filtered.token : 0}
              baseLabel={showFiltered && filtered ? 'filtered' : 'map'}
              maskPath={result?.mask_path}
              maskToken={result?.token}
              onUseAsThreshold={onUseAsThreshold}
            />
          </div>
        </div>
      </div>
    </ThemeContext.Provider>
  )
}
