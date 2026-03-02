<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <div class="flex flex-col gap-4">
      <DefinitionsPanel :sections="definitions" storage-key="defs-master-data" />
      <FilterBar :loading="store.loading" />

      <!-- Action Summary KPIs -->
      <ActionSummary :counts="store.actionSummary" @select="onActionSelect" />

      <!-- Action Breakdown Chart -->
      <div class="animate-fade-in-up" style="animation-delay: 0.1s">
        <ActionBreakdown
          :data="store.actionBreakdown"
          @select="onCategorySelect"
        />
      </div>

      <!-- Priority Worklist -->
      <div class="animate-fade-in-up" style="animation-delay: 0.15s">
        <PriorityWorklist
          :data="store.worklist"
          :total="store.worklistTotal"
          :page="store.currentPage"
          :page-size="store.pageSize"
          @page="onPageChange"
        />
      </div>

      <!-- Bottom Row: Match Review + Staleness -->
      <div ref="bottomRef" class="flex gap-4" :class="{ 'animate-fade-in-up': bottomVisible }">
        <div class="w-1/2">
          <MatchReviewPanel
            :matches="store.matchReviews"
            :total="store.matchReviewsTotal"
            :page="store.reviewPage"
            :page-size="store.reviewPageSize"
            @reviewPage="onReviewPageChange"
          />
        </div>
        <div class="w-1/2">
          <StalenessHeatmap :data="store.staleness" />
        </div>
      </div>
    </div>
  </PageShell>
</template>

<script setup>
import { onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { useFiltersStore } from '../stores/filters'
import { useMasterDataStore } from '../stores/masterData'
import FilterBar from '../components/layout/FilterBar.vue'
import ActionSummary from '../components/master-data/ActionSummary.vue'
import ActionBreakdown from '../components/master-data/ActionBreakdown.vue'
import PriorityWorklist from '../components/master-data/PriorityWorklist.vue'
import MatchReviewPanel from '../components/master-data/MatchReviewPanel.vue'
import StalenessHeatmap from '../components/master-data/StalenessHeatmap.vue'
import { useUrlSync } from '../composables/useUrlSync'
import PageShell from '../components/shared/PageShell.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { useScrollReveal } from '../composables/useScrollReveal'
import { Link, BrainCircuit, RefreshCw, CircleCheck, ListOrdered, Sparkles, CalendarClock } from 'lucide-vue-next'

const filters = useFiltersStore()
useUrlSync()
const store = useMasterDataStore()

const definitions = [
  {
    title: 'Action Types',
    items: [
      { term: 'Needs Mapping', description: 'Eligible product with no competitor match at all \u2014 needs manual pairing.', icon: Link },
      { term: 'Review Match', description: 'System found a potential match but confidence is below threshold \u2014 human review required.', icon: BrainCircuit },
      { term: 'Needs Price Update', description: 'Matched product whose competitor price is stale (>30 days old).', icon: RefreshCw },
      { term: 'Complete', description: 'Product is matched, prices are fresh \u2014 no action needed.', icon: CircleCheck },
    ],
  },
  {
    title: 'How to Use',
    items: [
      { term: 'Priority Worklist', description: 'Products sorted by revenue impact \u2014 resolve top items first for maximum PI coverage improvement.', icon: ListOrdered },
      { term: 'Match Review Panel', description: 'Suggested competitor matches with confidence scores. High scores (\u226590%) are likely correct.', icon: Sparkles },
      { term: 'Staleness Heatmap', description: 'Shows how many days since competitor prices were last updated, by subcategory. Darker = more stale.', icon: CalendarClock },
    ],
  },
]
const { target: bottomRef, isVisible: bottomVisible } = useScrollReveal()

onMounted(async () => {
  await filters.fetchFilterOptions()
  await store.fetchAll()
})

watchDebounced(() => filters.activeFilters, async () => {
  store.currentPage = 1
  store.reviewPage = 1
  await store.fetchAll()
}, { debounce: 400, deep: true })

function onCategorySelect(category) {
  filters.setFilter('mainCategory', category ? [category] : [])
}

function onActionSelect(actionKey) {
  // Map card key to filter value (empty array clears filter)
  filters.setFilter('actionType', actionKey === 'total' ? [] : [actionKey])
}

async function onPageChange(page) {
  await store.setPage(page)
}

async function onReviewPageChange(page) {
  await store.setReviewPage(page)
}
</script>
