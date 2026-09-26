import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import PriorityInbox from './PriorityInbox'
import start from '../test/fixtures/snapshot_start.json'
import emergency from '../test/fixtures/snapshot_emergency.json'
import type { Snapshot } from '../types'

const s0 = start as unknown as Snapshot
const se = emergency as unknown as Snapshot

function renderInbox(snap: Snapshot, onDecision = vi.fn()) {
  render(
    <PriorityInbox
      active={snap.incidents.active}
      held={snap.incidents.held}
      inProgress={snap.incidents.in_progress}
      attention={snap.attention}
      onDecision={onDecision}
    />,
  )
  return onDecision
}

test('shows each active incident with its recommendation and the people to send', () => {
  renderInbox(s0)
  const card = screen.getByRole('article', { name: /S12 has no operator/ })
  expect(within(card).getByText(/Cover S12/)).toBeInTheDocument()
  const who = s0.incidents.active.find((i) => i.title.includes('S12'))!.recommendation!.assignments[0].worker_name
  expect(within(card).getAllByText(new RegExp(who)).length).toBeGreaterThan(0)
  expect(within(card).getByText('Staffing')).toBeInTheDocument()
})

test('accept sends the decision for that incident', async () => {
  const onDecision = renderInbox(s0)
  const card = screen.getByRole('article', { name: /S12 has no operator/ })
  await userEvent.click(within(card).getByRole('button', { name: /accept/i }))
  const id = s0.incidents.active.find((i) => i.title.includes('S12'))!.id
  expect(onDecision).toHaveBeenCalledWith(id, 'accept', '', undefined)
})

test('dismiss asks for a reason before sending', async () => {
  const onDecision = renderInbox(s0)
  const card = screen.getByRole('article', { name: /No fire warden in zone B/ })
  await userEvent.click(within(card).getByRole('button', { name: /dismiss/i }))
  const send = within(card).getByRole('button', { name: /confirm dismiss/i })
  expect(send).toBeDisabled()
  await userEvent.type(within(card).getByLabelText(/reason/i), 'warden arriving at 07:00')
  await userEvent.click(send)
  const id = s0.incidents.active.find((i) => i.title.includes('fire warden'))!.id
  expect(onDecision).toHaveBeenCalledWith(id, 'dismiss', 'warden arriving at 07:00', undefined)
})

test('change lets the supervisor drop an assignment and send the rest with a reason', async () => {
  const onDecision = renderInbox(s0)
  const card = screen.getByRole('article', { name: /No fire warden in zone B/ })
  const inc = s0.incidents.active.find((i) => i.title.includes('fire warden'))!
  const [first, second] = inc.recommendation!.assignments
  await userEvent.click(within(card).getByRole('button', { name: /change/i }))
  await userEvent.click(within(card).getByRole('checkbox', { name: new RegExp(second.worker_name) }))
  await userEvent.type(within(card).getByLabelText(/reason/i), 'backfill myself')
  await userEvent.click(within(card).getByRole('button', { name: /send change/i }))
  expect(onDecision).toHaveBeenCalledWith(inc.id, 'modify', 'backfill myself', [
    { worker: first.worker, to_station: first.to_station, to_zone: first.to_zone, kind: first.kind, task: first.task },
  ])
})

test('safety-rule incidents cannot be dismissed and show the rule', () => {
  renderInbox(se)
  const card = screen.getByRole('article', { name: /Fire confirmed in zone C/ })
  expect(within(card).getByText(/safety rule · cannot be dismissed/i)).toBeInTheDocument()
  expect(within(card).getByRole('button', { name: /dismiss/i })).toBeDisabled()
  expect(within(card).getByText('EMERGENCY')).toBeInTheDocument()
})

test('shows the merged insight when several agents contributed', () => {
  renderInbox(se)
  const card = screen.getByRole('article', { name: /Repeated defects at S09/ })
  expect(within(card).getByText(/likely method\/training/)).toBeInTheDocument()
  expect(within(card).getByText('Staffing')).toBeInTheDocument()
  expect(within(card).getByText('Assembly')).toBeInTheDocument()
})

test('shows how much was held back', () => {
  renderInbox(s0)
  expect(screen.getByText(new RegExp(`${s0.attention.signals}\\s+signals`))).toBeInTheDocument()
})

test('empty inbox says nothing needs attention', () => {
  render(<PriorityInbox active={[]} held={[]} inProgress={[]} attention={s0.attention} onDecision={vi.fn()} />)
  expect(screen.getByText(/nothing needs you/i)).toBeInTheDocument()
})
