// Whole-app tests against the mock layer. They cover the user-visible promises:
// the slider chooses the model, answers stream in, and failures are visible and recoverable (I5).
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { mock } = vi.hoisted(() => ({ mock: { api: null } }))

vi.mock('./api/index.js', async () => {
  const { createMock } = await import('./api/mock.js')
  mock.api = createMock({ speed: 40 }) // fast, so tests stay quick
  return { api: mock.api, useMock: true }
})

const { default: App } = await import('./App.jsx')

afterEach(() => {
  cleanup()
  mock.api.restore()
  mock.api.setSpeed(40)
})

const slider = () => screen.getByRole('slider')
const composer = () => screen.getByLabelText('Message')
const ready = () => waitFor(() => expect(slider()).toBeInTheDocument())
async function ask(text) {
  fireEvent.change(composer(), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
}

describe('blend selection', () => {
  it('starts on the 50% blend and shows which model it is', async () => {
    render(<App />)
    await ready()
    expect(slider()).toHaveAttribute('aria-valuetext', '50% code')
    expect(screen.getAllByText('sweep_050 · Q4_K_M · t=50%').length).toBeGreaterThan(0)
    expect(composer()).toHaveAttribute('placeholder', 'Message 50% code')
  })

  it('moves along the slider with the arrow keys, and the chip follows', async () => {
    render(<App />)
    await ready()
    fireEvent.keyDown(slider(), { key: 'ArrowRight' })
    expect(slider()).toHaveAttribute('aria-valuetext', '75% code')
    fireEvent.keyDown(slider(), { key: 'End' })
    expect(slider()).toHaveAttribute('aria-valuetext', 'Code model')
    expect(screen.getAllByText('sweep_100 · Q4_K_M · t=100%').length).toBeGreaterThan(0)
    fireEvent.keyDown(slider(), { key: 'Home' })
    expect(slider()).toHaveAttribute('aria-valuetext', 'Writing model')
  })

  it('selects a layer-wise variant', async () => {
    render(<App />)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Variants & stats' }))
    fireEvent.click(screen.getByRole('button', { name: 'Gradient' }))
    expect(slider()).toHaveAttribute('aria-valuetext', 'Gradient')
    expect(screen.getByRole('button', { name: 'Gradient' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows the measured numbers for the chosen blend', async () => {
    render(<App />)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Variants & stats' }))
    const stats = screen.getByLabelText('Measured results for this blend')
    expect(within(stats).getByText('42%')).toBeInTheDocument() // sweep_050 code pass in the mock metrics
  })
})

describe('blend area', () => {
  it('shows both models, the share of each, and the context window', async () => {
    render(<App />)
    await ready()
    expect(screen.getByText('gemma-1.1-7b-it')).toBeInTheDocument()
    expect(screen.getByText('codegemma-7b-it')).toBeInTheDocument()
    fireEvent.keyDown(slider(), { key: 'End' })
    expect(screen.getByRole('button', { name: /Code model/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText(/Context window: about 0 of 4096/)).toBeInTheDocument()
  })

  it('picks a pure model by clicking its card', async () => {
    render(<App />)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: /Writing model/ }))
    expect(slider()).toHaveAttribute('aria-valuetext', 'Writing model')
  })

  it('counts the conversation against the context window', async () => {
    render(<App />)
    await ready()
    await ask('hello there')
    await waitFor(() => expect(screen.getByLabelText(/Context window: about [1-9]\d* of 4096/)).toBeInTheDocument(), { timeout: 4000 })
  })
})

describe('chatting', () => {
  it('streams an answer for the selected blend and reports the speed', async () => {
    render(<App />)
    await ready()
    fireEvent.keyDown(slider(), { key: 'End' }) // the code model
    await ask('Write is_prime')

    expect(await screen.findByText('Write is_prime')).toBeInTheDocument() // after the empty state animates out
    await waitFor(() => expect(screen.getByText(/tok\/s/, { selector: '.meta' })).toBeInTheDocument(), { timeout: 4000 })
    expect(screen.getByText(/def is_prime/)).toBeInTheDocument()
    expect(composer()).toHaveValue('') // the box clears after sending
  })

  it('sends one prompt to two blends in compare mode', async () => {
    render(<App />)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }))
    await ask('hello')
    await waitFor(() => expect(document.querySelectorAll('.answer-done')).toHaveLength(2), { timeout: 5000 })
  })

  it('can be stopped, keeping what was already written', async () => {
    mock.api.setSpeed(0.5) // slow, so there is something to stop
    render(<App />)
    await ready()
    await ask('long answer please')
    fireEvent.click(await screen.findByRole('button', { name: 'Stop generating' }))
    await waitFor(() => expect(screen.getByText('Stopped')).toBeInTheDocument())
  })
})

describe('failures are visible and recoverable (check I5)', () => {
  it('shows the problem, blocks sending, and lets the user retry after reconnecting', async () => {
    mock.api.setSpeed(0.5) // slow, so there is a stream to interrupt
    render(<App />)
    await ready()
    await ask('hello')
    await waitFor(() => expect(document.querySelector('.answer-streaming')).toBeTruthy(), { timeout: 3000 })

    mock.api.drop() // the server stops mid-stream

    expect(await screen.findByText('Connection lost. Trying to reconnect…')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('The connection dropped while this was generating.')
    expect(composer()).toHaveAttribute('placeholder', 'Waiting for the server…')
    expect(await screen.findByRole('button', { name: 'Send' })).toBeDisabled() // stop button animates out first

    mock.api.restore() // the server is back
    await waitFor(() => expect(composer()).toHaveAttribute('placeholder', 'Message 50% code'))
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    mock.api.setSpeed(40)
    await waitFor(() => expect(document.querySelector('.answer-done')).toBeTruthy(), { timeout: 4000 })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('finder', () => {
  it('runs and offers the recommended blend', async () => {
    render(<App />)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Find best blend' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Fill an example' }))
    const steps = []
    const realFindBest = mock.api.findBest
    mock.api.findBest = (tasks, onProgress, ...rest) => realFindBest(tasks, (p) => { steps.push(p.step); onProgress(p) }, ...rest)
    fireEvent.click(screen.getByRole('button', { name: 'Find the best blend' }))
    expect(await screen.findByText('Recommended', {}, { timeout: 6000 })).toBeInTheDocument()
    expect(steps).toEqual([1, 2, 3, 4, 5, 6, 7, 8]) // progress arrived in order
    mock.api.findBest = realFindBest
    fireEvent.click(screen.getByRole('button', { name: 'Use this blend' }))
    await waitFor(() => expect(slider()).not.toHaveAttribute('aria-valuetext', '50% code'))
  })

  it('asks for missing test lines instead of sending a bad request', async () => {
    render(<App />)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Find best blend' }))
    const finder = await screen.findByRole('button', { name: 'Find the best blend' })
    fireEvent.click(screen.getByRole('button', { name: 'Code' }))
    fireEvent.change(screen.getByLabelText('Prompt for task 1'), { target: { value: 'Write f' } })
    expect(screen.getByText(/add the function name and its test lines/)).toBeInTheDocument()
    expect(finder).toBeDisabled()
  })
})
