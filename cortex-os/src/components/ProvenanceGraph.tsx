import { useState, useEffect } from 'react'
import { Trash2 } from 'lucide-react'

export function ProvenanceGraph() {
  const [deleted, setDeleted] = useState(false)
  useEffect(() => {
    const iv = setInterval(() => {
      setDeleted(true)
      setTimeout(() => setDeleted(false), 2600)
    }, 5200)
    return () => clearInterval(iv)
  }, [])

  const lineColor = deleted ? '#ef4444' : 'rgba(28,28,30,0.18)'
  const dash = deleted ? '4 3' : 'none'

  return (
    <div className="relative">
      <svg viewBox="0 0 280 120" className="w-full">
        {[[60,60,140,30],[60,60,140,60],[60,60,140,90],
          [140,30,220,45],[140,60,220,45],[140,90,220,80]].map(([x1,y1,x2,y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke={lineColor} strokeWidth="1.5" strokeDasharray={dash}
            className="transition-all duration-500" />
        ))}
        <circle cx="60" cy="60" r="14"
          fill={deleted ? '#7f1d1d' : 'rgba(122,140,0,0.12)'}
          stroke={deleted ? '#ef4444' : 'var(--lime)'}
          strokeWidth="1.5" className="transition-all duration-500" />
        <text x="60" y="64" textAnchor="middle" fill="white" fontSize="7" fontFamily="monospace">USER</text>
        {[[140,30],[140,60],[140,90],[220,45],[220,80]].map(([cx,cy], i) => (
          <g key={i}>
            <circle cx={cx} cy={cy} r="10"
              fill={deleted ? '#450a0a' : 'rgba(28,28,30,0.05)'}
              stroke={deleted ? '#ef4444' : 'rgba(28,28,30,0.15)'}
              strokeWidth="1.5"
              opacity={deleted ? 0.35 : 1}
              className="transition-all duration-500" />
            <text x={cx} y={cy+3} textAnchor="middle"
              fill={deleted ? '#ef4444' : 'rgba(28,28,30,0.55)'}
              fontSize="6" fontFamily="monospace">
              {i < 3 ? 'MEM' : 'RSP'}
            </text>
          </g>
        ))}
        {deleted && (
          <g>
            <rect x="65" y="100" width="150" height="16" rx="4" fill="rgba(127,29,29,0.8)" />
            <text x="140" y="111" textAnchor="middle" fill="#ef4444" fontSize="7" fontFamily="monospace">
              GDPR CASCADE: DELETING...
            </text>
          </g>
        )}
      </svg>
      {!deleted && (
        <button onClick={() => setDeleted(true)}
          className="absolute bottom-0 right-0 flex items-center gap-1 text-xs font-mono transition-colors"
          style={{ color: 'var(--muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#B91C1C')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}>
          <Trash2 size={11} /> simulate deletion
        </button>
      )}
    </div>
  )
}
