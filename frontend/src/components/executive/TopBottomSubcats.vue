<template>
  <div class="flex gap-4">
    <!-- Where We're Cheapest -->
    <div class="flex-1 bg-white rounded-xl shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-green-500 shrink-0"></span>
        <span class="text-subheading font-bold text-grey-900">Where We're Cheapest</span>
      </div>
      <div class="py-1">
        <div
          v-for="(item, i) in cheapest"
          :key="item.sub_category_name"
          class="flex items-center gap-3 px-4 py-2.5 hover:bg-brand-50 transition-colors cursor-pointer border-b border-grey-50 last:border-0 group"
          @click="navigateTo(item.sub_category_name)"
        >
          <div class="w-6 h-6 rounded-full bg-green-50 flex items-center justify-center text-micro font-bold text-green-700 shrink-0">
            {{ i + 1 }}
          </div>
          <span class="text-body text-grey-700 flex-1 truncate" style="max-width: 200px" :title="item.sub_category_name">{{ item.sub_category_name }}</span>
          <span class="text-body font-bold text-green-600">{{ item.blended_pi?.toFixed(4) }}</span>
          <span class="text-micro font-semibold text-green-500">▲</span>
          <ChevronRight class="w-3.5 h-3.5 text-grey-300 group-hover:text-brand-primary transition-colors shrink-0" />
        </div>
        <div v-if="!cheapest.length" class="px-4 py-4 text-caption text-grey-400 text-center">No data</div>
      </div>
    </div>

    <!-- Where We're Most Expensive -->
    <div class="flex-1 bg-white rounded-xl shadow-card overflow-hidden">
      <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-red-500 shrink-0"></span>
        <span class="text-subheading font-bold text-grey-900">Where We're Most Expensive</span>
      </div>
      <div class="py-1">
        <div
          v-for="(item, i) in expensive"
          :key="item.sub_category_name"
          class="flex items-center gap-3 px-4 py-2.5 hover:bg-brand-50 transition-colors cursor-pointer border-b border-grey-50 last:border-0 group"
          @click="navigateTo(item.sub_category_name)"
        >
          <div class="w-6 h-6 rounded-full bg-red-50 flex items-center justify-center text-micro font-bold text-red-600 shrink-0">
            {{ i + 1 }}
          </div>
          <span class="text-body text-grey-700 flex-1 truncate" style="max-width: 200px" :title="item.sub_category_name">{{ item.sub_category_name }}</span>
          <span class="text-body font-bold text-red-500">{{ item.blended_pi?.toFixed(4) }}</span>
          <span class="text-micro font-semibold text-red-400">▼</span>
          <ChevronRight class="w-3.5 h-3.5 text-grey-300 group-hover:text-brand-primary transition-colors shrink-0" />
        </div>
        <div v-if="!expensive.length" class="px-4 py-4 text-caption text-grey-400 text-center">No data</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ChevronRight } from 'lucide-vue-next'

defineProps({
  cheapest: { type: Array, default: () => [] },
  expensive: { type: Array, default: () => [] },
})

const router = useRouter()

function navigateTo(subCategory) {
  router.push({ path: '/commercial', query: { subcat: subCategory } })
}
</script>
