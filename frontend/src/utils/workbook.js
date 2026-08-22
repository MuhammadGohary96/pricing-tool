/**
 * Every styled .xlsx in this app is rendered by the backend with openpyxl — the
 * community build of SheetJS writes values but no fills, fonts or number
 * formats, so a browser-built workbook cannot carry the house style at all.
 *
 * That makes each export a blob response rather than JSON. This unwraps one into
 * the `{ blob, filename }` shape ExportButton downloads, preferring the server's
 * own Content-Disposition name so the filename lives in one place.
 */
export async function asDownload(promise, fallbackName) {
  const res = await promise
  const name = /filename="([^"]+)"/.exec(res.headers?.['content-disposition'] || '')?.[1]
  return { blob: res.data, filename: name || fallbackName }
}
