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
  // --- Classification (High Impact / Vibrant) ---
  Extract:     '#FF0602', // Electric Indigo
  Class2D:     '#004FE0', // Cyan
  Select:      '#4AC630', // Magenta
  Class3D:     '#E09401', // Neon Red (High Focus)
  PostProcess: '#E27E96', // Vivid Rose Red
  Refine3D:    '#C6FB01', // Pink
  CtfRefine:   '#A58A00', // Lavender
  
  // --- Final Steps (High Contrast / Deep) ---
  Polish:      '#02AC98', // Brown
  LocalRes:    '#FFFAC8', // Beige
  MaskCreate:  '#C800C1', // Navy (Deep contrast to reds/pinks)
  Reconstruct: '#9E3700', // Mint
}

// export const TYPE_COLOR = {
//   // --- Classification (High Impact / Vibrant) ---
//   Extract:     '#009d9a', // Electric Indigo
//   Class2D:     '#42D4F4', // Cyan
//   Select:      '#F032E6', // Magenta
//   Class3D:     '#ff832b', // Neon Red (High Focus)
//   PostProcess: '#9E6B1E', // Vivid Rose Red
//   Refine3D:    '#DE1D58', // Pink
//   CtfRefine:   '#EC00F9', // Lavender
  
//   // --- Final Steps (High Contrast / Deep) ---
//   Polish:      '#9A6324', // Brown
//   LocalRes:    '#FFFAC8', // Beige
//   MaskCreate:  '#1D8BDE', // Navy (Deep contrast to reds/pinks)
//   Reconstruct: '#1DDE5D', // Mint
// }
 
export const STATUS_COLOR = {
  running:  '#f59e0b',
  finished: '#10b981',
  failed:   '#ef4444',
  aborted:  '#f97316',
  queued:   '#475569',
}

export const ThemeContext = createContext(themes.dark)
export const useTheme = () => useContext(ThemeContext)
