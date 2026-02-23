import { createContext, useContext } from 'react'

export const themes = {
  dark: {
    bg:         '#07070f',
    surface:    '#0a0a0f',
    surface2:   '#0e0e1a',
    border:     '#1e1e2e',
    border2:    '#2d2d4e',
    text:       '#e2e8f0',
    textMuted:  '#64748b',
    accent:     '#a78bfa',
  },
  light: {
    bg:         '#f8f8fc',
    surface:    '#ffffff',
    surface2:   '#f1f1f8',
    border:     '#e2e2f0',
    border2:    '#c8c8e0',
    text:       '#1e1e2e',
    textMuted:  '#6b7280',
    accent:     '#7c3aed',
  },
}

export const TYPE_COLOR = {
  Import:      '#6366f1',
  MotionCorr:  '#8b5cf6',
  CtfFind:     '#a78bfa',
  ManualPick:  '#0ea5e9',
  AutoPick:    '#38bdf8',
  Extract:     '#06b6d4',
  Class2D:     '#f97316',
  Select:      '#fb923c',
  Class3D:     '#ef4444',
  Refine3D:    '#dc2626',
  PostProcess: '#10b981',
  CtfRefine:   '#84cc16',
  Polish:      '#eab308',
  LocalRes:    '#14b8a6',
  MaskCreate:  '#64748b',
  Reconstruct: '#8b5cf6',
}

export const STATUS_COLOR = {
  running:  '#f59e0b',
  finished: '#10b981',
  failed:   '#ef4444',
  aborted:  '#f97316',
  queued:   '#475569',
}

export const ThemeContext = createContext(themes.dark)
export const useTheme = () => useContext(ThemeContext)
