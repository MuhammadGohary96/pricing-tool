<template>
  <span
    ref="anchor"
    class="relative inline-flex items-center"
    @mouseenter="open"
    @mouseleave="close"
    @focusin="open"
    @focusout="close"
  >
    <button
      type="button"
      class="w-4 h-4 rounded-full bg-grey-100 text-grey-500 text-micro font-bold flex items-center justify-center hover:bg-brand-50 hover:text-brand-primary transition-colors focus:outline-none focus:ring-1 focus:ring-brand-primary"
      :aria-label="`Help: ${text}`"
    >?</button>

    <!-- Teleported to <body> on purpose. These question marks live inside table
         headers, and every table here sits in a wrapper with overflow-x: auto
         inside a panel with overflow-hidden. An absolutely-positioned bubble is
         CLIPPED by those ancestors no matter how high its z-index goes, because
         overflow clipping happens before stacking is considered — so the tooltip
         was being cut off by the panel edge rather than drawn behind it. Fixed
         positioning from the body escapes both. -->
    <Teleport to="body">
      <Transition name="tooltip">
        <div
          v-if="show"
          ref="bubble"
          role="tooltip"
          class="fixed z-[9999] bg-grey-900 text-white text-micro rounded-lg px-3 py-2 shadow-lg leading-relaxed pointer-events-none whitespace-pre-line"
          :style="style"
        >
          {{ text }}
          <div
            class="absolute border-4 border-transparent"
            :class="placement === 'top' ? 'top-full border-t-grey-900' : 'bottom-full border-b-grey-900'"
            :style="arrowStyle"
          ></div>
        </div>
      </Transition>
    </Teleport>
  </span>
</template>

<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'

defineProps({
  text: { type: String, required: true },
})

const show = ref(false)
const anchor = ref(null)
const bubble = ref(null)
const placement = ref('top')
// Starts off-screen: the bubble has to be in the DOM before its height can be
// measured, and an unplaced fixed element would otherwise flash at the top-left
// corner of the viewport for one frame.
const style = ref({ left: '-9999px', top: '0px' })
const arrowStyle = ref({ left: '50%' })

const GAP = 8      // space between the question mark and the bubble
const EDGE = 8     // keep this clear of the viewport edges

function place() {
  const el = anchor.value
  const box = bubble.value
  if (!el || !box) return

  const r = el.getBoundingClientRect()
  const width = Math.min(260, window.innerWidth - EDGE * 2)
  const height = box.offsetHeight

  // Clamp horizontally so a tooltip on the last column of a wide table does not
  // run off the right edge.
  const centre = r.left + r.width / 2
  const left = Math.min(Math.max(EDGE, centre - width / 2), window.innerWidth - width - EDGE)

  // Prefer above; flip below only when there is genuinely no room, which is the
  // case for the sticky table headers near the top of the viewport.
  const fitsAbove = r.top - GAP - height >= EDGE
  placement.value = fitsAbove ? 'top' : 'bottom'

  style.value = {
    left: `${left}px`,
    top: fitsAbove ? `${r.top - GAP - height}px` : `${r.bottom + GAP}px`,
    width: `${width}px`,
  }
  // The arrow tracks the question mark, not the bubble centre — they differ
  // whenever the clamp above has kicked in.
  arrowStyle.value = { left: `${Math.min(Math.max(centre - left, 12), width - 12)}px` }
}

function onViewportChange() {
  if (show.value) place()
}

async function open() {
  show.value = true
  await nextTick()
  place()
  // Fixed positioning does not follow the page, so track both scrolling (capture,
  // to catch the table's own horizontal scroller as well as the window) and resize.
  window.addEventListener('scroll', onViewportChange, true)
  window.addEventListener('resize', onViewportChange)
}

function close() {
  show.value = false
  style.value = { left: '-9999px', top: '0px' }
  window.removeEventListener('scroll', onViewportChange, true)
  window.removeEventListener('resize', onViewportChange)
}

onBeforeUnmount(close)
</script>

<style scoped>
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
/* No translateX here: the bubble is placed by explicit left, not centred by a
   transform, so translating it would offset it from the anchor. */
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: translateY(4px); }
</style>
