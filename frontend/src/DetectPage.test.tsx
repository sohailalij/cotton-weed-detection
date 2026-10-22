import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './api'
import DetectPage from './DetectPage'

const result = {
  id: 1,
  image_width: 200,
  image_height: 100,
  conf_used: 0.15,
  count: 3,
  counts_by_class: { waterhemp: 1, ragweed: 2 },
  box_coverage: 0.2,
  detections: [
    { box: { x1: 0, y1: 0, x2: 100, y2: 50 }, confidence: 0.9, class_id: 0, class_name: 'waterhemp' },
    { box: { x1: 100, y1: 50, x2: 200, y2: 100 }, confidence: 0.7, class_id: 5, class_name: 'ragweed' },
    { box: { x1: 20, y1: 20, x2: 40, y2: 40 }, confidence: 0.3, class_id: 5, class_name: 'ragweed' },
  ],
}

const photo = new File(['x'], 'field.jpg', { type: 'image/jpeg' })

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})

function choosePhoto() {
  fireEvent.change(screen.getByLabelText(/Photo/), { target: { files: [photo] } })
}

function clickFind() {
  fireEvent.click(screen.getByRole('button', { name: 'Find weeds' }))
}

describe('DetectPage', () => {
  it('needs a photo before it can detect', () => {
    render(<DetectPage />)
    expect(screen.getByRole('button', { name: 'Find weeds' })).toBeDisabled()
    expect(screen.queryByLabelText('Confidence cutoff')).not.toBeInTheDocument()
  })

  it('asks the API at a low cutoff and shows boxes above the default cutoff', async () => {
    const detect = vi.fn(() => Promise.resolve(result))
    render(<DetectPage detect={detect} />)
    choosePhoto()
    clickFind()
    await screen.findByText(/detections, covering/)
    expect(detect).toHaveBeenCalledWith(photo, 0.15)
    expect(screen.getAllByTitle(/\d+%$/)).toHaveLength(2)
    expect(screen.getByText(/2 detections, covering 50.0% of the photo/)).toBeInTheDocument()
    expect(screen.getByText(/waterhemp: 1/)).toBeInTheDocument()
    expect(screen.getByText(/ragweed: 1/)).toBeInTheDocument()
  })

  it('shows and hides boxes as the slider moves', async () => {
    render(<DetectPage detect={() => Promise.resolve(result)} />)
    choosePhoto()
    clickFind()
    await screen.findByText(/detections, covering/)
    const slider = screen.getByLabelText('Confidence cutoff')
    fireEvent.change(slider, { target: { value: '0.2' } })
    expect(screen.getAllByTitle(/\d+%$/)).toHaveLength(3)
    fireEvent.change(slider, { target: { value: '0.8' } })
    expect(screen.getAllByTitle(/\d+%$/)).toHaveLength(1)
    fireEvent.change(slider, { target: { value: '0.95' } })
    expect(screen.getByText('No weeds found at this cutoff.')).toBeInTheDocument()
  })

  it('shows the loading state while waiting', async () => {
    let release: (value: typeof result) => void = () => {}
    const pending = new Promise<typeof result>((resolve) => {
      release = resolve
    })
    render(<DetectPage detect={() => pending} />)
    choosePhoto()
    clickFind()
    expect(await screen.findByRole('button', { name: 'Detecting…' })).toBeDisabled()
    release(result)
    await screen.findByText(/detections, covering/)
  })

  it('shows the message from an API error', async () => {
    const detect = () => Promise.reject(new ApiError(400, 'file is not a readable image'))
    render(<DetectPage detect={detect} />)
    choosePhoto()
    clickFind()
    expect(await screen.findByRole('alert')).toHaveTextContent('file is not a readable image')
  })

  it('explains a network failure without leaking details', async () => {
    render(<DetectPage detect={() => Promise.reject(new Error('boom'))} />)
    choosePhoto()
    clickFind()
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
  })

  it('says so when nothing is found', async () => {
    render(<DetectPage detect={() => Promise.resolve({ ...result, detections: [], count: 0 })} />)
    choosePhoto()
    clickFind()
    expect(await screen.findByText('No weeds found at this cutoff.')).toBeInTheDocument()
  })
})