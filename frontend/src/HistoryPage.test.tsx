import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import HistoryPage from './HistoryPage'

vi.mock('./api', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  }
  return {
    ApiError,
    api: { detections: vi.fn(), remove: vi.fn(), imageUrl: (id: number) => `/img/${id}` },
  }
})

type Page = Awaited<ReturnType<typeof api.detections>>
type Item = Page['items'][number]

const item = (id: number, count: number, counts: Record<string, number>): Item => ({
  id,
  created_at: '2026-10-21T09:54:54Z',
  model_name: 'yolo11s_v1_960',
  image_width: 1024,
  image_height: 768,
  conf_used: 0.58,
  count,
  box_coverage: 0.25,
  counts_by_class: counts,
})

const pageOf = (items: Item[], total: number, offset = 0): Page => ({
  items,
  total,
  limit: 12,
  offset,
})

const imageUrl = (id: number) => `/img/${id}`
const one = () => pageOf([item(1, 1, { ragweed: 1 })], 1)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('HistoryPage', () => {
  it('lists saved detections with species, counts and coverage', async () => {
    const list = vi.fn(() =>
      Promise.resolve(
        pageOf([item(2, 5, { waterhemp: 3, ragweed: 2 }), item(1, 1, { morning_glory: 1 })], 2),
      ),
    )
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    expect(await screen.findByText('Showing 1 to 2 of 2')).toBeInTheDocument()
    expect(screen.getByText('5 weeds: waterhemp 3, ragweed 2')).toBeInTheDocument()
    expect(screen.getByText('1 weed: morning glory 1')).toBeInTheDocument()
    expect(screen.getAllByText(/Cutoff 0\.58, boxes cover 25% of the photo/)).toHaveLength(2)
    expect(screen.getAllByAltText('Saved photo')).toHaveLength(2)
    expect(list).toHaveBeenCalledWith(12, 0)
  })

  it('shows a loading message while waiting', () => {
    const list = vi.fn(() => new Promise<Page>(() => {}))
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('says so when there is nothing saved', async () => {
    const list = vi.fn(() => Promise.resolve(pageOf([], 0)))
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    expect(await screen.findByText('No saved detections yet.')).toBeInTheDocument()
  })

  it('shows the message from an API error', async () => {
    const list = vi.fn(() => Promise.reject(new ApiError(503, 'database unavailable')))
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    expect(await screen.findByText('database unavailable')).toBeInTheDocument()
  })

  it('explains a network failure without leaking details', async () => {
    const list = vi.fn(() => Promise.reject(new Error('boom')))
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    expect(await screen.findByText('Could not reach the server')).toBeInTheDocument()
  })

  it('pages forward and back', async () => {
    const list = vi.fn((_limit: number, offset: number) =>
      Promise.resolve(pageOf([item(offset + 1, 1, { ragweed: 1 })], 30, offset)),
    )
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    expect(await screen.findByText('Showing 1 to 12 of 30')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Showing 13 to 24 of 30')).toBeInTheDocument()
    expect(list).toHaveBeenLastCalledWith(12, 12)
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Showing 25 to 30 of 30')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    expect(await screen.findByText('Showing 13 to 24 of 30')).toBeInTheDocument()
  })

  it('asks for confirmation, then deletes and reloads', async () => {
    const list = vi
      .fn()
      .mockResolvedValueOnce(one())
      .mockResolvedValueOnce(pageOf([], 0))
    const remove = vi.fn(() => Promise.resolve())
    render(<HistoryPage list={list} remove={remove} imageUrl={imageUrl} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Delete detection 1' }))
    expect(remove).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1))
    expect(await screen.findByText('No saved detections yet.')).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('does not delete when cancelled', async () => {
    const list = vi.fn(() => Promise.resolve(one()))
    const remove = vi.fn(() => Promise.resolve())
    render(<HistoryPage list={list} remove={remove} imageUrl={imageUrl} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Delete detection 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Delete detection 1' })).toBeInTheDocument()
  })

  it('keeps the row and shows the error when a delete fails', async () => {
    const list = vi.fn(() => Promise.resolve(one()))
    const remove = vi.fn(() => Promise.reject(new ApiError(500, 'could not delete')))
    render(<HistoryPage list={list} remove={remove} imageUrl={imageUrl} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Delete detection 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))
    expect(await screen.findByText('could not delete')).toBeInTheDocument()
    expect(screen.getByText('Showing 1 to 1 of 1')).toBeInTheDocument()
  })

  it('steps back a page when the last row of the last page is deleted', async () => {
    let rows = 13
    const list = vi.fn((limit: number, offset: number) => {
      const ids = Array.from({ length: rows }, (_, i) => rows - i)
      const items = ids.slice(offset, offset + limit).map((id) => item(id, 1, { ragweed: 1 }))
      return Promise.resolve(pageOf(items, rows, offset))
    })
    const remove = vi.fn(() => {
      rows -= 1
      return Promise.resolve()
    })
    render(<HistoryPage list={list} remove={remove} imageUrl={imageUrl} />)
    expect(await screen.findByText('Showing 1 to 12 of 13')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Showing 13 to 13 of 13')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete detection 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))
    expect(await screen.findByText('Showing 1 to 12 of 12')).toBeInTheDocument()
  })

  it('shows a placeholder when a photo cannot be loaded', async () => {
    const list = vi.fn(() => Promise.resolve(one()))
    render(<HistoryPage list={list} remove={vi.fn()} imageUrl={imageUrl} />)
    fireEvent.error(await screen.findByAltText('Saved photo'))
    expect(screen.getByRole('img', { name: 'No photo saved' })).toBeInTheDocument()
  })

  it('loads once with the default API and does not refetch in a loop', async () => {
    vi.mocked(api.detections).mockResolvedValue(one())
    render(<HistoryPage />)
    await screen.findByText('Showing 1 to 1 of 1')
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(api.detections).toHaveBeenCalledTimes(1)
  })
})