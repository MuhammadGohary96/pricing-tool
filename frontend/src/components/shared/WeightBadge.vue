<template>
  <HelpTooltip :text="tip">
    <span
      tabindex="0"
      :aria-label="tip"
      class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full ring-1 ring-inset text-micro leading-none font-sans font-semibold whitespace-nowrap cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
      :class="flagged
        ? 'bg-amber-50 text-amber-800 ring-amber-300'
        : 'bg-brand-50 text-brand-primary ring-brand-light'"
    >
      <component :is="flagged ? TriangleAlert : Scale" class="w-3 h-3 shrink-0" aria-hidden="true" />
      <span v-if="label">{{ label }}</span>
    </span>
  </HelpTooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Scale, TriangleAlert } from 'lucide-vue-next'
import HelpTooltip from './HelpTooltip.vue'
import { formatSize } from '../../utils/size'

// Marks a PI that is not a plain per-pack comparison (Fruits & Vegetables only):
//   normalized — compared per kg; their price was scaled to our pack weight
//   mismatch   — sizes too far apart to trust (or piece counts differ): the PI is
//                left per pack and the pair is flagged for a mapping review
//   blend      — a blended PI that contains `count` normalized products
//   blend-mismatch — a roll-up containing `count` products flagged for review
const props = defineProps({
  status: { type: String, required: true },
  competitor: { type: String, default: '' },
  bfSize: { type: Number, default: null },
  bfUnit: { type: String, default: null },
  compSize: { type: Number, default: null },
  compUnit: { type: String, default: null },
  compPrice: { type: Number, default: null },
  ratio: { type: Number, default: null },
  pi: { type: Number, default: null },
  rawPi: { type: Number, default: null },
  count: { type: Number, default: 0 },
  of: { type: Number, default: 0 },
  compact: { type: Boolean, default: false },
})

const flagged = computed(() => props.status === 'mismatch' || props.status === 'blend-mismatch')

const label = computed(() => {
  if (props.status === 'blend' || props.status === 'blend-mismatch') return String(props.count)
  if (props.compact) return ''
  return props.status === 'mismatch' ? 'check size' : 'per kg'
})

const money = (v) => (v == null ? '—' : Number(v).toFixed(2))

const sizes = computed(() => {
  const ours = formatSize(props.bfSize, props.bfUnit)
  const theirs = formatSize(props.compSize, props.compUnit)
  if (!ours && !theirs) return ''
  const them = props.competitor || 'Competitor'
  const at = props.compPrice != null ? ` at ${money(props.compPrice)}` : ''
  return `Ours: ${ours || 'unknown'} · ${them}: ${theirs || 'unknown'}${at}`
})

const tip = computed(() => {
  if (props.status === 'blend-mismatch') {
    return `${props.count} product${props.count === 1 ? '' : 's'} here ${props.count === 1 ? 'is' : 'are'} flagged ` +
      'for a pack-size review: sizes too far apart (or different piece counts), so ' +
      (props.count === 1 ? 'its PI is' : 'their PIs are') + ' left per pack.'
  }
  if (props.status === 'blend') {
    return `${props.count} of ${props.of} products in this blend are weight-normalized: ` +
      'their competitor price is compared per kg, not per pack.'
  }
  if (props.status === 'mismatch') {
    const pieces = props.bfUnit === 'pcs' || props.compUnit === 'pcs'
    return [
      'Pack-size mismatch: flagged for review.',
      sizes.value,
      pieces
        ? 'Piece counts are never normalized (competitors often list one pack as "1 pcs"), so the PI is left per pack.'
        : 'Weights this far apart usually mean a wrong mapping or a wrong weight, so the PI is left per pack.',
    ].filter(Boolean).join('\n')
  }
  const scaled = props.compPrice != null && props.ratio != null ? props.compPrice * props.ratio : null
  return [
    'Weight-normalized PI: compared per kg, not per pack.',
    sizes.value,
    scaled != null ? `Their price for our pack: ${money(scaled)}` : '',
    props.pi != null
      ? `PI ${money(props.pi)}${props.rawPi != null ? ` · per pack it would read ${money(props.rawPi)}` : ''}`
      : '',
  ].filter(Boolean).join('\n')
})
</script>
