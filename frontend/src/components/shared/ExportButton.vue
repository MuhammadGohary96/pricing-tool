<template>
  <PillButton
    variant="ghost"
    size="sm"
    :icon="Download"
    :loading="loading"
    @click="handleExport"
  >
    {{ loading ? 'Exporting...' : label }}
  </PillButton>
</template>

<script setup>
import { ref } from 'vue'
import { Download } from 'lucide-vue-next'
import PillButton from './PillButton.vue'

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
