import { describe, expect, it } from 'vitest'

import {
  colorForSpecies,
  formatDay,
  SPECIES,
  speciesInOrder,
  summarize,
  toChartRows,
} from './analytics'
import type { DayInput } from './analytics'
import { speciesColor } from './overlay'

const days: DayInput[] = [
  {
    day: '2026-10-20',
    detections: 1,
    weeds_found: 2,
    mean_box_coverage: 0.1234,
    counts_by_class: { ragweed: 2 },
  },
  {
    day: '2026-10-21',
    detections: 2,
    weeds_found: 4,
    mean_box_coverage: 0.405,
    counts_by_class: { ragweed: 1, waterhemp: 3 },
  },
]

describe('summarize', () => {
  it('adds up detections, weeds and species over all days', () => {
    expect(summarize(days)).toEqual({
      detections: 3,
      weeds: 6,
      activeDays: 2,
      species: [
        ['ragweed', 3],
        ['waterhemp', 3],
      ],
    })
  })

  it('handles no days', () => {
    expect(summarize([])).toEqual({ detections: 0, weeds: 0, activeDays: 0, species: [] })
  })
})

describe('speciesInOrder', () => {
  it('orders by total, then by name', () => {
    expect(speciesInOrder(days)).toEqual(['ragweed', 'waterhemp'])
  })
})

describe('toChartRows', () => {
  it('fills in zero for absent species and converts coverage to percent', () => {
    expect(toChartRows(days, ['ragweed', 'waterhemp'])).toEqual([
      { day: '2026-10-20', coveragePercent: 12.3, ragweed: 2, waterhemp: 0 },
      { day: '2026-10-21', coveragePercent: 40.5, ragweed: 1, waterhemp: 3 },
    ])
  })
})

describe('colorForSpecies', () => {
  it('matches the colors of the class ids and has a fallback', () => {
    expect(SPECIES).toHaveLength(12)
    expect(colorForSpecies('waterhemp')).toBe(speciesColor(0))
    expect(colorForSpecies('ragweed')).toBe(speciesColor(5))
    expect(colorForSpecies('something_new')).toBe('#888888')
  })
})

describe('formatDay', () => {
  it('shows the UTC day without shifting it to local time', () => {
    expect(formatDay('2026-10-21', 'en-US')).toBe('Oct 21')
    expect(formatDay('2026-01-01', 'en-US')).toBe('Jan 1')
  })
})