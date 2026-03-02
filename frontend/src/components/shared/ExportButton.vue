<template>
  <button
    class="text-caption px-3 py-1.5 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 hover:shadow-card flex items-center gap-1.5 disabled:opacity-40 transition-all"
    :disabled="loading"
    @click="handleExport"
  >
    <Loader2 v-if="loading" class="w-3.5 h-3.5 animate-spin" />
    <Download v-else class="w-3.5 h-3.5" />
    {{ loading ? 'Exporting...' : label }}
  </button>
</template>

<script setup>
import { ref } from 'vue'
import { Download, Loader2 } from 'lucide-vue-next'

const props = defineProps({
  label: { type: String, default: 'Export CSV' },
  filename: { type: String, default: 'export.csv' },
  fetcher: { type: Function, required: true },
})

const loading = ref(false)

async function handleExport() {
  loading.value = true
  try {
    const data = await props.fetcher()
    if (!data || !data.length) return

    const headers = Object.keys(data[0])
    const csvRows = [
      headers.join(','),
      ...data.map(row =>
        headers.map(h => {
          const val = row[h]
          if (val == null) return ''
          if (typeof val === 'string' && (val.includes(',') || val.includes('"')))
            return `"${val.replace(/"/g, '""')}"`
          return val
        }).join(',')
      ),
    ]
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = props.filename
    a.click()
    URL.revokeObjectURL(url)
  } finally {
    loading.value = false
  }
}
</script>
