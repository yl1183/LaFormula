import React, { useState, useEffect, useRef } from 'react'

/* ═══════════════════════════════════════════
   STARTING LIGHTS — F1 race start sequence
   5 red lights → all out → GO
   ═══════════════════════════════════════════ */
export function StartingLights({ onComplete, duration = 2800 }) {
  const [phase, setPhase] = useState(0) // 0-5: lights filling, 6: all out

  useEffect(() => {
    const timers = []
    for (let i = 1; i <= 5; i++) {
      timers.push(setTimeout(() => setPhase(i), i * 400))
    }
    // Lights out after all 5 lit
    timers.push(setTimeout(() => setPhase(6), 2400))
    // Complete
    timers.push(setTimeout(() => onComplete?.(), duration))
    return () => timers.forEach(clearTimeout)
  }, [])

  if (phase === 6) return null

  return (
    <div className="fixed inset-0 z-[9999] bg-black flex items-center justify-center"
      style={{ animation: phase === 6 ? 'fadeOut 0.3s forwards' : undefined }}>
      <div className="flex gap-4">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex flex-col gap-2">
            <div className={`w-8 h-8 rounded-full border-2 transition-all duration-150
              ${phase >= i 
                ? 'bg-red-600 border-red-500 shadow-[0_0_20px_rgba(225,6,0,0.8)]' 
                : 'bg-transparent border-gray-700'}`} 
            />
            <div className={`w-8 h-8 rounded-full border-2 transition-all duration-150
              ${phase >= i 
                ? 'bg-red-600 border-red-500 shadow-[0_0_20px_rgba(225,6,0,0.8)]' 
                : 'bg-transparent border-gray-700'}`} 
            />
          </div>
        ))}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════
   ANIMATED COUNTER — counts up from 0
   Used for key stats (bankroll, P&L, etc.)
   ═══════════════════════════════════════════ */
export function AnimatedCounter({ value, prefix = '', suffix = '', decimals = 2, duration = 1200, className = '' }) {
  const [display, setDisplay] = useState(0)
  const ref = useRef(null)
  const hasAnimated = useRef(false)

  useEffect(() => {
    if (hasAnimated.current) {
      setDisplay(value)
      return
    }
    
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !hasAnimated.current) {
        hasAnimated.current = true
        const start = performance.now()
        const animate = (now) => {
          const elapsed = now - start
          const progress = Math.min(elapsed / duration, 1)
          // Ease out cubic
          const eased = 1 - Math.pow(1 - progress, 3)
          setDisplay(value * eased)
          if (progress < 1) requestAnimationFrame(animate)
        }
        requestAnimationFrame(animate)
        observer.disconnect()
      }
    }, { threshold: 0.3 })

    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [value, duration])

  const formatted = typeof value === 'number' 
    ? `${prefix}${display.toFixed(decimals)}${suffix}`
    : `${prefix}${value}${suffix}`

  return <span ref={ref} className={`tabular-nums ${className}`}>{formatted}</span>
}

/* ═══════════════════════════════════════════
   STAGGER CHILDREN — cascading entrance
   ═══════════════════════════════════════════ */
export function StaggerChildren({ children, delay = 60, className = '' }) {
  return (
    <div className={className}>
      {React.Children.map(children, (child, i) => (
        <div style={{ 
          animation: `fadeSlideUp 0.4s ease-out both`,
          animationDelay: `${i * delay}ms` 
        }}>
          {child}
        </div>
      ))}
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

/* ═══════════════════════════════════════════
   LIVE PULSE — pulsing dot for live status
   ═══════════════════════════════════════════ */
export function LivePulse({ color = 'green', size = 8 }) {
  const colors = {
    green: { bg: '#22c55e', glow: 'rgba(34,197,94,0.4)' },
    red: { bg: '#ef4444', glow: 'rgba(239,68,68,0.4)' },
    yellow: { bg: '#eab308', glow: 'rgba(234,179,8,0.4)' },
    blue: { bg: '#3b82f6', glow: 'rgba(59,130,246,0.4)' },
  }
  const c = colors[color] || colors.green
  return (
    <span className="relative inline-flex" style={{ width: size, height: size }}>
      <span className="absolute inset-0 rounded-full animate-ping" 
        style={{ backgroundColor: c.glow, animationDuration: '2s' }} />
      <span className="relative inline-flex rounded-full w-full h-full" 
        style={{ backgroundColor: c.bg }} />
    </span>
  )
}

/* ═══════════════════════════════════════════
   RACING STRIPE — animated horizontal accent
   ═══════════════════════════════════════════ */
export function RacingStripe({ className = '' }) {
  return (
    <div className={`relative h-[2px] overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-lf-red to-transparent"
        style={{ animation: 'stripeMove 3s ease-in-out infinite' }} />
      <style>{`
        @keyframes stripeMove {
          0%, 100% { transform: translateX(-100%); opacity: 0; }
          50% { transform: translateX(100%); opacity: 1; }
        }
      `}</style>
    </div>
  )
}

/* ═══════════════════════════════════════════
   SECTOR TIME — purple/green/yellow flash
   like F1 timing screens
   ═══════════════════════════════════════════ */
export function SectorTime({ value, best = false, improved = false, className = '' }) {
  const color = best ? 'text-purple-400' : improved ? 'text-green-400' : 'text-yellow-400'
  const bg = best ? 'bg-purple-400/10' : improved ? 'bg-green-400/10' : 'bg-yellow-400/10'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono font-semibold ${color} ${bg} ${className}`}
      style={{ animation: 'sectorFlash 0.6s ease-out' }}>
      {value}
      <style>{`
        @keyframes sectorFlash {
          0% { opacity: 0; transform: scale(1.3); }
          30% { opacity: 1; transform: scale(0.95); }
          100% { transform: scale(1); }
        }
      `}</style>
    </span>
  )
}

/* ═══════════════════════════════════════════
   PROGRESS BAR — animated fill
   ═══════════════════════════════════════════ */
export function AnimatedBar({ value, max = 100, color = '#E10600', height = 6, delay = 0, className = '' }) {
  const [width, setWidth] = useState(0)
  const ref = useRef(null)

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setTimeout(() => setWidth((value / max) * 100), delay)
        observer.disconnect()
      }
    }, { threshold: 0.1 })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [value, max, delay])

  return (
    <div ref={ref} className={`w-full rounded-full overflow-hidden ${className}`}
      style={{ height, backgroundColor: 'rgba(255,255,255,0.06)' }}>
      <div className="h-full rounded-full transition-all duration-1000 ease-out"
        style={{ width: `${width}%`, backgroundColor: color }} />
    </div>
  )
}

/* ═══════════════════════════════════════════
   GRID POSITION BADGE — with team color
   ═══════════════════════════════════════════ */
export function GridBadge({ position, className = '' }) {
  const colors = position === 1 ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
    : position === 2 ? 'bg-gray-400/20 text-gray-300 border-gray-400/30'
    : position === 3 ? 'bg-orange-600/20 text-orange-400 border-orange-600/30'
    : 'bg-white/5 text-lf-text border-white/10'
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-md border text-xs font-bold font-mono ${colors} ${className}`}>
      P{position}
    </span>
  )
}

/* ═══════════════════════════════════════════
   TYRE CHIP — compound indicator
   ═══════════════════════════════════════════ */
export function TyreChip({ compound, className = '' }) {
  const tyres = {
    SOFT: { color: '#FF3333', label: 'S' },
    MEDIUM: { color: '#FFD700', label: 'M' },
    HARD: { color: '#FFFFFF', label: 'H' },
    INTERMEDIATE: { color: '#39B54A', label: 'I' },
    WET: { color: '#0072CE', label: 'W' },
  }
  const t = tyres[compound?.toUpperCase()] || tyres.MEDIUM
  return (
    <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold border ${className}`}
      style={{ borderColor: t.color, color: t.color, backgroundColor: `${t.color}15` }}>
      {t.label}
    </span>
  )
}

/* ═══════════════════════════════════════════
   CHECKERED FLAG — for section endings
   ═══════════════════════════════════════════ */
export function CheckeredDivider({ className = '' }) {
  const squares = 24
  return (
    <div className={`flex h-[6px] overflow-hidden opacity-20 ${className}`}>
      {Array.from({ length: squares }).map((_, i) => (
        <div key={i} className={`flex-1 ${i % 2 === 0 ? 'bg-white' : 'bg-transparent'}`} />
      ))}
    </div>
  )
}

/* ═══════════════════════════════════════════
   SPEED COUNTER — fast counting number display
   ═══════════════════════════════════════════ */
export function SpeedNumber({ value, className = '' }) {
  const [show, setShow] = useState(false)
  const ref = useRef(null)
  
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setShow(true); observer.disconnect() }
    }, { threshold: 0.3 })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  
  return (
    <span ref={ref} className={className}
      style={show ? { animation: 'numberReveal 0.5s ease-out' } : { opacity: 0 }}>
      {value}
      <style>{`
        @keyframes numberReveal {
          0% { opacity: 0; transform: translateY(8px) scale(0.9); filter: blur(4px); }
          60% { opacity: 1; filter: blur(0); }
          80% { transform: translateY(-2px) scale(1.02); }
          100% { transform: translateY(0) scale(1); }
        }
      `}</style>
    </span>
  )
}
