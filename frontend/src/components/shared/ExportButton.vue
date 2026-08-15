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

    // Server-rendered file: the fetcher returns { blob, filename }. Used for
    // styled workbooks, which cannot be produced in the browser — the community
    // build of SheetJS writes values but no cell formatting.
    if (data.blob) {
      const url = URL.createObjectURL(data.blob)
      const a = document.createElement('a')
      a.href = url
      a.download = data.filename || props.filename
      a.click()
      URL.revokeObjectURL(url)
      return
    }

    // Multi-sheet workbook: fetcher returns
    //   { sheets: [{ name, rows, title?, note?, widths? }], filename }
    // title/note reproduce the layout of the hand-built brand-portfolio
    // workbook — blank row 1, title on row 2, optional note on row 3, blank,
    // then the table — so an export can be dropped straight in beside the
    // sheets that were made by hand.
    if (data.sheets) {
      const sheets = data.sheets.filter(s => s && s.rows && s.rows.length)
      if (!sheets.length) return
      const XLSX = await import('xlsx')
      const wb = XLSX.utils.book_new()
      const used = new Set()
      for (const sheet of sheets) {
        let ws, headerRow
        if (sheet.title) {
          ws = XLSX.utils.aoa_to_sheet([[], [sheet.title]])
          if (sheet.note) XLSX.utils.sheet_add_aoa(ws, [[sheet.note]], { origin: 'A3' })
          headerRow = sheet.note ? 5 : 4          // matches the workbook exactly
          XLSX.utils.sheet_add_json(ws, sheet.rows, { origin: `A${headerRow}` })
        } else {
          ws = XLSX.utils.json_to_sheet(sheet.rows)
          headerRow = 1
        }
        // Freeze above the first data row so headers stay put while scrolling.
        ws['!freeze'] = { xSplit: 0, ySplit: headerRow }
        ws['!autofilter'] = {
          ref: XLSX.utils.encode_range({
            s: { r: headerRow - 1, c: 0 },
            e: { r: headerRow - 1 + sheet.rows.length,
                 c: Math.max(0, Object.keys(sheet.rows[0]).length - 1) },
          }),
        }
        if (sheet.widths) ws['!cols'] = sheet.widths.map(w => ({ wch: w }))
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
