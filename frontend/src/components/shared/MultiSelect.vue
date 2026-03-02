<template>
  <div ref="wrapperRef" class="relative inline-block">
    <button
      type="button"
      class="text-body border rounded-lg px-3 py-1.5 text-grey-900 hover:border-brand-light focus:border-brand-primary focus:ring-1 focus:ring-brand-lightest outline-none transition-colors cursor-pointer flex items-center gap-1.5 min-w-[130px]"
      :class="modelValue.length ? 'border-brand-primary bg-brand-50 font-medium' : 'border-grey-200 bg-grey-50'"
      @click="toggle"
    >
      <span class="truncate">{{ displayLabel }}</span>
      <span v-if="modelValue.length" class="inline-flex items-center justify-center w-4.5 h-4.5 rounded-full bg-brand-primary text-white text-[10px] font-bold leading-none shrink-0">{{ modelValue.length }}</span>
      <ChevronDown class="w-3.5 h-3.5 text-grey-400 shrink-0 ml-auto transition-transform" :class="open ? 'rotate-180' : ''" />
    </button>

    <Transition name="dropdown">
      <div
        v-if="open"
        class="absolute top-full left-0 mt-1 bg-white rounded-lg shadow-lg border border-grey-200 z-50 min-w-[220px] max-w-[320px]"
      >
        <!-- Search input -->
        <div class="p-2 border-b border-grey-100">
          <div class="relative">
            <Search class="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-grey-400 pointer-events-none" />
            <input
              ref="searchRef"
              v-model="query"
              type="text"
              :placeholder="`Search ${label.toLowerCase()}...`"
              class="w-full pl-7 pr-3 py-1.5 text-body border border-grey-200 rounded-md bg-white focus:border-brand-primary focus:ring-1 focus:ring-brand-lightest outline-none transition-colors"
            />
          </div>
        </div>

        <!-- Select All / Clear -->
        <div class="border-b border-grey-100 flex items-center justify-between px-3 py-1.5">
          <label class="flex items-center gap-2 hover:bg-brand-50 cursor-pointer transition-colors">
            <input
              type="checkbox"
              :checked="allSelected"
              :indeterminate="someSelected && !allSelected"
              class="w-3.5 h-3.5 rounded border-grey-300 text-brand-primary focus:ring-brand-lightest accent-[var(--brand-primary)]"
              @change="toggleAll"
            />
            <span class="text-body text-grey-700 font-medium">Select All</span>
          </label>
          <div class="flex items-center gap-2">
            <span class="text-micro text-grey-400">{{ selectedCount }}/{{ filteredOptions.length }}</span>
            <button
              v-if="modelValue.length"
              class="text-micro text-grey-500 hover:text-brand-primary font-medium"
              @click="clearAll"
            >
              Clear
            </button>
          </div>
        </div>

        <!-- Options list -->
        <div class="max-h-[240px] overflow-auto py-1">
          <label
            v-for="opt in filteredOptions"
            :key="opt"
            class="flex items-center gap-2 px-3 py-1.5 hover:bg-brand-50 cursor-pointer transition-colors"
          >
            <input
              type="checkbox"
              :checked="modelValue.includes(opt)"
              class="w-3.5 h-3.5 rounded border-grey-300 text-brand-primary focus:ring-brand-lightest accent-[var(--brand-primary)]"
              @change="toggleOption(opt)"
            />
            <span class="text-body text-grey-900 truncate">{{ opt }}</span>
          </label>
          <div v-if="filteredOptions.length === 0" class="px-3 py-3 text-body text-grey-400 text-center">
            No matches
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { Search, ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  label: { type: String, default: 'Select' },
  placeholder: { type: String, default: null },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const query = ref('')
const wrapperRef = ref(null)
const searchRef = ref(null)

const displayLabel = computed(() => {
  if (props.modelValue.length === 0) return props.placeholder || `All ${props.label}`
  if (props.modelValue.length === 1) return props.modelValue[0]
  return `${props.modelValue.length} ${props.label}`
})

const filteredOptions = computed(() => {
  if (!query.value) return props.options
  const q = query.value.toLowerCase()
  return props.options.filter(opt => opt.toLowerCase().includes(q))
})

const selectedCount = computed(() => {
  return filteredOptions.value.filter(opt => props.modelValue.includes(opt)).length
})

const allSelected = computed(() => {
  return filteredOptions.value.length > 0 && filteredOptions.value.every(opt => props.modelValue.includes(opt))
})

const someSelected = computed(() => {
  return filteredOptions.value.some(opt => props.modelValue.includes(opt))
})

function toggle() {
  open.value = !open.value
  if (open.value) {
    query.value = ''
    nextTick(() => searchRef.value?.focus())
  }
}

function toggleOption(opt) {
  const current = [...props.modelValue]
  const idx = current.indexOf(opt)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(opt)
  }
  emit('update:modelValue', current)
}

function toggleAll() {
  if (allSelected.value) {
    // Remove all filtered options
    const filtered = new Set(filteredOptions.value)
    emit('update:modelValue', props.modelValue.filter(v => !filtered.has(v)))
  } else {
    // Add all filtered options that aren't already selected
    const current = new Set(props.modelValue)
    const toAdd = filteredOptions.value.filter(v => !current.has(v))
    emit('update:modelValue', [...props.modelValue, ...toAdd])
  }
}

function clearAll() {
  emit('update:modelValue', [])
}

function handleClickOutside(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', handleClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', handleClickOutside))
</script>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
