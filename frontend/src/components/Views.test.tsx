import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import OversightView from './OversightView'
import HandoverView from './HandoverView'
import TopBar from './TopBar'
import oversight from '../test/fixtures/oversight.json'
import models from '../test/fixtures/models.json'
import start from '../test/fixtures/snapshot_start.json'
import type { ModelCard, Oversight, Snapshot } from '../types'

const ov = oversight as unknown as Oversight
const s0 = start as unknown as Snapshot

test('oversight shows decisions, override rate and the works council commitments', () => {
  render(<OversightView data={ov} models={[]} />)
  expect(screen.getByText(/decisions by humans/i)).toBeInTheDocument()
  expect(screen.getByText(`${Math.round(ov.override_rate * 100)}%`)).toBeInTheDocument()
  expect(screen.getByText(/no individual performance scoring/i)).toBeInTheDocument()
  expect(screen.getAllByRole('row').length).toBeGreaterThan(ov.log.length)
})

test('handover generates text in the chosen language', async () => {
  const onGenerate = vi.fn().mockResolvedValue({ text: 'Shift handover: all good', mode: 'offline' })
  render(<HandoverView onGenerate={onGenerate} />)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /language/i }), 'pl')
  await userEvent.click(screen.getByRole('button', { name: /generate/i }))
  expect(onGenerate).toHaveBeenCalledWith('pl')
  expect(await screen.findByDisplayValue('Shift handover: all good')).toBeInTheDocument()
})

test('top bar shows clock and output, and controls the simulation', async () => {
  const onSim = vi.fn()
  render(<TopBar snapshot={s0} onSim={onSim} />)
  expect(screen.getByText('06:02')).toBeInTheDocument()
  expect(screen.getByText(new RegExp(`${s0.kpis.cars_built}\\s*/\\s*${s0.kpis.plan}`))).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /play/i }))
  expect(onSim).toHaveBeenCalledWith({ action: 'start' })
  await userEvent.click(screen.getByRole('button', { name: /\+15 min/i }))
  expect(onSim).toHaveBeenCalledWith({ action: 'step', minutes: 15 })
})

test('oversight shows each model card with its result and limits', () => {
  const cards = models.models as unknown as ModelCard[]
  render(<OversightView data={ov} models={cards} />)
  const panel = screen.getByRole('list', { name: /models/i })
  expect(within(panel).getAllByRole('listitem')).toHaveLength(3)
  expect(panel).toHaveTextContent(/random forest/i)
  expect(panel).toHaveTextContent(cards[0].limits.slice(0, 30))
})
