<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <span class="text-subheading font-bold text-grey-900">Match Review</span>
      <span class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">
        {{ total.toLocaleString() }} pending · Accept or Reject
      </span>
    </div>

    <div class="overflow-y-auto p-3 flex flex-col gap-2.5" style="max-height: 420px">
      <!-- Match Card -->
      <div
        v-for="(match, idx) in matches"
        :key="match.product_id"
        class="border border-grey-200 rounded-lg p-3.5 transition-all duration-150 hover:border-brand-light hover:shadow-card"
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
          <div class="text-grey-300 text-heading shrink-0">↔</div>
          <div class="flex-1 bg-grey-50 rounded-md p-2.5 min-w-0">
            <div class="text-micro font-bold uppercase tracking-wide text-grey-400 mb-1">Talabat</div>
            <div class="text-body font-medium text-grey-800 truncate" :title="match.suggested_talabat_name">{{ match.suggested_talabat_name }}</div>
            <div class="text-caption font-bold text-grey-700 mt-0.5">Est. EGP {{ match.estimated_talabat_price?.toFixed(1) }}</div>
          </div>
        </div>

        <!-- Score Bar -->
        <div class="h-2 bg-grey-100 rounded-full mb-2.5 overflow-hidden">
          <div
            class="h-full rounded-full bg-gradient-to-r from-brand-primary to-green-400"
            :style="{ width: (match.similarity_score * 100) + '%' }"
          />
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-2">
          <button
            class="flex-1 py-1.5 rounded-lg text-caption font-semibold bg-green-600 text-white hover:bg-green-700 transition-colors"
            @click="acceptMatch(match)"
          >✓ Accept</button>
          <button
            class="flex-1 py-1.5 rounded-lg text-caption font-semibold bg-grey-100 text-grey-600 border border-grey-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
            @click="rejectMatch(match)"
          >✕ Reject</button>
        </div>
      </div>

      <EmptyState v-if="!matches.length" :icon="CheckCircleIcon" title="All caught up!" message="All matches reviewed. Check back after the next data sync." />
    </div>

    <!-- Pagination — pill style to differentiate from Worklist pagination -->
    <div v-if="totalPages > 1" class="px-4 py-2.5 border-t-2 border-brand-light flex items-center justify-between bg-brand-50/30 gap-3">
      <span class="text-caption text-brand-primary font-medium shrink-0">
        {{ ((page - 1) * pageSize + 1) }}&ndash;{{ Math.min(page * pageSize, total) }} of {{ total }}
      </span>
      <div class="flex items-center gap-1.5">
        <button
          :disabled="page <= 1"
          class="text-caption w-7 h-7 rounded-full border border-brand-light bg-white hover:bg-brand-50 disabled:opacity-40 transition-colors flex items-center justify-center"
          @click="$emit('reviewPage', page - 1)"
        >&larr;</button>
        <span class="text-caption text-brand-primary font-bold px-2">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          class="text-caption w-7 h-7 rounded-full border border-brand-light bg-white hover:bg-brand-50 disabled:opacity-40 transition-colors flex items-center justify-center"
          @click="$emit('reviewPage', page + 1)"
        >&rarr;</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useToast } from '../../composables/useToast'
import EmptyState from '../shared/EmptyState.vue'
import { CheckCircle as CheckCircleIcon } from 'lucide-vue-next'

const props = defineProps({
  matches: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})

defineEmits(['reviewPage'])

const toast = useToast()
const dismissed = ref(new Set())

const totalPages = computed(() => Math.ceil(props.total / props.pageSize))

function similarityClass(score) {
  if (score >= 0.9) return 'bg-green-50 text-green-700'
  if (score >= 0.75) return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-600'
}

function acceptMatch(match) {
  dismissed.value.add(match.product_id)
  toast.success('Match accepted', `${match.bf_product_name} → Complete`)
}

function rejectMatch(match) {
  dismissed.value.add(match.product_id)
  toast.info('Match rejected', `${match.bf_product_name} → Needs Mapping`)
}
</script>
