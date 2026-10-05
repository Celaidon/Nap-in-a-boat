import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { useState } from 'react'
import { api, useMock } from './api/index.js'
import { describeBlend, findBlend } from './lib/blends.js'
import { useChat } from './state/useChat.js'
import { Banner } from './components/Banner.jsx'
import { BlendDock } from './components/BlendDock.jsx'
import { Chat } from './components/Chat.jsx'
import { Composer } from './components/Composer.jsx'
import { CurvePanel } from './components/CurvePanel.jsx'
import { FinderPanel } from './components/FinderPanel.jsx'
import { TopBar } from './components/TopBar.jsx'

const TITLES = { curve: 'Capability curve', finder: 'Find the best blend' }

export default function App() {
  const chat = useChat(api)
  const { state, status } = chat
  const [panel, setPanel] = useState(null) // null | 'curve' | 'finder'
  const ready = Boolean(state.blendId) && status === 'online'
  const current = findBlend(state.blends, state.blendId)

  const placeholder = !state.blendId
    ? 'Loading blends…'
    : status !== 'online'
      ? 'Waiting for the server…'
      : `Message ${describeBlend(current).toLowerCase()}`

  return (
    <MotionConfig reducedMotion="user">
      <div className="app">
        <TopBar status={status} mock={useMock} panel={panel} onPanel={setPanel} onNewChat={chat.clear} canClear={state.turns.length > 0 && !chat.streaming} />
        <Banner status={status} />

        <div className="body">
          <main className="stage">
            {state.loadError ? (
              <div className="fatal" role="alert">
                <h1 className="display">Could not load the blends</h1>
                <p>{state.loadError}</p>
                <button className="primary" onClick={() => location.reload()}>Reload</button>
              </div>
            ) : (
              <>
                <Chat turns={state.turns} blends={state.blends} ready={ready} onSend={chat.send} onRetry={chat.retry} />
                <div className="foot">
                  <BlendDock
                    blends={state.blends} blendId={state.blendId} compareId={state.compareId} metrics={state.metrics}
                    onSelect={chat.selectBlend} onCompare={chat.setCompare}
                  />
                  <Composer placeholder={placeholder} ready={ready} streaming={chat.streaming} onSend={chat.send} onStop={chat.stop} />
                  <p className="fineprint">Answers come from merged open models and can be wrong. Mid-range blends sometimes produce odd text.</p>
                </div>
              </>
            )}
          </main>

          <AnimatePresence initial={false}>
            {panel && state.blends.length > 0 && (
              <motion.aside
                key="aside" className="aside" aria-label={TITLES[panel]}
                initial={{ width: 0, opacity: 0 }} animate={{ width: 470, opacity: 1 }} exit={{ width: 0, opacity: 0 }}
                transition={{ type: 'spring', stiffness: 320, damping: 36 }}
              >
                <div className="aside-inner">
                  <header className="aside-head">
                    <h2 className="display">{TITLES[panel]}</h2>
                    <button className="ghost" onClick={() => setPanel(null)} aria-label="Close panel">Close</button>
                  </header>
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div key={panel} className="aside-body" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
                      {panel === 'curve' ? (
                        <CurvePanel blends={state.blends} metrics={state.metrics} blendId={state.blendId} />
                      ) : (
                        <FinderPanel api={api} blends={state.blends} ready={status === 'online'} onUse={(id) => { chat.selectBlend(id); setPanel(null) }} />
                      )}
                    </motion.div>
                  </AnimatePresence>
                </div>
              </motion.aside>
            )}
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  )
}
