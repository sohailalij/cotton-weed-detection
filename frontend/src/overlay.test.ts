import { describe, expect, it } from 'vitest'

import { atLeast, boxStyle, countBySpecies, coverage } from './overlay'

describe('boxStyle', () => {
  it('converts pixel boxes to percentages of the image', () => {
    const style = boxStyle({ x1: 20, y1: 10, x2: 120, y2: 60 }, 200, 100)
    expect(style).toEqual({ left: '10%', top: '10%', width: '50%', height: '50%' })
  })

  it('clips boxes that stick out of the image', () => {
    const style = boxStyle({ x1: -50, y1: -50, x2: 50, y2: 50 }, 100, 100)
    expect(style).toEqual({ left: '0%', top: '0%', width: '50%', height: '50%' })
  })
})

describe('atLeast', () => {
  it('keeps items at or above the cutoff', () => {
    const items = [{ confidence: 0.3 }, { confidence: 0.58 }, { confidence: 0.9 }]
    expect(atLeast(items, 0.58)).toEqual([{ confidence: 0.58 }, { confidence: 0.9 }])
    expect(atLeast(items, 0.95)).toEqual([])
  })
})

describe('countBySpecies', () => {
  it('sorts by count, then by name', () => {
    const items = ['ragweed', 'waterhemp', 'ragweed', 'eclipta'].map((class_name) => ({ class_name }))
    expect(countBySpecies(items)).toEqual([
      ['ragweed', 2],
      ['eclipta', 1],
      ['waterhemp', 1],
    ])
  })

  it('returns an empty list for no detections', () => {
    expect(countBySpecies([])).toEqual([])
  })
})

describe('coverage', () => {
  it('is zero without boxes', () => {
    expect(coverage([], 100, 100)).toBe(0)
  })

  it('counts overlapping boxes once', () => {
    const boxes = [
      { x1: 0, y1: 0, x2: 50, y2: 100 },
      { x1: 25, y1: 0, x2: 75, y2: 100 },
    ]
    expect(coverage(boxes, 100, 100)).toBe(0.75)
  })

  it('clips boxes to the image', () => {
    expect(coverage([{ x1: -50, y1: -50, x2: 50, y2: 50 }], 100, 100)).toBe(0.25)
  })
})