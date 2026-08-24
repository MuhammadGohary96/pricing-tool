// Sync/freshness timestamps from the backend.
//
// The backend emits ISO strings that are timezone-aware UTC going forward;
// values written before that change are naive but were produced in UTC.
// JavaScript parses an offset-less ISO string as LOCAL time, which is how a
// UTC timestamp ends up displayed three hours off in Cairo — so parseTs pins
// offset-less strings to UTC before any math or display.
export function parseTs(iso) {
  if (!iso) return null
  const hasOffset = /[Zz]$|[+-]\d\d:?\d\d$/.test(iso)
  return new Date(hasOffset ? iso : iso + 'Z')
}

// Every wall-clock time in the UI reads in Cairo time, whatever the viewer's
// machine is set to — the business runs on Egypt time.
export function fmtCairo(d) {
  if (!d) return ''
  return d.toLocaleString('en-GB', {
    timeZone: 'Africa/Cairo',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }) + ' Cairo'
}
