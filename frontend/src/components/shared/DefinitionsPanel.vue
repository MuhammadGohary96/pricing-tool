<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <button
      class="w-full px-4 py-2.5 flex items-center justify-between hover:bg-grey-50 transition-colors"
      @click="toggle"
    >
      <span class="inline-flex items-center gap-2 text-sm font-semibold text-grey-700">
        <BookOpen class="w-4 h-4 text-brand-primary" />
        Definitions &amp; Guide
      </span>
      <ChevronDown
        class="w-4 h-4 text-grey-400 transition-transform duration-200"
        :class="expanded ? 'rotate-180' : ''"
      />
    </button>

    <div
      ref="contentRef"
      class="overflow-hidden transition-all duration-300 ease-in-out"
      :style="{ maxHeight: expanded ? contentHeight + 'px' : '0px' }"
    >
      <div ref="innerRef" class="px-4 pb-4 pt-1 border-t border-grey-100">
        <div
          v-for="(section, si) in sections"
          :key="si"
          :class="si > 0 ? 'mt-4' : ''"
        >
          <h4 class="text-sm font-bold text-brand-primary uppercase tracking-wide mb-2">{{ section.title }}</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-x-6 gap-y-2.5">
            <div v-for="(item, ii) in section.items" :key="ii" class="flex items-start gap-2">
              <component
                v-if="item.icon"
                :is="item.icon"
                class="w-4 h-4 text-brand-primary shrink-0 mt-1"
              />
              <div>
                <span class="text-sm font-semibold text-grey-900">{{ item.term }}</span>
                <span class="text-sm text-grey-500 ml-1">{{ item.description }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { BookOpen, ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  sections: { type: Array, default: () => [] },
  storageKey: { type: String, default: 'definitions-panel' },
})

const expanded = ref(false)
const contentHeight = ref(0)
const innerRef = ref(null)

function toggle() {
  expanded.value = !expanded.value
  try {
    localStorage.setItem(props.storageKey, expanded.value ? '1' : '0')
  } catch { /* ignore */ }
}

function measureHeight() {
  if (innerRef.value) {
    contentHeight.value = innerRef.value.scrollHeight
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(props.storageKey)
    if (saved === '1') expanded.value = true
  } catch { /* ignore */ }
  nextTick(measureHeight)
})

watch(() => props.sections, () => nextTick(measureHeight), { deep: true })
</script>
