import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearVisitorId, getVisitorId } from './visitor'

const VALID_ID = /^[A-Za-z0-9_-]{16,64}$/

beforeEach(() => {
  clearVisitorId()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('getVisitorId', () => {
  it('makes a valid id and keeps it', () => {
    const first = getVisitorId()
    expect(first).toMatch(VALID_ID)
    expect(getVisitorId()).toBe(first)
    expect(window.localStorage.getItem('weedlab.visitorId')).toBe(first)
  })

  it('makes a different id after the old one is forgotten', () => {
    const first = getVisitorId()
    clearVisitorId()
    expect(getVisitorId()).not.toBe(first)
  })

  it('replaces a stored value that the API would reject', () => {
    window.localStorage.setItem('weedlab.visitorId', 'not valid!')
    const id = getVisitorId()
    expect(id).toMatch(VALID_ID)
    expect(window.localStorage.getItem('weedlab.visitorId')).toBe(id)
  })

  it('works when only getRandomValues exists, as on a plain http page', () => {
    vi.stubGlobal('crypto', { getRandomValues: globalThis.crypto.getRandomValues.bind(crypto) })
    expect(getVisitorId()).toMatch(VALID_ID)
  })

  it('keeps one id in memory when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const first = getVisitorId()
    expect(first).toMatch(VALID_ID)
    expect(getVisitorId()).toBe(first)
  })
})