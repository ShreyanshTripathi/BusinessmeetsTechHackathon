import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import ChatPanel from './ChatPanel'

const proposal = {
  id: 'prp_0001', kind: 'assign' as const, description: 'Move Lena Schmidt to S12', params: {}, status: 'pending' as const,
}

test('sends the question and shows the answer', async () => {
  const onSend = vi.fn().mockResolvedValue({ reply: 'Zone B has 8 people.', proposals: [], mode: 'offline' })
  render(<ChatPanel mode="offline" onSend={onSend} onConfirm={vi.fn()} onReject={vi.fn()} />)
  await userEvent.type(screen.getByRole('textbox', { name: /ask/i }), 'How is zone B?{Enter}')
  expect(onSend).toHaveBeenCalledWith('How is zone B?', [], 'en')
  expect(await screen.findByText('Zone B has 8 people.')).toBeInTheDocument()
})

test('passes conversation history and the chosen language', async () => {
  const onSend = vi.fn().mockResolvedValue({ reply: 'ok', proposals: [], mode: 'claude' })
  render(<ChatPanel mode="claude" onSend={onSend} onConfirm={vi.fn()} onReject={vi.fn()} />)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /language/i }), 'de')
  await userEvent.type(screen.getByRole('textbox', { name: /ask/i }), 'first{Enter}')
  await screen.findByText('ok')
  await userEvent.type(screen.getByRole('textbox', { name: /ask/i }), 'second{Enter}')
  expect(onSend).toHaveBeenLastCalledWith(
    'second',
    [{ role: 'user', content: 'first' }, { role: 'assistant', content: 'ok' }],
    'de',
  )
})

test('proposed actions need confirmation', async () => {
  const onSend = vi.fn().mockResolvedValue({ reply: 'I proposed a move.', proposals: [proposal], mode: 'claude' })
  const onConfirm = vi.fn().mockResolvedValue({ applied: ['Lena Schmidt → S12'] })
  render(<ChatPanel mode="claude" onSend={onSend} onConfirm={onConfirm} onReject={vi.fn()} />)
  await userEvent.type(screen.getByRole('textbox', { name: /ask/i }), 'cover S12{Enter}')
  expect(await screen.findByText('Move Lena Schmidt to S12')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
  expect(onConfirm).toHaveBeenCalledWith('prp_0001')
  expect(await screen.findByText(/Lena Schmidt → S12/)).toBeInTheDocument()
})

test('suggestion chips ask common questions', async () => {
  const onSend = vi.fn().mockResolvedValue({ reply: 'ok', proposals: [], mode: 'offline' })
  render(<ChatPanel mode="offline" onSend={onSend} onConfirm={vi.fn()} onReject={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: /summarise the shift/i }))
  expect(onSend).toHaveBeenCalledWith(expect.stringMatching(/summar/i), [], 'en')
})

test('shows which mode answers', () => {
  render(<ChatPanel mode="offline" onSend={vi.fn()} onConfirm={vi.fn()} onReject={vi.fn()} />)
  expect(screen.getByText(/offline/i)).toBeInTheDocument()
})

test('hides the microphone when the browser has no speech recognition', () => {
  render(<ChatPanel mode="offline" onSend={vi.fn()} onConfirm={vi.fn()} onReject={vi.fn()} />)
  expect(screen.queryByRole('button', { name: /speak/i })).not.toBeInTheDocument()
})
