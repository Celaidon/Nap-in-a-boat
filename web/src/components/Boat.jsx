// The one illustration: a flat rowboat in the deck's colours. Hand-built SVG, no stock art.
const INK = '#3f0009'

export function Boat({ className, title }) {
  return (
    <svg viewBox="0 0 240 150" className={className} role={title ? 'img' : undefined} aria-hidden={title ? undefined : true}>
      {title && <title>{title}</title>}
      <g strokeLinecap="round" strokeLinejoin="round">
        <path d="M24 122 L190 46" stroke={INK} strokeWidth="6" fill="none" />
        <path d="M62 40 L200 124" stroke={INK} strokeWidth="6" fill="none" />
        <ellipse cx="30" cy="120" rx="17" ry="7" transform="rotate(-24 30 120)" fill="#e49b2b" stroke={INK} strokeWidth="4" />
        <ellipse cx="205" cy="127" rx="17" ry="7" transform="rotate(32 205 127)" fill="#e49b2b" stroke={INK} strokeWidth="4" />
        <path d="M16 80 H224 C216 120 184 140 120 140 S24 120 16 80Z" fill="#e49b2b" stroke={INK} strokeWidth="5" />
        <path d="M32 90 Q120 112 208 90" fill="none" stroke="#fff8f5" strokeWidth="4" opacity="0.85" />
        <path d="M98 82 Q120 46 142 82Z" fill="#6b0011" stroke={INK} strokeWidth="4" />
        <circle cx="120" cy="56" r="15" fill="#ffdfe3" stroke={INK} strokeWidth="4" />
        <path d="M16 80 H224" stroke={INK} strokeWidth="5" fill="none" />
      </g>
    </svg>
  )
}
