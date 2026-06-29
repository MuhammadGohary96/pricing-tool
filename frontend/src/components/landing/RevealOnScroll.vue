<template>
  <!-- Content is visible by default; the reveal only ENHANCES on scroll-in, so a
       headless render or a never-fired observer still ships the content (never
       blank). Under prefers-reduced-motion the global block neutralises the
       animation, leaving an instant appearance. -->
  <component
    :is="tag"
    ref="target"
    :class="{ 'animate-fade-in-up': isVisible }"
    :style="isVisible && delay ? { animationDelay: delay } : null"
  >
    <slot />
  </component>
</template>

<script setup>
import { useScrollReveal } from '../../composables/useScrollReveal'

defineProps({
  tag: { type: String, default: 'div' },
  delay: { type: String, default: '' },
})
const { target, isVisible } = useScrollReveal()
</script>
