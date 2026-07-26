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

// Excel sheet-name rules: ≤31 chars, none of  : \ / ? * [ ]  — and unique.
function safeSheetName(name, used) {
  let n = String(name || 'Sheet').replace(/[:\\/?*[\]]/g, ' ').trim().slice(0, 31) || 'Sheet'
  let base = n, i = 2
  while (used.has(n)) { const suffix = ` (${i++})`; n = base.slice(0, 31 - suffix.length) + suffix }
  used.add(n)
  return n
}

async function handleExport() {
  loading.value = true
  try {
    const data = await props.fetcher()
    if (!data) return

    // Multi-sheet workbook: fetcher returns { sheets: [{ name, rows }], filename }.
    if (data.sheets) {
      const sheets = data.sheets.filter(s => s && s.rows && s.rows.length)
      if (!sheets.length) return
      const XLSX = await import('xlsx')
      const wb = XLSX.utils.book_new()
      const used = new Set()
      for (const sheet of sheets) {
        const ws = XLSX.utils.json_to_sheet(sheet.rows)
        XLSX.utils.book_append_sheet(wb, ws, safeSheetName(sheet.name, used))
      }
      XLSX.writeFile(wb, data.filename || props.filename.replace(/\.csv$/, '.xlsx'))
      return
    }

    if (!data.length) return

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
