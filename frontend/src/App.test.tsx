import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import start from './test/fixtures/snapshot_start.json'
import emergency from './test/fixtures/snapshot_emergency.json'
import workers from './test/fixtures/workers.json'
import oversight from './test/fixtures/oversight.json'

const snap = { current: start as unknown }

vi.mock('./useSnapshot', () => ({
  useSnapshot: () => ({ snapshot: snap.current, connected: true, refresh: vi.fn() }),
}))

vi.mock('./api', () => ({
  api: {
    decide: vi.fn().mockResolvedValue({}),
    ackNotification: vi.fn(),
    ackEscalation: vi.fn(),
    chat: vi.fn().mockResolvedValue({ reply: 'hi', proposals: [], mode: 'offline' }),
    confirmProposal: vi.fn(),
    rejectProposal: vi.fn(),
    handover: vi.fn(),
    whatIf: vi.fn(),
    oversight: vi.fn().mockResolvedValue(oversight),
    workers: vi.fn().mockResolvedValue(workers),
    sim: vi.fn(),
    checkin: vi.fn(),
    allClear: vi.fn(),
  },
}))

import App from './App'
import { api } from './api'

const SECTIONS = ['Now', 'Line', 'People', 'Safety', 'Alerts', 'Copilot', 'Oversight', 'Handover']

function nav() {
  return screen.getByRole('navigation', { name: /sections/i })
}

test('sidebar lists every section and opens on Now', () => {
  snap.current = start
  render(<App />)
  for (const name of SECTIONS) {
    expect(within(nav()).getByRole('button', { name: new RegExp(`^${name}`) })).toBeInTheDocument()
  }
  expect(within(nav()).getByRole('button', { name: /^Now/ })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('heading', { level: 1, name: 'Decisions waiting for you' })).toBeInTheDocument()
})

test('Now shows only the decisions, not the map or the chat', () => {
  snap.current = start
  render(<App />)
  expect(screen.getByRole('article', { name: /S12 has no operator/ })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: /zone a/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: /ask/i })).not.toBeInTheDocument()
})

test('Now badge shows how many decisions are waiting', () => {
  snap.current = start
  render(<App />)
  const now = within(nav()).getByRole('button', { name: /^Now/ })
  expect(now).toHaveTextContent(String((start as { incidents: { active: unknown[] } }).incidents.active.length))
})

test('accepting from Now calls the API', async () => {
  snap.current = start
  render(<App />)
  await userEvent.click(screen.getAllByRole('button', { name: /accept/i })[0])
  expect(api.decide).toHaveBeenCalled()
})

test('each section shows its own content', async () => {
  snap.current = start
  render(<App />)
  await userEvent.click(within(nav()).getByRole('button', { name: /^Line/ }))
  expect(screen.getByRole('region', { name: /zone a/i })).toBeInTheDocument()
  await userEvent.click(within(nav()).getByRole('button', { name: /^People/ }))
  expect(await screen.findByRole('row', { name: /S12/ })).toBeInTheDocument()
  await userEvent.click(within(nav()).getByRole('button', { name: /^Safety/ }))
  expect(screen.getByRole('heading', { level: 1, name: /safety/i })).toBeInTheDocument()
  await userEvent.click(within(nav()).getByRole('button', { name: /^Alerts/ }))
  expect(screen.getByText(/calls waiting/i)).toBeInTheDocument()
  await userEvent.click(within(nav()).getByRole('button', { name: /^Copilot/ }))
  expect(screen.getByRole('textbox', { name: /ask/i })).toBeInTheDocument()
  await userEvent.click(within(nav()).getByRole('button', { name: /^Oversight/ }))
  expect(await screen.findByText(/decisions by humans/i)).toBeInTheDocument()
})

test('emergency takes over Now and shows a banner in other sections', async () => {
  snap.current = emergency
  render(<App />)
  expect(screen.getByRole('heading', { name: /emergency.*zone c/i })).toBeInTheDocument()
  await userEvent.click(within(nav()).getByRole('button', { name: /^Line/ }))
  expect(screen.getByRole('alert')).toHaveTextContent(/emergency in zone c/i)
})
