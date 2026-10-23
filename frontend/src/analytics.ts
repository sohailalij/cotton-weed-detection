import { speciesColor } from './overlay'

export interface DayInput {
  day: string
  detections: number
  weeds_found: number
  mean_box_coverage: number
  counts_by_class: Record<string, number>
}

export type ChartRow = Record<string, number | string>

// Same order as the model's class ids, so the colors match the Detect and History pages.
export const SPECIES = [
  'waterhemp',
  'morning_glory',
  'purslane',
  'spotted_spurge',
  'carpetweed',
  'ragweed',
  'eclipta',
  'prickly_sida',
  'palmer_amaranth',
  'sicklepod',
  'goosegrass',
  'cutleaf_groundcherry',
]

export function colorForSpecies(name: string): string {
  const id = SPECIES.indexOf(name)
  return id === -1 ? '#888888' : speciesColor(id)
}

export function summarize(days: DayInput[]) {
  const totals = new Map<string, number>()
  let detections = 0
  let weeds = 0
  for (const d of days) {
    detections += d.detections
    weeds += d.weeds_found
    for (const [name, n] of Object.entries(d.counts_by_class)) {
      totals.set(name, (totals.get(name) ?? 0) + n)
    }
  }
  const species = [...totals.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return { detections, weeds, activeDays: days.length, species }
}

/** Species that occur at all, most common first. */
export function speciesInOrder(days: DayInput[]): string[] {
  return summarize(days).species.map(([name]) => name)
}

/** One row per day for the charts: every species has a count (zero if absent), coverage in percent. */
export function toChartRows(days: DayInput[], species: string[]): ChartRow[] {
  return days.map((d) => {
    const row: ChartRow = {
      day: d.day,
      coveragePercent: Math.round(d.mean_box_coverage * 1000) / 10,
    }
    for (const name of species) row[name] = d.counts_by_class[name] ?? 0
    return row
  })
}

export function formatDay(day: string, locale?: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}