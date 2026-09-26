import { render, screen, within } from '@testing-library/react'
import SafetyView from './SafetyView'
import start from '../test/fixtures/snapshot_start.json'
import emergency from '../test/fixtures/snapshot_emergency.json'
import type { Snapshot } from '../types'

const s0 = start as unknown as Snapshot
const se = emergency as unknown as Snapshot

test('one card per zone with people, wardens and exits', () => {
  render(<SafetyView zones={s0.zones} emergencyZone={null} />)
  expect(screen.getAllByRole('region')).toHaveLength(4)
  const b = screen.getByRole('region', { name: /zone b/i })
  expect(within(b).getByText(/no fire warden/i)).toBeInTheDocument()
  const a = screen.getByRole('region', { name: /zone a/i })
  expect(within(a).getByText(s0.zones[0].exits.join(' · '))).toBeInTheDocument()
})

test('sensor readings over the warning level are flagged', () => {
  render(<SafetyView zones={se.zones} emergencyZone="C" />)
  const c = screen.getByRole('region', { name: /zone c/i })
  expect(c).toHaveAttribute('data-emergency', 'true')
  expect(within(c).getByText(/smoke/i).closest('[data-state]')).toHaveAttribute('data-state', 'warning')
  const a = screen.getByRole('region', { name: /zone a/i })
  expect(within(a).getByText(/smoke/i).closest('[data-state]')).toHaveAttribute('data-state', 'normal')
})
