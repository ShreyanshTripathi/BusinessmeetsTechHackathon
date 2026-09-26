import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import ForecastList from './ForecastList'
import forecast from '../test/fixtures/snapshot_forecast.json'
import type { Snapshot } from '../types'

const sf = forecast as unknown as Snapshot
const withModel = sf.incidents.held.filter((i) => i.predictions.length)

test('lists held model forecasts with risk and explanation', () => {
  render(<ForecastList incidents={sf.incidents.held} onDecision={vi.fn()} />)
  const list = screen.getByRole('list', { name: /model forecasts/i })
  expect(within(list).getAllByRole('listitem')).toHaveLength(withModel.length)
  const first = withModel[0]
  const item = within(list).getByRole('listitem', { name: new RegExp(first.title) })
  expect(item).toHaveTextContent(`${Math.round(first.predictions[0].risk * 100)}%`)
})

test('a forecast can be acted on', async () => {
  const onDecision = vi.fn()
  render(<ForecastList incidents={sf.incidents.held} onDecision={onDecision} />)
  const item = screen.getByRole('listitem', { name: new RegExp(withModel[0].title) })
  await userEvent.click(within(item).getByRole('button', { name: /act on it/i }))
  expect(onDecision).toHaveBeenCalledWith(withModel[0].id, 'accept', '', undefined)
})

test('renders nothing when there are no forecasts', () => {
  const { container } = render(<ForecastList incidents={[]} onDecision={vi.fn()} />)
  expect(container).toBeEmptyDOMElement()
})
