/**
 * Single source of truth for the PI color system. "Both tails bad."
 *
 * PI = Breadfast price ÷ Competitor price.
 *   PI < 0.95   → too CHEAP   (cool / blue,  ▼) — margin left on the table
 *   PI 0.95–1.05 → PARITY     (green, ◆)        — the target, healthy
 *   PI > 1.05   → too PRICEY  (warm / red,   ▲) — demand risk
 *
 * Two channels: SEVERITY rides on tint depth (farther from parity = heavier),
 * DIRECTION rides on the cool/warm hue split AND a mandatory glyph, so meaning
 * survives tiny cells, screenshots, projectors, and red–green colorblindness.
 * Grey is reserved exclusively for "no data" — parity is green, never grey.
 */
export const PI_CHEAP = 0.95
export const PI_EXPENSIVE = 1.05

/**
 * Zone tokens. `fill` = light cell background (clears WCAG AA with `text`),
 * `bold` = saturated hex for charts/borders, `glyph` = directional indicator
 * (doubled on the deep tiers so severity survives in greyscale).
 */
export const PI_ZONES = {
  deepCheap:    { fill: '#BFDBFE', text: '#1E3A8A', bold: '#1D4ED8', glyph: '▼▼', label: 'Deep Cheap',      dir: 'cheaper' },
  cheap:        { fill: '#DBEAFE', text: '#1E40AF', bold: '#2563EB', glyph: '▼',  label: 'Cheap',           dir: 'cheaper' },
  slightCheap:  { fill: '#EFF6FF', text: '#1D4ED8', bold: '#3B82F6', glyph: '▼',  label: 'Slightly Cheap',  dir: 'cheaper' },
  parity:       { fill: '#DCFCE7', text: '#166534', bold: '#16A34A', glyph: '◆',  label: 'Parity',          dir: 'parity'  },
  slightPricey: { fill: '#FFFBEB', text: '#B45309', bold: '#F59E0B', glyph: '▲',  label: 'Slightly Pricey', dir: 'pricier' },
  pricey:       { fill: '#FFEDD5', text: '#9A3412', bold: '#EA580C', glyph: '▲',  label: 'Pricey',          dir: 'pricier' },
  deepPricey:   { fill: '#FECACA', text: '#7F1D1D', bold: '#DC2626', glyph: '▲▲', label: 'Deep Pricey',     dir: 'pricier' },
  none:         { fill: '#F3F4F6', text: '#9CA3AF', bold: '#E5E7EB', glyph: '',   label: 'No data',         dir: 'none'    },
}

/** Resolve a PI value to its zone key. */
export function piZoneKey(pi) {
  if (pi == null) return 'none'
  if (pi < 0.80) return 'deepCheap'
  if (pi < 0.90) return 'cheap'
  if (pi < PI_CHEAP) return 'slightCheap'
  if (pi <= PI_EXPENSIVE) return 'parity'
  if (pi <= 1.10) return 'slightPricey'
  if (pi <= 1.20) return 'pricey'
  return 'deepPricey'
}

/**
 * Full treatment bundle for any surface:
 * { fill, text, bold, glyph, label, dir, key, severity }
 * `severity` is 0 inside the parity band, ramping to 1 by ~±0.30 deviation.
 */
export function piTreatment(pi) {
  const key = piZoneKey(pi)
  const severity = pi == null
    ? 0
    : Math.min(1, Math.max(0, (Math.abs(pi - 1) - 0.05) / 0.25))
  return { ...PI_ZONES[key], key, severity }
}

/* ── Tailwind class adapters (literal strings so the JIT keeps them) ── */
const CLASS = {
  deepCheap:    { bg: 'bg-blue-200',  text: 'text-blue-900'   },
  cheap:        { bg: 'bg-blue-100',  text: 'text-blue-800'   },
  slightCheap:  { bg: 'bg-blue-50',   text: 'text-blue-700'   },
  parity:       { bg: 'bg-green-100', text: 'text-green-800'  },
  slightPricey: { bg: 'bg-amber-50',  text: 'text-amber-700'  },
  pricey:       { bg: 'bg-orange-100', text: 'text-orange-800' },
  deepPricey:   { bg: 'bg-red-100',   text: 'text-red-900'    },
  none:         { bg: 'bg-grey-50',   text: 'text-grey-400'   },
}

export function piBgClass(pi) {
  return CLASS[piZoneKey(pi)].bg
}

export function piTextClass(pi) {
  return CLASS[piZoneKey(pi)].text
}

/** Colorblind-safe directional glyph (▼ cheaper · ◆ parity · ▲ pricier; doubled when deep). */
export function piArrow(pi) {
  return piTreatment(pi).glyph
}

/**
 * Back-compat coarse zone. Maps the 7-zone model down to the legacy
 * 'green' | 'yellow' | 'red' | 'neutral' buckets that older call sites expect,
 * but RE-ORIENTED so high PI (pricey) is the alarming end, not green.
 *   parity → 'green', cheap side → 'cyan', pricey side → 'red', no data → 'neutral'
 */
export function piZone(pi) {
  const key = piZoneKey(pi)
  if (key === 'none') return 'neutral'
  if (key === 'parity') return 'green'
  if (PI_ZONES[key].dir === 'cheaper') return 'cyan'
  return 'red'
}

/** Inline-bar gradient — cool for cheaper, green for parity, warm for pricier. */
export function piBarGradient(pi) {
  switch (piZone(pi)) {
    case 'green': return 'linear-gradient(90deg, #34D399, #16A34A)'
    case 'cyan':  return 'linear-gradient(90deg, #60A5FA, #2563EB)'
    case 'red':   return 'linear-gradient(90deg, #FB923C, #DC2626)'
    default:      return '#E5E7EB'
  }
}

/* ── Continuous color for gradients (gauge arc, treemap, dots, sparklines) ──
 * Diverging blue → green → red, anchored green at parity (1.00). The warm tail
 * runs a touch hotter than the cool tail by design: over-pricing (demand loss)
 * is flagged more urgently than under-pricing (slow margin bleed). */
const STOPS = [
  [0.70, '#1E40AF'], [0.80, '#2563EB'], [0.90, '#60A5FA'], [0.95, '#4ADE80'],
  [1.00, '#16A34A'], [1.05, '#4ADE80'], [1.10, '#FBBF24'], [1.20, '#F97316'], [1.30, '#DC2626'],
]

function _hexToRgb(h) {
  return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]
}
function _rgbToHex(rgb) {
  return '#' + rgb.map(x => Math.round(x).toString(16).padStart(2, '0')).join('').toUpperCase()
}
function _mix(a, b, t) {
  const A = _hexToRgb(a), B = _hexToRgb(b)
  return _rgbToHex([0, 1, 2].map(i => A[i] + (B[i] - A[i]) * t))
}

/** Continuous PI → hex for ECharts (treemap, gauge, bar) and SVG charts. */
export function piToHex(pi) {
  if (pi == null) return '#E5E7EB'
  const v = Math.min(1.30, Math.max(0.70, pi))
  for (let i = 1; i < STOPS.length; i++) {
    if (v <= STOPS[i][0]) {
      const [a, ca] = STOPS[i - 1]
      const [b, cb] = STOPS[i]
      return _mix(ca, cb, (v - a) / (b - a))
    }
  }
  return STOPS[STOPS.length - 1][1]
}

/** Dot color for strip plot / scatter — continuous, re-oriented. */
export function piDotColor(pi) {
  return pi == null ? '#E5E7EB' : piToHex(pi)
}

/**
 * Multi-zone gauge bands, re-oriented to the real data (PI = BF ÷ Competitor):
 * low PI = cheaper (cool), center = parity (green), high PI = pricier (warm).
 */
export const GAUGE_ZONES = [
  { min: 0.70, max: 0.80,       color: '#1D4ED8', label: 'Deep Cheap' },
  { min: 0.80, max: 0.90,       color: '#2563EB', label: 'Cheap' },
  { min: 0.90, max: PI_CHEAP,   color: '#60A5FA', label: 'Slightly Cheap' },
  { min: PI_CHEAP, max: PI_EXPENSIVE, color: '#16A34A', label: 'Parity' },
  { min: PI_EXPENSIVE, max: 1.10, color: '#F59E0B', label: 'Slightly Pricey' },
  { min: 1.10, max: 1.20,       color: '#EA580C', label: 'Pricey' },
  { min: 1.20, max: 1.30,       color: '#DC2626', label: 'Deep Pricey' },
]
