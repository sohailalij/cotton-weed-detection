import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'

vi.mock('./AnalyticsPage', () => ({ default: () => <p>Analytics page</p> }))

describe('App', () => {
  it('shows the page heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Weed detection' })).toBeInTheDocument()
  })

  it('opens on the Detect tab with a switcher to the other pages', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Detect' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'History' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('button', { name: 'Analytics' })).not.toHaveAttribute('aria-current')
  })

  it('loads the Analytics page only when its tab is opened', async () => {
    render(<App />)
    expect(screen.queryByText('Analytics page')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Analytics' }))
    expect(await screen.findByText('Analytics page')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analytics' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })
})