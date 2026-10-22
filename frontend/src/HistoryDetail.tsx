import { useEffect, useState } from 'react'

import { api, ApiError } from './api'
import { atLeast, boxStyle, countBySpecies, coverage, speciesColor } from './overlay'
import './HistoryDetail.css'

type Detail = Awaited<ReturnType<typeof api.detection>>

const MIN_CUTOFF = 0.15
const DEFAULT_CUTOFF = 0.58

const defaultLoad = (id: number) => api.detection(id)
const defaultImageUrl = (id: number) => api.imageUrl(id)

export default function HistoryDetail({
  id,
  onBack,
  load = defaultLoad,
  imageUrl = defaultImageUrl,
}: {
  id: number
  onBack: () => void
  load?: (id: number) => Promise<Detail>
  imageUrl?: (id: number) => string
}) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cutoff, setCutoff] = useState(DEFAULT_CUTOFF)
  const [photoFailed, setPhotoFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    load(id)
      .then((next) => {
        if (!cancelled) setDetail(next)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Could not reach the server')
      })
    return () => {
      cancelled = true
    }
  }, [id, load])

  const shown = detail ? atLeast(detail.detections, cutoff) : []
  const species = countBySpecies(shown)
  const colorByName = new Map(shown.map((d) => [d.class_name, speciesColor(d.class_id)]))
  const covered = detail
    ? coverage(
        shown.map((d) => d.box),
        detail.image_width,
        detail.image_height,
      )
    : 0

  return (
    <section className="detail">
      <button type="button" onClick={onBack}>
        Back to the list
      </button>
      {error && (
        <p role="alert" className="detail-error">
          {error}
        </p>
      )}
      {!detail && !error && <p>Loading...</p>}
      {detail && (
        <>
          <h2>Detection {detail.id}</h2>
          <p>
            {new Date(detail.created_at).toLocaleString(undefined, {
              dateStyle: 'medium',
              timeStyle: 'short',
            })}
          </p>
          {photoFailed ? (
            <p>No photo was saved for this detection.</p>
          ) : (
            <div className="detail-stage">
              <img
                src={imageUrl(detail.id)}
                alt="Saved photo"
                onError={() => setPhotoFailed(true)}
              />
              {shown.map((d, i) => (
                <div
                  key={`${d.class_name}-${i}`}
                  className="detail-box"
                  title={`${d.class_name} ${(d.confidence * 100).toFixed(0)}%`}
                  style={{
                    ...boxStyle(d.box, detail.image_width, detail.image_height),
                    borderColor: speciesColor(d.class_id),
                  }}
                />
              ))}
            </div>
          )}
          <label>
            Confidence cutoff: {cutoff.toFixed(2)}{' '}
            <input
              type="range"
              aria-label="Confidence cutoff"
              min={MIN_CUTOFF}
              max={0.95}
              step={0.01}
              value={cutoff}
              onChange={(e) => setCutoff(Number(e.target.value))}
            />
          </label>
          {shown.length === 0 ? (
            <p>No weeds found at this cutoff.</p>
          ) : (
            <>
              <p>
                {shown.length} detections, covering {(covered * 100).toFixed(1)}% of the photo
              </p>
              <ul className="detail-legend">
                {species.map(([name, n]) => (
                  <li key={name}>
                    <span className="detail-swatch" style={{ background: colorByName.get(name) }} />
                    {name}: {n}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  )
}