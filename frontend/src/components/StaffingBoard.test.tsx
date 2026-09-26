import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import StaffingBoard from './StaffingBoard'
import start from '../test/fixtures/snapshot_start.json'
import workers from '../test/fixtures/workers.json'
import type { Snapshot, Worker } from '../types'

const s0 = start as unknown as Snapshot
const ws = workers.workers as unknown as Worker[]

test('lists stations with operator and qualification, flagging gaps', () => {
  render(<StaffingBoard stations={s0.stations} zones={s0.zones} workers={ws} onWhatIf={vi.fn()} />)
  const row = screen.getByRole('row', { name: /S12/ })
  expect(within(row).getByText(/no operator/i)).toBeInTheDocument()
  const ok = screen.getByRole('row', { name: /S01/ })
  expect(within(ok).getByText(/qualified|trainer/)).toBeInTheDocument()
})

test('shows absent people and fire warden cover per zone', () => {
  render(<StaffingBoard stations={s0.stations} zones={s0.zones} workers={ws} onWhatIf={vi.fn()} />)
  const absent = ws.filter((w) => w.status === 'absent')
  expect(screen.getByText(new RegExp(`Absent \\(${absent.length}\\)`))).toBeInTheDocument()
  expect(screen.getByText(/zone b: no fire warden/i)).toBeInTheDocument()
})

test('what-if check shows warnings before anyone is moved', async () => {
  const onWhatIf = vi.fn().mockResolvedValue({
    worker: 'W001', worker_name: 'Lena Schmidt', from_station: 'S01', to_station: 'S20', ok: false,
    warnings: ['Lena Schmidt is not qualified on S20 (level 0)'], benefits: [],
  })
  render(<StaffingBoard stations={s0.stations} zones={s0.zones} workers={ws} onWhatIf={onWhatIf} />)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /person/i }), 'W001')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /to station/i }), 'S20')
  await userEvent.click(screen.getByRole('button', { name: /check/i }))
  expect(onWhatIf).toHaveBeenCalledWith('W001', 'S20')
  expect(await screen.findByText(/not qualified on S20/)).toBeInTheDocument()
})
