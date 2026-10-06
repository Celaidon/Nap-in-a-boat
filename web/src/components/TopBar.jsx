import { motion } from 'framer-motion'
import { Boat } from './Boat.jsx'

const STATUS_LABEL = { online: 'Online', connecting: 'Connecting', reconnecting: 'Reconnecting' }

function StatusPill({ status, mock }) {
  return (
    <span className={`status status-${status}`} role="status">
      <span className="status-dot" aria-hidden="true" />
      <span className="status-text">{mock && status === 'online' ? 'Demo data' : STATUS_LABEL[status] ?? status}</span>
    </span>
  )
}

export function TopBar({ status, mock, panel, onPanel, onNewChat, canClear }) {
  const tab = (id, label, short) => (
    <button className={`topbtn ${panel === id ? 'is-active' : ''}`} onClick={() => onPanel(panel === id ? null : id)} aria-pressed={panel === id} aria-label={label}>
      <span className="long">{label}</span>
      <span className="short">{short}</span>
    </button>
  )
  return (
    <header className="topbar">
      <div className="brand">
        <motion.span className="brand-mark" whileHover={{ rotate: -8 }} transition={{ type: 'spring', stiffness: 300, damping: 14 }}>
          <Boat />
        </motion.span>
        <span className="brand-text">
          <span className="display brand-name">Nap in a boat</span>
          <span className="brand-sub">BlendLab · blend two models, see the trade-off</span>
        </span>
      </div>
      <nav className="topnav" aria-label="Tools">
        <button className="topbtn" onClick={onNewChat} disabled={!canClear} aria-label="New chat">
          <span className="long">New chat</span>
          <span className="short">New</span>
        </button>
        {tab('curve', 'Capability curve', 'Curve')}
        {/* {tab('finder', 'Find best blend', 'Finder')} */}
        <StatusPill status={status} mock={mock} />
      </nav>
    </header>
  )
}
