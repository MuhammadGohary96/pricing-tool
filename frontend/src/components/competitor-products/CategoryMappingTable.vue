<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden flex-1">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Layers class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Category Breakdown</span>
        <span class="text-caption text-grey-400 ml-1">by competitor</span>
      </div>
      <ExportButton :fetcher="exportData" filename="category_breakdown.csv" />
    </div>

    <div class="overflow-x-auto max-h-[500px] overflow-y-auto">
      <table v-if="competitorRows.length" class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100 sticky top-0 z-10">
          <tr>
            <th class="px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width: 220px">Name</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Total</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Mapped BF</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Mapped Comp.</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Unmapped</th>
            <th class="px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width: 130px">Mapping %</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Potential</th>
            <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Avg Price</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="comp in competitorRows" :key="comp.competitor_name">
            <!-- Competitor Row -->
            <tr
              class="cursor-pointer transition-colors border-b border-grey-100"
              :class="ex.comp === comp.competitor_name ? 'bg-brand-50' : 'hover:bg-grey-50'"
              @click="toggleComp(comp.competitor_name)"
            >
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-1.5">
                  <ChevronRight class="w-4 h-4 text-grey-400 transition-transform duration-200 shrink-0" :class="{ 'rotate-90': ex.comp === comp.competitor_name }" />
                  <CompetitorLogo :name="comp.competitor_name" />
                  <span class="text-body font-bold text-grey-900">{{ comp.competitor_name }}</span>
                </div>
              </td>
              <MetricCells :row="comp" weight="bold" />
            </tr>

            <!-- L1 Rows -->
            <template v-if="ex.comp === comp.competitor_name">
              <template v-for="l1 in getChildren('l1', comp.competitor_name)" :key="`${comp.competitor_name}-${l1.category_level_1}`">
                <tr
                  class="cursor-pointer transition-colors"
                  :class="ex.l1 === compL1Key(comp.competitor_name, l1.category_level_1) ? 'bg-brand-50' : 'hover:bg-grey-50'"
                  @click.stop="toggleL1(comp.competitor_name, l1.category_level_1)"
                >
                  <td class="py-2 pr-4" style="padding-left: 2rem">
                    <div class="flex items-center gap-1.5">
                      <ChevronRight class="w-3.5 h-3.5 text-grey-300 transition-transform duration-200 shrink-0" :class="{ 'rotate-90': ex.l1 === compL1Key(comp.competitor_name, l1.category_level_1) }" />
                      <span class="text-body font-semibold text-grey-800">{{ l1.category_level_1 }}</span>
                    </div>
                  </td>
                  <MetricCells :row="l1" weight="semibold" />
                </tr>

                <!-- L2 Rows -->
                <template v-if="ex.l1 === compL1Key(comp.competitor_name, l1.category_level_1)">
                  <template v-for="l2 in getChildren('l2', comp.competitor_name, l1.category_level_1)" :key="`${comp.competitor_name}-${l1.category_level_1}-${l2.category_level_2}`">
                    <tr
                      class="cursor-pointer transition-colors"
                      :class="ex.l2 === compL2Key(comp.competitor_name, l1.category_level_1, l2.category_level_2) ? 'bg-brand-50' : 'hover:bg-grey-50'"
                      @click.stop="toggleL2(comp.competitor_name, l1.category_level_1, l2.category_level_2)"
                    >
                      <td class="py-2 pr-4" style="padding-left: 3.25rem">
                        <div class="flex items-center gap-1.5">
                          <ChevronRight class="w-3 h-3 text-grey-300 transition-transform duration-200 shrink-0" :class="{ 'rotate-90': ex.l2 === compL2Key(comp.competitor_name, l1.category_level_1, l2.category_level_2) }" />
                          <span class="text-body text-grey-700">{{ l2.category_level_2 }}</span>
                        </div>
                      </td>
                      <MetricCells :row="l2" weight="normal" muted />
                    </tr>

                    <!-- L3 Rows -->
                    <template v-if="ex.l2 === compL2Key(comp.competitor_name, l1.category_level_1, l2.category_level_2)">
                      <tr
                        v-for="l3 in getChildren('l3', comp.competitor_name, l1.category_level_1, l2.category_level_2)"
                        :key="`${comp.competitor_name}-${l1.category_level_1}-${l2.category_level_2}-${l3.category_level_3}`"
                        class="hover:bg-grey-50 transition-colors"
                      >
                        <td class="py-1.5 pr-4" style="padding-left: 4.5rem">
                          <span class="text-body text-grey-500">{{ l3.category_level_3 }}</span>
                        </td>
                        <MetricCells :row="l3" weight="normal" muted />
                      </tr>
                    </template>
                  </template>
                </template>
              </template>
            </template>
          </template>
        </tbody>
      </table>
      <div v-else class="px-4 py-8 text-center text-grey-400 text-body">No data available</div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, h, defineComponent } from 'vue'
import { Layers, ChevronRight } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

// Inline functional component for metric cells to avoid repeating 7 <td> blocks
const MetricCells = defineComponent({
  props: {
    row: { type: Object, required: true },
    weight: { type: String, default: 'normal' },
    muted: { type: Boolean, default: false },
  },
  setup(props) {
    return () => {
      const r = props.row
      const m = props.muted
      const num = m ? 'text-grey-500' : 'text-grey-900'
      const green = m ? 'text-green-400' : 'text-green-600'
      const green2 = m ? 'text-green-400' : 'text-green-500'
      const grey = m ? 'text-grey-400' : 'text-grey-500'
      const amber = m ? 'text-amber-400' : 'text-amber-600'
      const price = m ? 'text-grey-400' : 'text-grey-600'
      const barH = m ? 'h-1' : 'h-1.5'

      const pct = r.mapping_pct
      const barBg = pct >= 60 ? 'bg-green-500' : pct >= 35 ? 'bg-amber-400' : 'bg-red-500'
      const pctTxt = pct >= 60 ? 'text-green-600' : pct >= 35 ? 'text-amber-600' : 'text-red-600'

      return [
        h('td', { class: `px-4 py-2 text-right text-body font-mono ${num}` }, r.total.toLocaleString()),
        h('td', { class: `px-4 py-2 text-right text-body font-mono ${green}` }, r.mapped_bf.toLocaleString()),
        h('td', { class: `px-4 py-2 text-right text-body font-mono ${green2}` }, r.mapped_competitor.toLocaleString()),
        h('td', { class: `px-4 py-2 text-right text-body font-mono ${grey}` }, r.unmapped.toLocaleString()),
        h('td', { class: 'px-4 py-2' }, [
          h('div', { class: 'flex items-center gap-2' }, [
            h('div', { class: `flex-1 ${barH} bg-grey-100 rounded-full overflow-hidden` }, [
              h('div', { class: `h-full rounded-full transition-all duration-500 ${barBg}`, style: { width: `${pct}%` } }),
            ]),
            h('span', { class: `text-caption font-semibold w-10 text-right ${pctTxt}` }, `${pct}%`),
          ]),
        ]),
        h('td', { class: `px-4 py-2 text-right text-body font-mono ${amber}` }, r.ai_match.toLocaleString()),
        h('td', { class: `px-4 py-2 text-right text-body font-mono ${price}` }, r.avg_competitor_price != null ? r.avg_competitor_price.toLocaleString() : '—'),
      ]
    }
  },
})

const ex = reactive({ comp: null, l1: null, l2: null })

const competitorRows = computed(() =>
  props.data
    .filter((r) => r.level === 'competitor')
    .sort((a, b) => b.total - a.total)
)

function getChildren(level, compName, l1, l2) {
  return props.data
    .filter((r) => {
      if (r.level !== level) return false
      if (r.competitor_name !== compName) return false
      if (level === 'l1') return true
      if (r.category_level_1 !== l1) return false
      if (level === 'l2') return true
      return r.category_level_2 === l2
    })
    .sort((a, b) => b.total - a.total)
}

function compL1Key(comp, l1) { return `${comp}::${l1}` }
function compL2Key(comp, l1, l2) { return `${comp}::${l1}::${l2}` }

function toggleComp(comp) {
  if (ex.comp === comp) {
    ex.comp = null; ex.l1 = null; ex.l2 = null
  } else {
    ex.comp = comp; ex.l1 = null; ex.l2 = null
  }
}

function toggleL1(comp, l1) {
  const key = compL1Key(comp, l1)
  if (ex.l1 === key) {
    ex.l1 = null; ex.l2 = null
  } else {
    ex.l1 = key; ex.l2 = null
  }
}

function toggleL2(comp, l1, l2) {
  const key = compL2Key(comp, l1, l2)
  ex.l2 = ex.l2 === key ? null : key
}

function exportData() {
  return props.data.map((r) => ({
    level: r.level,
    competitor_name: r.competitor_name,
    category_level_1: r.category_level_1 || '',
    category_level_2: r.category_level_2 || '',
    category_level_3: r.category_level_3 || '',
    total: r.total,
    mapped_bf: r.mapped_bf,
    mapped_competitor: r.mapped_competitor,
    unmapped: r.unmapped,
    mapping_pct: r.mapping_pct,
    ai_match: r.ai_match,
    avg_competitor_price: r.avg_competitor_price,
  }))
}
</script>
