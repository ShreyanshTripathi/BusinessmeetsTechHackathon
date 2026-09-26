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

import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import nearmiss from '../test/fixtures/snapshot_nearmiss.json'

const sn = nearmiss as unknown as Snapshot
const reports = [...sn.incidents.active, ...sn.incidents.held, ...sn.incidents.in_progress]
  .filter((i) => i.predictions.some((p) => p.model === 'safety_model'))

test('near-miss form sends the report to the safety model', async () => {
  const onReport = vi.fn().mockResolvedValue(reports[0])
  render(<SafetyView zones={s0.zones} emergencyZone={null} reports={[]} onReport={onReport} />)
  await userEvent.type(screen.getByRole('textbox', { name: /what happened/i }), 'Pallet fell off the rack near S17')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /zone/i }), 'C')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /station/i }), 'S17')
  await userEvent.click(screen.getByRole('button', { name: /send report/i }))
  expect(onReport).toHaveBeenCalledWith('Pallet fell off the rack near S17', 'C', 'S17')
  expect(await screen.findByText(/report sent/i)).toBeInTheDocument()
})

test('rated reports are listed with the model explanation', () => {
  render(<SafetyView zones={sn.zones} emergencyZone={null} reports={reports} onReport={vi.fn()} />)
  const list = screen.getByRole('list', { name: /near-miss reports/i })
  expect(within(list).getByText(reports[0].title)).toBeInTheDocument()
  expect(list).toHaveTextContent(reports[0].predictions[0].explanation.slice(0, 30))
})
