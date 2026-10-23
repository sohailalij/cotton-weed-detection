import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import AnalyticsPage from './AnalyticsPage'

vi.mock('./api', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  }
  return { ApiError, api: { statsDaily: vi.fn() } }
})

// Recharts needs real browser measurements, so the tests use stand-ins and check the data.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  BarChart: ({ data, children }: { data: unknown[]; children?: ReactNode }) => (
    <div data-testid="bar-chart" data-rows={data.length}>
      {children}
    </div>
  ),
  LineChart: ({ data, children }: { data: unknown[]; children?: ReactNode }) => (
    <div data-testid="line-chart" data-rows={data.length}>
      {children}
    </div>
  ),
  Bar: ({ dataKey }: { dataKey: string }) => <span data-testid="bar-series">{dataKey}</span>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
}))

type Series = Awaited<ReturnType<typeof api.statsDaily>>

const series: Series = {
  start: null,
  end: null,
  days: [
    {
      day: '2026-10-20',
      detections: 1,
      weeds_found: 2,
      mean_box_coverage: 0.1234,
      counts_by_class: { ragweed: 2 },
    },
    {
      day: '2026-10-21',
      detections: 2,
      weeds_found: 4,
      mean_box_coverage: 0.405,
      counts_by_class: { ragweed: 1, waterhemp: 3 },
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AnalyticsPage', () => {
  it('shows a loading message while waiting', () => {
    render(<AnalyticsPage load={() => new Promise<Series>(() => {})} />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows totals, species and both charts from the daily rows', async () => {
    render(<AnalyticsPage load={() => Promise.resolve(series)} />)
    expect(await screen.findByText('3 detections on 2 days, 6 weeds found')).toBeInTheDocument()
    expect(screen.getByText('ragweed 3, waterhemp 3')).toBeInTheDocument()
    expect(screen.getByTestId('bar-chart')).toHaveAttribute('data-rows', '2')
    expect(screen.getByTestId('line-chart')).toHaveAttribute('data-rows', '2')
    expect(screen.getAllByTestId('bar-series').map((el) => el.textContent)).toEqual([
      'ragweed',
      'waterhemp',
    ])
  })

  it('uses singular words for a single detection', async () => {
    const one: Series = {
      ...series,
      days: [
        {
          day: '2026-10-20',
          detections: 1,
          weeds_found: 1,
          mean_box_coverage: 0.1,
          counts_by_class: { ragweed: 1 },
        },
      ],
    }
    render(<AnalyticsPage load={() => Promise.resolve(one)} />)
    expect(await screen.findByText('1 detection on 1 day, 1 weed found')).toBeInTheDocument()
  })

  it('says so when there is no history', async () => {
    render(<AnalyticsPage load={() => Promise.resolve({ ...series, days: [] })} />)
    expect(await screen.findByText(/No detections yet/)).toBeInTheDocument()
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument()
  })

  it('shows the message from an API error', async () => {
    render(<AnalyticsPage load={() => Promise.reject(new ApiError(503, 'database unavailable'))} />)
    expect(await screen.findByText('database unavailable')).toBeInTheDocument()
  })

  it('explains a network failure without leaking details', async () => {
    render(<AnalyticsPage load={() => Promise.reject(new Error('boom'))} />)
    expect(await screen.findByText('Could not reach the server')).toBeInTheDocument()
  })

  it('loads once with the default API and does not refetch in a loop', async () => {
    vi.mocked(api.statsDaily).mockResolvedValue(series)
    render(<AnalyticsPage />)
    await screen.findByText('3 detections on 2 days, 6 weeds found')
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(api.statsDaily).toHaveBeenCalledTimes(1)
  })
})