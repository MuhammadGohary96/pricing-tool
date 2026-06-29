/**
 * Canvas charts (ECharts) don't honour the global `prefers-reduced-motion` CSS
 * block in breadfast.css, so chart options must gate animation in JS.
 * Usage in a chartOption: `animation: !prefersReducedMotion()`.
 */
export function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
