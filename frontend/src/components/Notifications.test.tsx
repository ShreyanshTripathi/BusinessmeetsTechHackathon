import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import Notifications from './Notifications'
import Escalations from './Escalations'
import emergency from '../test/fixtures/snapshot_emergency.json'
import type { Snapshot } from '../types'

const se = emergency as unknown as Snapshot

test('shows unacknowledged count and puts critical first', () => {
  render(<Notifications notifications={se.notifications} onAck={vi.fn()} />)
  const unacked = se.notifications.filter((n) => !n.acknowledged).length
  expect(screen.getByText(new RegExp(`${unacked} new`))).toBeInTheDocument()
  const items = screen.getAllByRole('listitem')
  expect(items[0]).toHaveAttribute('data-level', 'critical')
})

test('acknowledge calls back with the notification id', async () => {
  const onAck = vi.fn()
  render(<Notifications notifications={se.notifications} onAck={onAck} />)
  const first = screen.getAllByRole('listitem')[0]
  await userEvent.click(within(first).getByRole('button', { name: /acknowledge/i }))
  expect(onAck).toHaveBeenCalledWith(expect.stringMatching(/^ntf_/))
})

test('escalations show who has not confirmed and allow marking confirmed', async () => {
  const onAck = vi.fn()
  render(<Escalations escalations={se.escalations} now={se.clock} onAck={onAck} />)
  const esc = se.escalations.find((e) => !e.acknowledged_at)!
  const item = screen.getByRole('listitem', { name: new RegExp(esc.team) })
  expect(within(item).getByText(/waiting/i)).toBeInTheDocument()
  await userEvent.click(within(item).getByRole('button', { name: /confirmed/i }))
  expect(onAck).toHaveBeenCalledWith(esc.id)
})
