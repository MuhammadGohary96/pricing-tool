<template>
  <div class="relative" ref="wrapper">
    <button
      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-body font-medium transition-colors"
      :class="hasSelection
        ? 'border-brand-primary bg-brand-50 text-brand-primary'
        : 'border-grey-200 bg-white text-grey-700 hover:border-grey-300'"
      @click="open = !open"
    >
      <EyeIcon class="w-3.5 h-3.5" />
      Competitors
      <span
        class="text-micro px-1.5 py-px rounded-full font-bold"
        :class="hasSelection ? 'bg-brand-primary text-white' : 'bg-grey-100 text-grey-500'"
      >{{ hasSelection ? modelValue.length : 'All' }}</span>
      <ChevronDown class="w-3 h-3 transition-transform" :class="open ? 'rotate-180' : ''" />
    </button>

    <Transition name="dropdown">
      <div
        v-if="open"
        class="absolute z-30 mt-1 left-0 bg-white rounded-lg shadow-lg border border-grey-200 py-1 min-w-[200px]"
      >
        <button
          class="w-full text-left px-3 py-1.5 text-body text-brand-primary font-medium hover:bg-brand-50 transition-colors"
          @click="selectAll"
        >{{ hasSelection ? 'Show All' : 'Deselect All' }}</button>
        <div class="border-t border-grey-100 my-1"></div>
        <label
          v-for="comp in competitors"
          :key="comp"
          class="flex items-center gap-2 px-3 py-1 cursor-pointer hover:bg-grey-50 transition-colors"
        >
          <input
            type="checkbox"
            :checked="isSelected(comp)"
            class="w-3.5 h-3.5 rounded border-grey-300 accent-brand-primary cursor-pointer"
            @change="toggle(comp)"
          />
          <span class="text-body text-grey-700">{{ comp }}</span>
        </label>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Eye as EyeIcon, ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  competitors: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const wrapper = ref(null)
onClickOutside(wrapper, () => { open.value = false })

const hasSelection = computed(() => props.modelValue.length > 0 && props.modelValue.length < props.competitors.length)

function isSelected(comp) {
  return props.modelValue.length === 0 || props.modelValue.includes(comp)
}

function toggle(comp) {
  let current = props.modelValue.length === 0
    ? [...props.competitors]
    : [...props.modelValue]

  if (current.includes(comp)) {
    current = current.filter(c => c !== comp)
  } else {
    current.push(comp)
  }
  // If all selected or none, reset to empty (= show all)
  if (current.length === 0 || current.length === props.competitors.length) {
    emit('update:modelValue', [])
  } else {
    emit('update:modelValue', current)
  }
}

function selectAll() {
  emit('update:modelValue', [])
}
</script>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.dropdown-enter-from, .dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
