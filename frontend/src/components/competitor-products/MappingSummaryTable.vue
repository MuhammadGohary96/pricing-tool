<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex-1">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <BarChart3 class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900">Mapping Summary</span>
        <span class="text-caption text-grey-400 ml-1">per competitor</span>
      </div>
      <ExportButton :fetcher="exportData" filename="mapping_summary.csv" />
    </div>

    <div class="overflow-x-auto">
      <table v-if="data.length" class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th class="px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide">Competitor</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Total</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Mapped BF</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Mapped Comp.</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Unmapped</th>
            <th class="px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width: 150px">Mapping %</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Potential</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Fresh</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Stale</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Avg Age</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in data" :key="row.competitor_name" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <CompetitorLogo :name="row.competitor_name" />
                <span class="text-body font-semibold text-grey-900">{{ row.competitor_name }}</span>
              </div>
            </td>
            <td class="px-4 py-3 text-right text-body font-mono text-grey-900">{{ row.total.toLocaleString() }}</td>
            <td class="px-4 py-3 text-right text-body font-mono text-green-600">{{ row.mapped_bf.toLocaleString() }}</td>
            <td class="px-4 py-3 text-right text-body font-mono text-green-500">{{ row.mapped_competitor.toLocaleString() }}</td>
            <td class="px-4 py-3 text-right text-body font-mono text-grey-500">{{ row.unmapped.toLocaleString() }}</td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <div class="flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all duration-500"
                    :class="barColor(row.mapping_pct)"
                    :style="{ width: `${row.mapping_pct}%` }"
                  ></div>
                </div>
                <span class="text-caption font-semibold w-10 text-right" :class="pctColor(row.mapping_pct)">
                  {{ row.mapping_pct }}%
                </span>
              </div>
            </td>
            <td class="px-4 py-3 text-right text-body font-mono text-amber-600">{{ row.with_ai_match.toLocaleString() }}</td>
            <td class="px-4 py-3 text-right text-body font-mono text-green-600">{{ row.fresh.toLocaleString() }}</td>
            <td class="px-4 py-3 text-right text-body font-mono text-red-500">{{ row.stale.toLocaleString() }}</td>
            <td class="px-4 py-3 text-right text-body font-mono text-grey-600">
              {{ row.avg_crawl_age != null ? `${row.avg_crawl_age}d` : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="px-4 py-8 text-center text-grey-400 text-body">No data available</div>
    </div>
  </div>
</template>

<script setup>
import { BarChart3 } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

function barColor(pct) {
  if (pct >= 60) return 'bg-green-500'
  if (pct >= 35) return 'bg-amber-400'
  return 'bg-red-500'
}

function pctColor(pct) {
  if (pct >= 60) return 'text-green-600'
  if (pct >= 35) return 'text-amber-600'
  return 'text-red-600'
}

function exportData() {
  return props.data.map((r) => ({
    competitor: r.competitor_name,
    total: r.total,
    mapped_bf: r.mapped_bf,
    mapped_competitor: r.mapped_competitor,
    unmapped: r.unmapped,
    mapping_pct: r.mapping_pct,
    ai_match: r.with_ai_match,
    fresh: r.fresh,
    stale: r.stale,
    avg_crawl_age: r.avg_crawl_age,
  }))
}
</script>
