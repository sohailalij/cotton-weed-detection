import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'

import { api, ApiError } from './api'
import { atLeast, boxStyle, countBySpecies, coverage, speciesColor } from './overlay'
import './DetectPage.css'

type DetectResult = Awaited<ReturnType<typeof api.detect>>
type Detect = (file: File, conf: number) => Promise<DetectResult>

// Ask the API once at a low cutoff, then filter in the browser as the slider moves.
const FLOOR = 0.15
const DEFAULT_CUTOFF = 0.58

const color = (classId: number) => speciesColor(classId)

type State =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; result: DetectResult }

export default function DetectPage({
  detect = (file, conf) => api.detect(file, conf),
}: {
  detect?: Detect
}) {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [cutoff, setCutoff] = useState(DEFAULT_CUTOFF)

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    },
    [previewUrl],
  )

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0] ?? null
    setFile(chosen)
    setPreviewUrl(chosen ? URL.createObjectURL(chosen) : null)
    setState({ kind: 'idle' })
  }

  async function run() {
    if (!file) return
    setState({ kind: 'loading' })
    try {
      setState({ kind: 'done', result: await detect(file, FLOOR) })
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Could not reach the server'
      setState({ kind: 'error', message })
    }
  }

  const result = state.kind === 'done' ? state.result : null
  const shown = result ? atLeast(result.detections, cutoff) : []
  const species = countBySpecies(shown)
  const colorByName = new Map(shown.map((d) => [d.class_name, color(d.class_id)]))
  const covered = result
    ? coverage(
        shown.map((d) => d.box),
        result.image_width,
        result.image_height,
      )
    : 0

  return (
    <section className="detect">
      <h2>Detect weeds</h2>
      <div className="controls">
        <label>
          Photo{' '}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={onFile}
            disabled={state.kind === 'loading'}
          />
        </label>
        <button type="button" onClick={run} disabled={!file || state.kind === 'loading'}>
          {state.kind === 'loading' ? 'Detecting…' : 'Find weeds'}
        </button>
      </div>
      {state.kind === 'error' && (
        <p role="alert" className="error">
          {state.message}
        </p>
      )}
      {previewUrl && (
        <div className="stage">
          <img src={previewUrl} alt="Uploaded field photo" />
          {result &&
            shown.map((d, i) => (
              <div
                key={`${d.class_name}-${i}`}
                className="box"
                title={`${d.class_name} ${(d.confidence * 100).toFixed(0)}%`}
                style={{
                  ...boxStyle(d.box, result.image_width, result.image_height),
                  borderColor: color(d.class_id),
                }}
              />
            ))}
        </div>
      )}
      {result && (
        <div className="results">
          <label>
            Confidence cutoff: {cutoff.toFixed(2)}{' '}
            <input
              type="range"
              aria-label="Confidence cutoff"
              min={FLOOR}
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
              <ul className="legend">
                {species.map(([name, n]) => (
                  <li key={name}>
                    <span className="swatch" style={{ background: colorByName.get(name) }} />
                    {name}: {n}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}