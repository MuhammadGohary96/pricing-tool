// Pack sizes arrive from the model in canonical units: grams ('g') or pieces
// ('pcs'). Grams read as kg from 1000 g, the way produce is labelled.
function trim(n) {
  const digits = n < 10 ? 2 : n < 100 ? 1 : 0
  return String(Number(n.toFixed(digits)))
}

/** { num, unit } for display, e.g. { num: '1.79', unit: 'kg' }; null when unknown. */
export function sizeParts(value, unit) {
  if (value == null || !unit) return null
  if (unit === 'g') return value >= 1000 ? { num: trim(value / 1000), unit: 'kg' } : { num: trim(value), unit: 'g' }
  return { num: trim(value), unit }
}

export function formatSize(value, unit) {
  const p = sizeParts(value, unit)
  return p ? `${p.num} ${p.unit}` : ''
}
