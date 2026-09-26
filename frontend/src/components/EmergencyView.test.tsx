import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import EmergencyView from './EmergencyView'
import emergency from '../test/fixtures/snapshot_emergency.json'
import type { Snapshot } from '../types'

const se = emergency as unknown as Snapshot
const em = se.emergency!

test('takes over with zone, people count, exits and wardens', () => {
  render(<EmergencyView emergency={em} zones={se.zones} onCheckin={vi.fn()} onAllClear={vi.fn()} />)
  expect(screen.getByRole('heading', { name: /emergency.*zone c/i })).toBeInTheDocument()
  expect(screen.getByText(new RegExp(`0\\s*/\\s*${em.people.length}`))).toBeInTheDocument()
  expect(screen.getByText(new RegExp(em.exits[0]))).toBeInTheDocument()
  expect(screen.getByText(`Assembly point ${em.assembly_point}`)).toBeInTheDocument()
})

test('tapping a person checks them in at the assembly point', async () => {
  const onCheckin = vi.fn()
  render(<EmergencyView emergency={em} zones={se.zones} onCheckin={onCheckin} onAllClear={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: new RegExp(em.people[0].name) }))
  expect(onCheckin).toHaveBeenCalledWith(em.people[0].id)
})

test('all clear needs a second tap and then shows the restart plan', async () => {
  const onAllClear = vi.fn().mockResolvedValue({
    zone: 'C', duration_min: 11, cars_to_recover: 11, steps: ['Restart zone C first', 'Recover 11 cars'],
  })
  render(<EmergencyView emergency={em} zones={se.zones} onCheckin={vi.fn()} onAllClear={onAllClear} />)
  await userEvent.click(screen.getByRole('button', { name: /all clear/i }))
  expect(onAllClear).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: /confirm all clear/i }))
  expect(onAllClear).toHaveBeenCalled()
  expect(await screen.findByText('Restart zone C first')).toBeInTheDocument()
})
