import React from 'react'
import { useTheme, TYPE_COLOR } from '../theme.js'
import { fileUrl } from '../api/http.js'

// File extensions that are likely result outputs vs job metadata
const RESULT_EXTS = new Set(['.mrc', '.mrcs', '.star', '.pdf', '.eps', '.dat', '.xml', '.bild', '.txt'])
const META_FILES  = new Set(['job.star', 'job_pipeline.star', 'default_pipeline.star', 'continue_job.star', 'run.job', 'run.out', 'run.err', 'note.txt', 'PIPELINER_JOB_EXIT_SUCCESS', 'RELION_JOB_EXIT_SUCCESS'])

function ext(filename) { return filename.slice(filename.lastIndexOf('.')).toLowerCase() }

function FileRow({ jobId, filename, theme }) {
  const isMrc = ext(filename) === '.mrc' || ext(filename) === '.mrcs'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: `1px solid ${theme.border}` }}>
      <span style={{ fontSize: 11, fontFamily: 'monospace', color: theme.text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {filename}
      </span>
      <a
        href={fileUrl(`${jobId}/${filename}`)}
        download={filename}
        style={{ fontSize: 10, color: theme.accent, textDecoration: 'none', flexShrink: 0 }}
      >
        ↓
      </a>
    </div>
  )
}

function FileList({ jobId, files, theme }) {
  const results = files.filter(f => RESULT_EXTS.has(ext(f)) && !META_FILES.has(f))
  if (!results.length) return <p style={{ color: theme.textMuted, fontSize: 12 }}>No result files found.</p>
  return (
    <div>
      {results.map(f => <FileRow key={f} jobId={jobId} filename={f} theme={theme} />)}
    </div>
  )
}

function MrcGrid({ jobId, files, theme }) {
  // Show .mrc filenames that look like class maps (run_it*_class*.mrc)
  const classMaps = files.filter(f => /run_it\d+_class\d+\.mrc$/.test(f))
  const latest = [...new Set(classMaps.map(f => f.replace(/run_it\d+_/, 'run_it???_')))]
  // Find the highest iteration for each class
  const byClass = {}
  classMaps.forEach(f => {
    const m = f.match(/run_it(\d+)_(class\d+\.mrc)$/)
    if (!m) return
    const [, iter, cls] = m
    if (!byClass[cls] || parseInt(iter) > parseInt(byClass[cls].iter)) {
      byClass[cls] = { iter, file: f }
    }
  })
  const finalMaps = Object.values(byClass).map(v => v.file)
  if (!finalMaps.length) return <FileList jobId={jobId} files={files} theme={theme} />

  return (
    <div>
      <p style={{ fontSize: 11, color: theme.textMuted, marginBottom: 8 }}>
        {finalMaps.length} class map{finalMaps.length > 1 ? 's' : ''} (latest iteration)
      </p>
      {finalMaps.map(f => (
        <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: `1px solid ${theme.border}` }}>
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: TYPE_COLOR['Class3D'], flex: 1 }}>{f}</span>
          <a href={fileUrl(`${jobId}/${f}`)} download={f} style={{ fontSize: 10, color: theme.accent, textDecoration: 'none' }}>↓</a>
        </div>
      ))}
      <div style={{ marginTop: 12 }}>
        <p style={{ fontSize: 11, color: theme.textMuted }}>All output files:</p>
        <FileList jobId={jobId} files={files} theme={theme} />
      </div>
    </div>
  )
}

function PostProcessResults({ jobId, files, theme }) {
  const fscFile = files.find(f => f === 'postprocess_fsc.dat')
  return (
    <div>
      {fscFile && (
        <div style={{ marginBottom: 12 }}>
          <p style={{ fontSize: 11, color: theme.textMuted, marginBottom: 4 }}>FSC data available</p>
          <a href={fileUrl(`${jobId}/${fscFile}`)} download={fscFile}
            style={{ fontSize: 11, color: theme.accent }}>↓ {fscFile}</a>
        </div>
      )}
      <FileList jobId={jobId} files={files} theme={theme} />
    </div>
  )
}

export default function ResultsViewer({ job, files }) {
  const theme = useTheme()

  if (!job) return null
  if (!files) return <p style={{ padding: 16, color: theme.textMuted, fontSize: 12 }}>Loading…</p>

  const type = job.type

  return (
    <div style={{ padding: '12px 16px', overflowY: 'auto', height: '100%' }}>
      {(type === 'Class3D' || type === 'Class2D') && <MrcGrid jobId={job.id} files={files} theme={theme} />}
      {(type === 'PostProcess') && <PostProcessResults jobId={job.id} files={files} theme={theme} />}
      {!['Class3D', 'Class2D', 'PostProcess'].includes(type) && <FileList jobId={job.id} files={files} theme={theme} />}
    </div>
  )
}
