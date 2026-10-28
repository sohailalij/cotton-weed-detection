const STORAGE_KEY = 'weedlab.visitorId'
const VALID_ID = /^[A-Za-z0-9_-]{16,64}$/

let memoryId: string | null = null

/** 128 random bits as hex. getRandomValues also works on plain http, unlike randomUUID. */
function newVisitorId(): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * The id that tells the API whose detections these are. It is made on the first visit and kept
 * in localStorage. When storage is blocked it lives in memory for the session instead.
 */
export function getVisitorId(): string {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored !== null && VALID_ID.test(stored)) return stored
    const fresh = newVisitorId()
    window.localStorage.setItem(STORAGE_KEY, fresh)
    return fresh
  } catch {
    memoryId ??= newVisitorId()
    return memoryId
  }
}

/** Forget the id, so the next call makes a new one. Used by the tests. */
export function clearVisitorId(): void {
  memoryId = null
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage is unavailable, so there is nothing stored to remove.
  }
}