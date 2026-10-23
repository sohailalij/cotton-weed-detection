import { describe, expect, it } from 'vitest'

import { atLeast, boxStyle, countBySpecies, coverage, speciesColor } from './overlay'

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

function luminance(hex: string): number {
  const channel = (start: number) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
}

const BACKGROUNDS = { dark: '#16171d', light: '#ffffff' } as const

describe('speciesColor', () => {
  it('gives each of the 12 species its own color in both schemes and wraps around', () => {
    for (const scheme of ['dark', 'light'] as const) {
      const colors = Array.from({ length: 12 }, (_, i) => speciesColor(i, scheme))
      expect(new Set(colors).size).toBe(12)
      expect(speciesColor(12, scheme)).toBe(speciesColor(0, scheme))
    }
  })

  it('has different palettes for light and dark pages', () => {
    expect(speciesColor(0, 'light')).not.toBe(speciesColor(0, 'dark'))
  })

  it('stays readable on its page background', () => {
    for (const scheme of ['dark', 'light'] as const) {
      const background = luminance(BACKGROUNDS[scheme])
      for (let id = 0; id < 12; id++) {
        const lum = luminance(speciesColor(id, scheme))
        const ratio = (Math.max(lum, background) + 0.05) / (Math.min(lum, background) + 0.05)
        expect(ratio, `${scheme} class ${id}`).toBeGreaterThanOrEqual(3)
      }
    }
  })

  it('uses the dark palette when the browser cannot report a preference', () => {
    expect(speciesColor(3)).toBe(speciesColor(3, 'dark'))
  })
})