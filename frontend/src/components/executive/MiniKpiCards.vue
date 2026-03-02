<template>
  <div class="flex flex-col gap-4 h-full">
    <!-- Coverage Rate -->
    <div class="bg-white rounded-xl shadow-card flex-1 px-5 py-5 flex items-center gap-4 card-interactive">
      <div class="w-10 h-10 rounded-full bg-brand-lightest flex items-center justify-center shrink-0">
        <BarChart3 class="w-5 h-5 text-brand-primary" />
      </div>
      <div class="min-w-0">
        <div
          class="text-kpi leading-tight"
          :class="coverageColor"
        >{{ coverage }}%</div>
        <div class="text-caption text-grey-500 mt-0.5 flex items-center gap-1">
          Coverage Rate
          <HelpTooltip text="Products Used in PI ÷ Eligible Products. Shows what % of trackable products have matched competitors and fresh prices." />
        </div>
        <div class="text-micro text-grey-400 mt-0.5" v-if="summary">{{ summary.used_products?.toLocaleString() }} used / {{ summary.eligible_products?.toLocaleString() }} eligible</div>
      </div>
    </div>

    <!-- Products Used -->
    <div class="bg-white rounded-xl shadow-card flex-1 px-5 py-5 flex items-center gap-4 card-interactive">
      <div class="w-10 h-10 rounded-full bg-green-50 flex items-center justify-center shrink-0">
        <CheckCircle class="w-5 h-5 text-green-600" />
      </div>
      <div class="min-w-0">
        <div class="text-kpi text-grey-900 leading-tight">{{ usedProducts }}</div>
        <div class="text-caption text-grey-500 mt-0.5">Products Used in PI</div>
      </div>
    </div>

    <!-- Actions Remaining — clickable → Master Data -->
    <div
      class="bg-white rounded-xl shadow-card flex-1 px-5 py-5 flex items-center gap-4 card-interactive cursor-pointer hover:shadow-card-hover transition-shadow group"
      @click="router.push('/master-data')"
    >
      <div class="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center shrink-0">
        <AlertTriangle class="w-5 h-5 text-red-500" />
      </div>
      <div class="min-w-0 flex-1">
        <div class="text-kpi text-red-500 leading-tight">{{ needsAction }}</div>
        <div class="text-caption text-grey-500 mt-0.5">Actions Remaining</div>
      </div>
      <ChevronRight class="w-4 h-4 text-grey-300 group-hover:text-brand-primary transition-colors shrink-0" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import HelpTooltip from '../shared/HelpTooltip.vue'
import { BarChart3, CheckCircle, AlertTriangle, ChevronRight } from 'lucide-vue-next'

const router = useRouter()

const props = defineProps({
  summary: { type: Object, default: null },
})

const coverage = computed(() => props.summary?.coverage_pct ?? '--')
const usedProducts = computed(() => props.summary?.used_products?.toLocaleString() ?? '--')
const needsAction = computed(() => props.summary?.needs_action?.toLocaleString() ?? '--')

const coverageColor = computed(() => {
  const pct = props.summary?.coverage_pct
  if (pct == null) return 'text-grey-400'
  if (pct >= 80) return 'text-green-600'
  if (pct >= 60) return 'text-amber-500'
  return 'text-red-500'
})
</script>
