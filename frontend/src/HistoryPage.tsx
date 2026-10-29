import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

import { api, ApiError } from './api'
import HistoryDetail from './HistoryDetail'
import './HistoryPage.css'

type DetectionList = Awaited<ReturnType<typeof api.detections>>
type Row = DetectionList['items'][number]

const PAGE_SIZE = 12

type Services = {
  list?: (limit: number, offset: number) => Promise<DetectionList>
  remove?: (id: number) => Promise<void>
  imageUrl?: (id: number) => string
}

function Thumbnail({ src }: { src: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div className="history-nophoto" role="img" aria-label="No photo saved">
        No photo
      </div>
    )
  }
  return <img src={src} alt="Saved photo" loading="lazy" onError={() => setFailed(true)} />
}

function speciesText(counts: Row['counts_by_class']): string {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1])
  if (entries.length === 0) return 'no weeds'
  return entries.map(([name, n]) => `${name.replaceAll('_', ' ')} ${n}`).join(', ')
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

const messageOf = (error: unknown) =>
  error instanceof ApiError ? error.message : 'Could not reach the server'

const defaultList = (limit: number, offset: number) => api.detections(limit, offset)
const defaultRemove = (id: number) => api.remove(id)
const defaultImageUrl = (id: number) => api.imageUrl(id)

function ConfirmDialog({
  date,
  src,
  busy,
  onConfirm,
  onCancel,
}: {
  date: string
  src: string
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const titleId = useId()
  const cancelRef = useRef<HTMLButtonElement>(null)

  // Move focus into the dialog, and give it back to the button that opened it afterwards.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    cancelRef.current?.focus()
    return () => opener?.focus()
  }, [])

  useEffect(() => {
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape' && !busy) onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [busy, onCancel])

  // Keep Tab inside the dialog while it is open.
  function trapTab(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
    if (buttons.length === 0) return
    const first = buttons[0]
    const last = buttons[buttons.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel()
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={trapTab}
      >
        <h3 id={titleId}>Delete this detection?</h3>
        <img src={src} alt="" onError={(event) => (event.currentTarget.style.display = 'none')} />
        <p>Saved on {date}.</p>
        <p>The result and its photo will be removed. This cannot be undone.</p>
        <div className="modal-actions">
          <button type="button" ref={cancelRef} onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Deleting…' : 'Yes, delete'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function HistoryPage({
  list = defaultList,
  remove = defaultRemove,
  imageUrl = defaultImageUrl,
}: Services) {
  const [page, setPage] = useState<DetectionList | null>(null)
  const [offset, setOffset] = useState(0)
  const [reloads, setReloads] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    list(PAGE_SIZE, offset)
      .then((next) => {
        if (cancelled) return
        if (next.items.length === 0 && offset > 0) {
          // The last row of this page was deleted, so step back one page.
          setOffset(Math.max(0, offset - PAGE_SIZE))
          return
        }
        setPage(next)
        setError(null)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(messageOf(e))
      })
    return () => {
      cancelled = true
    }
  }, [list, offset, reloads])

  async function confirmDelete(id: number) {
    setDeleting(true)
    try {
      await remove(id)
      setReloads((n) => n + 1)
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setDeleting(false)
      setConfirming(null)
    }
  }

  const total = page?.total ?? 0
  const first = total === 0 ? 0 : offset + 1
  const last = Math.min(offset + PAGE_SIZE, total)
  const toDelete = page?.items.find((row) => row.id === confirming) ?? null

  if (openId !== null) {
    return <HistoryDetail id={openId} onBack={() => setOpenId(null)} />
  }

  return (
    <section className="history">
      <h2>Saved detections</h2>
      <div role="status" aria-live="polite">
        {error && <p className="history-error">{error}</p>}
        {!page && !error && <p className="state">Loading...</p>}
      </div>

      {page && page.total === 0 && <p className="state">No saved detections yet.</p>}

      {page && page.total > 0 && (
        <>
          <p className="history-count">
            Showing {first} to {last} of {total}
          </p>
          <ul className="history-list">
            {page.items.map((row) => (
              <li key={row.id} className="history-row">
                <Thumbnail src={imageUrl(row.id)} />
                <div className="history-info">
                  <strong>{formatDate(row.created_at)}</strong>
                  <span>
                    {row.count} {row.count === 1 ? 'weed' : 'weeds'}: {speciesText(row.counts_by_class)}
                  </span>
                  <span>
                    Cutoff {row.conf_used.toFixed(2)}, boxes cover {Math.round(row.box_coverage * 100)}%
                    of the photo
                  </span>
                </div>
                <div className="history-actions">
                  <button
                    type="button"
                    onClick={() => setOpenId(row.id)}
                    aria-label={`Open detection ${row.id}`}
                  >
                    View
                  </button>
                  <button
                    type="button"
                    className="danger-outline"
                    onClick={() => setConfirming(row.id)}
                    aria-label={`Delete detection ${row.id}`}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {total > PAGE_SIZE && (
            <div className="history-pager">
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {toDelete && (
        <ConfirmDialog
          date={formatDate(toDelete.created_at)}
          src={imageUrl(toDelete.id)}
          busy={deleting}
          onConfirm={() => confirmDelete(toDelete.id)}
          onCancel={() => setConfirming(null)}
        />
      )}
    </section>
  )
}