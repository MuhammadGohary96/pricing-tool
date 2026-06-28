<template>
  <component
    :is="as"
    :type="as === 'button' ? type : undefined"
    :disabled="as === 'button' ? (disabled || loading) : undefined"
    class="group inline-flex items-center justify-center font-semibold rounded-full transition-[transform,background-color,border-color,color] duration-200 ease-premium select-none disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary"
    :class="[sizeClasses, variantClasses]"
  >
    <!-- Leading icon (or loading spinner) -->
    <Loader2 v-if="loading" class="animate-spin shrink-0" :class="iconSize" />
    <component v-else-if="icon" :is="icon" class="shrink-0" :class="iconSize" />

    <span><slot /></span>

    <!-- Trailing "pip" — icon nested in its own circle, the landing-page CTA move -->
    <span
      v-if="pip"
      class="grid place-items-center rounded-full shrink-0 transition-transform duration-200 ease-premium group-hover:translate-x-0.5 group-hover:-translate-y-px"
      :class="[pipSize, pipBg]"
    >
      <component :is="trailingIcon" :class="pipIconSize" />
    </span>
  </component>
</template>

<script setup>
import { computed } from 'vue'
import { Loader2, ArrowRight } from 'lucide-vue-next'

const props = defineProps({
  // brand = magenta fill · solid = ink fill · ghost = bordered white · subtle = grey fill
  variant: { type: String, default: 'brand' },
  size: { type: String, default: 'md' }, // sm | md
  icon: { type: [Object, Function], default: null },        // leading icon
  pip: { type: Boolean, default: false },                   // trailing icon-in-circle
  trailingIcon: { type: [Object, Function], default: () => ArrowRight },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  as: { type: String, default: 'button' },                  // button | a | router-link
  type: { type: String, default: 'button' },
})

const sizeClasses = computed(() => {
  const base = props.size === 'sm' ? 'text-caption gap-1.5' : 'text-body gap-2'
  // tighter right padding when a pip is present so the circle sits flush
  if (props.size === 'sm') return `${base} ${props.pip ? 'pl-3.5 pr-1.5 py-1.5' : 'px-3.5 py-1.5'}`
  return `${base} ${props.pip ? 'pl-5 pr-1.5 py-2.5' : 'px-5 py-2.5'}`
})

const variantClasses = computed(() => ({
  brand:  'bg-brand-primary text-white shadow-[0_1px_2px_rgba(77,0,58,0.4),inset_0_1px_0_rgba(255,255,255,0.16)] hover:bg-brand-dark active:scale-[0.975]',
  solid:  'bg-grey-900 text-white hover:bg-black active:scale-[0.975]',
  ghost:  'bg-white text-grey-900 ring-1 ring-grey-200 hover:ring-brand-primary active:scale-[0.975]',
  subtle: 'bg-grey-100 text-grey-700 hover:bg-grey-200 active:scale-[0.975]',
}[props.variant] || ''))

const iconSize = computed(() => (props.size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'))
const pipSize = computed(() => (props.size === 'sm' ? 'w-6 h-6' : 'w-7 h-7'))
const pipIconSize = computed(() => (props.size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'))
const pipBg = computed(() =>
  props.variant === 'ghost' || props.variant === 'subtle'
    ? 'bg-brand-primary/10 text-brand-primary'
    : 'bg-white/18 text-current'
)
</script>
