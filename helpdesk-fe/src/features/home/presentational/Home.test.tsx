import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../../test/render'
import { Home } from './Home'

describe('Home', () => {
  it('API に接続できたときは「接続OK」を表示する', () => {
    renderWithProviders(<Home apiStatus="ok" />)

    expect(screen.getByText('接続OK')).toBeInTheDocument()
  })

  it('API に接続できないときは「接続できません」を表示する', () => {
    renderWithProviders(<Home apiStatus="error" />)

    expect(screen.getByText('接続できません')).toBeInTheDocument()
  })
})
