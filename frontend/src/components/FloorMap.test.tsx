import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import FloorMap from './FloorMap'
import start from '../test/fixtures/snapshot_start.json'
import emergency from '../test/fixtures/snapshot_emergency.json'
import type { Snapshot } from '../types'

const s0 = start as unknown as Snapshot
const se = emergency as unknown as Snapshot

test('draws every station with its status', () => {
  render(<FloorMap zones={s0.zones} stations={s0.stations} emergencyZone={null} selected={null} onSelect={vi.fn()} />)
  expect(screen.getAllByRole('button', { name: /^S\d{2}/ })).toHaveLength(24)
  expect(screen.getByRole('button', { name: /S12.*no operator/i })).toBeInTheDocument()
})

test('clicking a station selects it', async () => {
  const onSelect = vi.fn()
  render(<FloorMap zones={s0.zones} stations={s0.stations} emergencyZone={null} selected={null} onSelect={onSelect} />)
  await userEvent.click(screen.getByRole('button', { name: /^S05/ }))
  expect(onSelect).toHaveBeenCalledWith('S05')
})

test('shows people per zone and marks the emergency zone', () => {
  render(<FloorMap zones={se.zones} stations={se.stations} emergencyZone="C" selected={null} onSelect={vi.fn()} />)
  const zoneC = screen.getByRole('region', { name: /zone c/i })
  expect(zoneC).toHaveAttribute('data-emergency', 'true')
  expect(zoneC).toHaveTextContent(`${se.zones[2].people} people`)
})
