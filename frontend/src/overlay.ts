export interface Box {
  x1: number
  y1: number
  x2: number
  y2: number
}

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value))

/** CSS percentages that place a box over an image of the given pixel size. */
export function boxStyle(box: Box, width: number, height: number) {
  const x1 = clamp(box.x1, 0, width)
  const y1 = clamp(box.y1, 0, height)
  const x2 = clamp(box.x2, 0, width)
  const y2 = clamp(box.y2, 0, height)
  return {
    left: `${(x1 * 100) / width}%`,
    top: `${(y1 * 100) / height}%`,
    width: `${((x2 - x1) * 100) / width}%`,
    height: `${((y2 - y1) * 100) / height}%`,
  }
}

export function atLeast<T extends { confidence: number }>(items: T[], minimum: number): T[] {
  return items.filter((item) => item.confidence >= minimum)
}

/** Species with their counts, most common first, ties in alphabetical order. */
export function countBySpecies(items: { class_name: string }[]): [string, number][] {
  const counts = new Map<string, number>()
  for (const item of items) counts.set(item.class_name, (counts.get(item.class_name) ?? 0) + 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}

/** Share of the image covered by the union of the boxes, on a grid of at most 256 px. */
export function coverage(boxes: Box[], width: number, height: number): number {
  if (boxes.length === 0 || width <= 0 || height <= 0) return 0
  const scale = Math.min(1, 256 / Math.max(width, height))
  const gridW = Math.max(1, Math.round(width * scale))
  const gridH = Math.max(1, Math.round(height * scale))
  const mask = new Uint8Array(gridW * gridH)
  for (const box of boxes) {
    const x0 = clamp(Math.floor(box.x1 * scale), 0, gridW)
    const x1 = clamp(Math.ceil(box.x2 * scale), 0, gridW)
    const y0 = clamp(Math.floor(box.y1 * scale), 0, gridH)
    const y1 = clamp(Math.ceil(box.y2 * scale), 0, gridH)
    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) mask[y * gridW + x] = 1
    }
  }
  let covered = 0
  for (const cell of mask) covered += cell
  return covered / (gridW * gridH)
}

const PALETTE = [
  '#e6194b',
  '#3cb44b',
  '#4363d8',
  '#f58231',
  '#911eb4',
  '#008080',
  '#9a6324',
  '#800000',
  '#808000',
  '#000075',
  '#f032e6',
  '#469990',
]

export const speciesColor = (classId: number) => PALETTE[classId % PALETTE.length] ?? '#000000'