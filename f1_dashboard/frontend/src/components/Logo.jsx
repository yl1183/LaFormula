import React from 'react'

export function Logo({ size = 'md', animate = true }) {
  const sizes = {
    sm: { w: 32, text: 'text-sm', sub: 'text-[8px]' },
    md: { w: 38, text: 'text-base', sub: 'text-[9px]' },
    lg: { w: 56, text: 'text-2xl', sub: 'text-[11px]' },
    xl: { w: 80, text: 'text-4xl', sub: 'text-xs' },
  }
  const s = sizes[size] || sizes.md

  return (
    <div className="flex items-center gap-2.5 group">
      <div className="relative" style={{ width: s.w, height: s.w }}>
        <svg width={s.w} height={s.w} viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            {/* Glow filter */}
            <filter id="logo-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
              <feColorMatrix in="blur" type="matrix" values="1 0 0 0 0  0 0.02 0 0 0  0 0 0 0 0  0 0 0 0.6 0" />
              <feMerge>
                <feMergeNode />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            
            {/* Speed lines gradient */}
            <linearGradient id="speed-grad" x1="0" y1="0" x2="80" y2="0">
              <stop offset="0%" stopColor="#E10600" stopOpacity="0" />
              <stop offset="40%" stopColor="#E10600" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#FF4444" stopOpacity="1" />
            </linearGradient>
            
            <linearGradient id="track-grad" x1="0" y1="0" x2="80" y2="80">
              <stop offset="0%" stopColor="#E10600" />
              <stop offset="100%" stopColor="#B00500" />
            </linearGradient>
            
            {/* Animated dash for the track line */}
            <linearGradient id="dash-grad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#E10600" stopOpacity="0" />
              <stop offset="50%" stopColor="#FF6B6B" stopOpacity="1" />
              <stop offset="100%" stopColor="#E10600" stopOpacity="0" />
            </linearGradient>
          </defs>
          
          {/* Background: angular racing shape */}
          <path d="M8 0H60L80 20V72C80 76.418 76.418 80 72 80H8C3.582 80 0 76.418 0 72V8C0 3.582 3.582 0 8 0Z" 
            fill="#0D0D14" stroke="#E10600" strokeWidth="1.5" strokeOpacity="0.3" filter="url(#logo-glow)" />
          
          {/* Cut corner accent */}
          <path d="M60 0L80 20H68C63.582 20 60 16.418 60 12V0Z" fill="url(#track-grad)" />
          
          {/* Speed lines — the animated trail */}
          <g className={animate ? 'logo-speed-lines' : ''} opacity="0.4">
            <rect x="4" y="30" width="24" height="1.5" rx="0.75" fill="url(#speed-grad)">
              {animate && <animate attributeName="width" values="0;24;0" dur="3s" repeatCount="indefinite" />}
              {animate && <animate attributeName="opacity" values="0;0.6;0" dur="3s" repeatCount="indefinite" />}
            </rect>
            <rect x="4" y="42" width="18" height="1.5" rx="0.75" fill="url(#speed-grad)">
              {animate && <animate attributeName="width" values="0;18;0" dur="3s" begin="0.3s" repeatCount="indefinite" />}
              {animate && <animate attributeName="opacity" values="0;0.4;0" dur="3s" begin="0.3s" repeatCount="indefinite" />}
            </rect>
            <rect x="4" y="54" width="14" height="1.5" rx="0.75" fill="url(#speed-grad)">
              {animate && <animate attributeName="width" values="0;14;0" dur="3s" begin="0.6s" repeatCount="indefinite" />}
              {animate && <animate attributeName="opacity" values="0;0.3;0" dur="3s" begin="0.6s" repeatCount="indefinite" />}
            </rect>
          </g>
          
          {/* Telemetry trace — animated racing line */}
          <path d="M6 65 Q20 58, 30 62 T50 55 T74 50" 
            fill="none" stroke="#E10600" strokeWidth="1" strokeOpacity="0.25"
            strokeDasharray="4 3">
            {animate && <animate attributeName="stroke-dashoffset" values="0;-80" dur="4s" repeatCount="indefinite" />}
          </path>
          
          {/* The "L" — bold geometric */}
          <text x="14" y="56" fontFamily="'Space Grotesk', sans-serif" fontWeight="800" fontSize="40" fill="white" letterSpacing="-3">
            L
          </text>
          
          {/* The "F" — with red accent */}
          <text x="38" y="56" fontFamily="'Space Grotesk', sans-serif" fontWeight="800" fontSize="40" fill="#E10600" letterSpacing="-3">
            F
          </text>
          
          {/* Dot — like a position marker on track */}
          <circle cx="74" cy="6" r="2.5" fill="#E10600">
            {animate && <animate attributeName="r" values="2;3;2" dur="2s" repeatCount="indefinite" />}
            {animate && <animate attributeName="opacity" values="0.8;1;0.8" dur="2s" repeatCount="indefinite" />}
          </circle>
          
          {/* Checkered micro-pattern in corner */}
          <g opacity="0.15">
            <rect x="62" y="2" width="4" height="4" fill="white" />
            <rect x="70" y="2" width="4" height="4" fill="white" />
            <rect x="66" y="6" width="4" height="4" fill="white" />
            <rect x="74" y="6" width="4" height="4" fill="white" />
            <rect x="62" y="10" width="4" height="4" fill="white" />
            <rect x="70" y="10" width="4" height="4" fill="white" />
            <rect x="74" y="14" width="4" height="4" fill="white" />
          </g>
        </svg>
      </div>
      
      <div className="flex flex-col leading-none">
        <span className={`font-bold tracking-tight ${s.text}`}>
          La <span className="text-lf-red group-hover:text-lf-red-glow transition-colors">Formula</span>
        </span>
        <span className={`uppercase tracking-[0.2em] text-lf-text font-medium mt-0.5 ${s.sub}`}>
          Trading Intelligence
        </span>
      </div>
    </div>
  )
}

export function LogoMark({ size = 32, animate = true }) {
  return (
    <svg width={size} height={size} viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lm-grad" x1="0" y1="0" x2="80" y2="80">
          <stop offset="0%" stopColor="#E10600" /><stop offset="100%" stopColor="#B00500" />
        </linearGradient>
      </defs>
      <path d="M8 0H60L80 20V72C80 76.418 76.418 80 72 80H8C3.582 80 0 76.418 0 72V8C0 3.582 3.582 0 8 0Z" 
        fill="#0D0D14" stroke="#E10600" strokeWidth="1.5" strokeOpacity="0.3" />
      <path d="M60 0L80 20H68C63.582 20 60 16.418 60 12V0Z" fill="url(#lm-grad)" />
      <text x="14" y="56" fontFamily="'Space Grotesk', sans-serif" fontWeight="800" fontSize="40" fill="white" letterSpacing="-3">L</text>
      <text x="38" y="56" fontFamily="'Space Grotesk', sans-serif" fontWeight="800" fontSize="40" fill="#E10600" letterSpacing="-3">F</text>
      <circle cx="74" cy="6" r="2.5" fill="#E10600">
        {animate && <animate attributeName="r" values="2;3;2" dur="2s" repeatCount="indefinite" />}
      </circle>
    </svg>
  )
}
