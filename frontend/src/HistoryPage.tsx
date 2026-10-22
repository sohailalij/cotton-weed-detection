import { useEffect, useState } from 'react'

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

const messageOf = (error: unknown) =>
  error instanceof ApiError ? error.message : 'Could not reach the server'

const defaultList = (limit: number, offset: number) => api.detections(limit, offset)
const defaultRemove = (id: number) => api.remove(id)
const defaultImageUrl = (id: number) => api.imageUrl(id)

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
      setConfirming(null)
      setReloads((n) => n + 1)
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setDeleting(false)
    }
  }

  const total = page?.total ?? 0
  const first = total === 0 ? 0 : offset + 1
  const last = Math.min(offset + PAGE_SIZE, total)

  if (openId !== null) {
    return <HistoryDetail id={openId} onBack={() => setOpenId(null)} />
  }

  return (
    <section className="history">
      <h2>Saved detections</h2>
      <div role="status" aria-live="polite">
        {error && <p className="history-error">{error}</p>}
        {!page && !error && <p>Loading...</p>}
      </div>

      {page && page.total === 0 && <p>No saved detections yet.</p>}

      {page && page.total > 0 && (
        <>
          <p>
            Showing {first} to {last} of {total}
          </p>
          <ul className="history-list">
            {page.items.map((row) => (
              <li key={row.id} className="history-row">
                <Thumbnail src={imageUrl(row.id)} />
                <div className="history-info">
                  <strong>
                    {new Date(row.created_at).toLocaleString(undefined, {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </strong>
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
                  {confirming === row.id ? (
                    <>
                      <button type="button" onClick={() => confirmDelete(row.id)} disabled={deleting}>
                        Yes, delete
                      </button>
                      <button type="button" onClick={() => setConfirming(null)} disabled={deleting}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirming(row.id)}
                      aria-label={`Delete detection ${row.id}`}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
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
        </>
      )}
    </section>
  )
}