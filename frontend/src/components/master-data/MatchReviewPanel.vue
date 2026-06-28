<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <span class="text-subheading font-bold text-grey-900 tracking-tightish">Match Review</span>
      <span class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">
        {{ total.toLocaleString() }} pending · Accept or Reject
      </span>
    </div>

    <div class="overflow-y-auto p-3 flex flex-col gap-2.5" style="max-height: 420px">
      <!-- Match Card -->
      <div
        v-for="(match, idx) in matches"
        :key="match.product_id"
        class="border border-grey-200 rounded-lg p-3.5 transition-all duration-150 hover:border-brand-light hover:shadow-panel-hover"
        :class="dismissed.has(match.product_id) ? 'opacity-40 pointer-events-none' : ''"
      >
        <!-- Card Header: index + similarity badge -->
        <div class="flex items-center justify-between mb-2.5">
          <span class="text-micro text-grey-400 font-medium">#{{ (page - 1) * pageSize + idx + 1 }}</span>
          <span
            class="text-micro font-bold px-2 py-0.5 rounded-md"
            :class="similarityClass(match.similarity_score)"
          >
            {{ (match.similarity_score * 100).toFixed(0) }}% match
          </span>
        </div>

        <!-- Product Pair -->
        <div class="flex items-center gap-2 mb-2.5">
          <div class="flex-1 bg-grey-50 rounded-md p-2.5 min-w-0">
            <div class="text-micro font-bold uppercase tracking-wide text-grey-400 mb-1">Breadfast</div>
            <div class="text-body font-medium text-grey-800 truncate" :title="match.bf_product_name">{{ match.bf_product_name }}</div>
            <div class="text-caption font-bold text-grey-700 mt-0.5">EGP {{ match.bf_price?.toFixed(1) }}</div>
          </div>
          <ArrowLeftRight class="w-4 h-4 text-grey-300 shrink-0" />
          <div class="flex-1 bg-grey-50 rounded-md p-2.5 min-w-0">
            <div class="text-micro font-bold uppercase tracking-wide text-grey-400 mb-1">{{ match.competitor_name || 'Competitor' }}</div>
            <div class="text-body font-medium text-grey-800 truncate" :title="match.suggested_competitor_name">{{ match.suggested_competitor_name }}</div>
            <div class="text-caption font-bold text-grey-700 mt-0.5">Est. EGP {{ match.estimated_competitor_price?.toFixed(1) }}</div>
          </div>
        </div>

        <!-- Score Bar -->
        <div class="h-2 bg-grey-100 rounded-full mb-2.5 overflow-hidden">
          <div
            class="h-full rounded-full bg-brand-primary"
            :style="{ width: (match.similarity_score * 100) + '%' }"
          />
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-2">
          <button
            class="flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-caption font-semibold bg-green-600 text-white hover:bg-green-700 transition-colors"
            @click="acceptMatch(match)"
          ><Check class="w-3.5 h-3.5" />Accept</button>
          <button
            class="flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-caption font-semibold bg-grey-100 text-grey-600 border border-grey-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
            @click="rejectMatch(match)"
          ><X class="w-3.5 h-3.5" />Reject</button>
        </div>
      </div>

      <EmptyState v-if="!matches.length" :icon="CheckCircleIcon" title="All caught up!" message="All matches reviewed. Check back after the next data sync." />
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="px-4 py-2.5 border-t border-grey-100 flex items-center justify-between bg-grey-50 gap-3">
      <span class="text-caption text-grey-500 shrink-0">
        {{ ((page - 1) * pageSize + 1) }}-{{ Math.min(page * pageSize, total) }} of {{ total }}
      </span>
      <div class="flex items-center gap-1.5">
        <button
          :disabled="page <= 1"
          class="w-7 h-7 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors flex items-center justify-center"
          aria-label="Previous page"
          @click="$emit('reviewPage', page - 1)"
        ><ArrowLeft class="w-3.5 h-3.5" /></button>
        <span class="text-caption text-grey-500 px-2">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          class="w-7 h-7 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors flex items-center justify-center"
          aria-label="Next page"
          @click="$emit('reviewPage', page + 1)"
        ><ArrowRight class="w-3.5 h-3.5" /></button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useToast } from '../../composables/useToast'
import EmptyState from '../shared/EmptyState.vue'
import { CheckCircle as CheckCircleIcon, ArrowLeftRight, Check, X, ArrowLeft, ArrowRight } from 'lucide-vue-next'

const props = defineProps({
  matches: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})

defineEmits(['reviewPage'])

const toast = useToast()
const dismissed = ref(new Set())
const pendingTimers = ref({})

const totalPages = computed(() => Math.ceil(props.total / props.pageSize))

function similarityClass(score) {
  if (score >= 0.9) return 'bg-green-50 text-green-700'
  if (score >= 0.75) return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-600'
}

function undoAction(productId) {
  clearTimeout(pendingTimers.value[productId])
  delete pendingTimers.value[productId]
  const next = new Set(dismissed.value)
  next.delete(productId)
  dismissed.value = next
}

function acceptMatch(match) {
  dismissed.value = new Set([...dismissed.value, match.product_id])
  const timer = setTimeout(() => { delete pendingTimers.value[match.product_id] }, 5000)
  pendingTimers.value[match.product_id] = timer
  toast.success('Match accepted', `${match.bf_product_name} → Complete`, {
    duration: 5000,
    action: { label: 'Undo', fn: () => undoAction(match.product_id) },
  })
}

function rejectMatch(match) {
  dismissed.value = new Set([...dismissed.value, match.product_id])
  const timer = setTimeout(() => { delete pendingTimers.value[match.product_id] }, 5000)
  pendingTimers.value[match.product_id] = timer
  toast.info('Match rejected', `${match.bf_product_name} → Needs Mapping`, {
    duration: 5000,
    action: { label: 'Undo', fn: () => undoAction(match.product_id) },
  })
}
</script>
