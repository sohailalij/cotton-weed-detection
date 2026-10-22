import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import HistoryDetail from './HistoryDetail'

type Detail = Awaited<ReturnType<typeof api.detection>>

const detail: Detail = {
  id: 4,
  created_at: '2026-10-21T09:54:54Z',
  model_name: 'yolo11s_v1_960',
  image_width: 200,
  image_height: 100,
  conf_used: 0.15,
  count: 3,
  box_coverage: 0.5,
  counts_by_class: { waterhemp: 1, ragweed: 2 },
  detections: [
    { box: { x1: 0, y1: 0, x2: 100, y2: 50 }, confidence: 0.9, class_id: 0, class_name: 'waterhemp' },
    { box: { x1: 100, y1: 50, x2: 200, y2: 100 }, confidence: 0.7, class_id: 5, class_name: 'ragweed' },
    { box: { x1: 20, y1: 20, x2: 40, y2: 40 }, confidence: 0.3, class_id: 5, class_name: 'ragweed' },
  ],
}

const imageUrl = (id: number) => `/img/${id}`

describe('HistoryDetail', () => {
  it('loads the detection and shows the photo with boxes above the default cutoff', async () => {
    const load = vi.fn(() => Promise.resolve(detail))
    render(<HistoryDetail id={4} onBack={vi.fn()} load={load} imageUrl={imageUrl} />)
    expect(await screen.findByRole('heading', { name: 'Detection 4' })).toBeInTheDocument()
    expect(load).toHaveBeenCalledWith(4)
    expect(screen.getByAltText('Saved photo')).toHaveAttribute('src', '/img/4')
    expect(screen.getAllByTitle(/\d+%$/)).toHaveLength(2)
    expect(screen.getByText(/2 detections, covering 50.0% of the photo/)).toBeInTheDocument()
    expect(screen.getByText(/waterhemp: 1/)).toBeInTheDocument()
    expect(screen.getByText(/ragweed: 1/)).toBeInTheDocument()
  })

  it('shows and hides boxes as the slider moves', async () => {
    render(
      <HistoryDetail id={4} onBack={vi.fn()} load={() => Promise.resolve(detail)} imageUrl={imageUrl} />,
    )
    await screen.findByRole('heading', { name: 'Detection 4' })
    const slider = screen.getByLabelText('Confidence cutoff')
    fireEvent.change(slider, { target: { value: '0.2' } })
    expect(screen.getAllByTitle(/\d+%$/)).toHaveLength(3)
    fireEvent.change(slider, { target: { value: '0.95' } })
    expect(screen.getByText('No weeds found at this cutoff.')).toBeInTheDocument()
  })

  it('shows a loading message while waiting', () => {
    const load = () => new Promise<Detail>(() => {})
    render(<HistoryDetail id={4} onBack={vi.fn()} load={load} imageUrl={imageUrl} />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows the message from an API error', async () => {
    const load = () => Promise.reject(new ApiError(404, 'detection not found'))
    render(<HistoryDetail id={4} onBack={vi.fn()} load={load} imageUrl={imageUrl} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('detection not found')
  })

  it('explains a network failure without leaking details', async () => {
    const load = () => Promise.reject(new Error('boom'))
    render(<HistoryDetail id={4} onBack={vi.fn()} load={load} imageUrl={imageUrl} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
  })

  it('says so when the photo cannot be loaded', async () => {
    render(
      <HistoryDetail id={4} onBack={vi.fn()} load={() => Promise.resolve(detail)} imageUrl={imageUrl} />,
    )
    fireEvent.error(await screen.findByAltText('Saved photo'))
    expect(screen.getByText('No photo was saved for this detection.')).toBeInTheDocument()
    expect(screen.queryAllByTitle(/\d+%$/)).toHaveLength(0)
  })

  it('goes back to the list', async () => {
    const onBack = vi.fn()
    render(<HistoryDetail id={4} onBack={onBack} load={() => Promise.resolve(detail)} imageUrl={imageUrl} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Back to the list' }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })
})