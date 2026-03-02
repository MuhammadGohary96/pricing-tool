/**
 * Single source of truth for PI color thresholds.
 * PI = Competitor price ÷ BF price.
 * HIGH PI (>1.05) = BF cheaper = GREEN
 * LOW PI (<0.95) = BF more expensive = RED
 */
export const PI_CHEAP = 0.95
export const PI_EXPENSIVE = 1.05

export function piZone(pi) {
  if (pi == null) return 'neutral'
  if (pi > PI_EXPENSIVE) return 'green'
  if (pi < PI_CHEAP) return 'red'
  return 'yellow'
}

export function piTextClass(pi) {
  switch (piZone(pi)) {
    case 'green': return 'text-green-600'
    case 'yellow': return 'text-amber-600'
    case 'red': return 'text-red-600'
    default: return 'text-grey-400'
  }
}

export function piBgClass(pi) {
  switch (piZone(pi)) {
    case 'green': return 'bg-green-50'
    case 'yellow': return 'bg-amber-50'
    case 'red': return 'bg-red-50'
    default: return 'bg-grey-50'
  }
}

export function piBarGradient(pi) {
  switch (piZone(pi)) {
    case 'green': return 'linear-gradient(90deg, #34D399, #059669)'
    case 'yellow': return 'linear-gradient(90deg, #FCD34D, #F59E0B)'
    case 'red': return 'linear-gradient(90deg, #FCA5A5, #EF4444)'
    default: return '#E5E7EB'
  }
}

/** Dot color for strip plot / scatter */
export function piDotColor(pi) {
  if (pi == null) return '#E5E7EB'
  if (pi < PI_CHEAP) return '#ef4444'
  if (pi <= PI_EXPENSIVE) return '#f59e0b'
  return '#22c55e'
}

/** For ECharts — treemap, bar chart, gauge */
export function piToHex(pi) {
  if (pi == null) return '#E5E7EB'
  if (pi >= 1.15) return '#059669'
  if (pi >= 1.10) return '#34D399'
  if (pi >= PI_EXPENSIVE) return '#BBF7D0'
  if (pi >= PI_CHEAP) return '#FEF9C3'
  if (pi >= 0.90) return '#FECACA'
  if (pi >= 0.85) return '#F87171'
  return '#DC2626'
}

/** Multi-zone gauge colors */
export const GAUGE_ZONES = [
  { min: 0.70, max: 0.85, color: '#991B1B', label: 'Very Expensive' },
  { min: 0.85, max: PI_CHEAP, color: '#DC2626', label: 'Expensive' },
  { min: PI_CHEAP, max: PI_EXPENSIVE, color: '#EAB308', label: 'Parity' },
  { min: PI_EXPENSIVE, max: 1.15, color: '#16A34A', label: 'Cheaper' },
  { min: 1.15, max: 1.30, color: '#166534', label: 'Much Cheaper' },
]
