import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('shows the page heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Weed detection' })).toBeInTheDocument()
  })

  it('opens on the Detect tab with a switcher to History', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Detect' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'History' })).not.toHaveAttribute('aria-current')
  })
})