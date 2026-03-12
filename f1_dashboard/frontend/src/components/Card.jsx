import React from 'react'

export function Card({ children, className = '', accent = false, glow = false, padding = 'p-5' }) {
  return (
    <div className={`
      bg-lf-card rounded-xl border border-lf-border ${padding}
      shadow-card transition-all duration-200
      ${accent ? 'accent-line pl-7' : ''}
      ${glow ? 'hover:shadow-card-hover hover:border-lf-muted' : ''}
      ${className}
    `}>
      {children}
    </div>
  )
}

export function StatCard({ label, value, sub, color, icon: Icon, trend, className = '' }) {
  const colorMap = {
    red: 'text-lf-red',
    green: 'text-lf-green',
    yellow: 'text-lf-yellow',
    blue: 'text-lf-blue',
    purple: 'text-lf-purple',
    default: 'text-white',
  }
  const textColor = colorMap[color] || colorMap.default

  return (
    <Card glow className={`group ${className}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-0.5 sm:space-y-1 min-w-0">
          <p className="text-[10px] sm:text-[11px] uppercase tracking-wider text-lf-text font-medium">{label}</p>
          <p className={`text-xl sm:text-2xl font-bold tabular-nums truncate ${textColor}`}>{value}</p>
          {sub && <p className="text-xs text-lf-text">{sub}</p>}
        </div>
        {Icon && (
          <div className="p-1.5 sm:p-2 rounded-lg bg-lf-surface group-hover:bg-lf-border transition-colors shrink-0 hidden sm:block">
            <Icon size={16} className="text-lf-text" />
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div className={`mt-2 text-xs font-medium ${trend >= 0 ? 'text-lf-green' : 'text-lf-red'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
        </div>
      )}
    </Card>
  )
}

export function SectionTitle({ children, right, sub }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-[15px] font-semibold text-white tracking-tight">{children}</h2>
        {sub && <p className="text-xs text-lf-text mt-0.5">{sub}</p>}
      </div>
      {right}
    </div>
  )
}

export function Badge({ children, color = 'gray', dot = false, className = '' }) {
  const colors = {
    red: 'bg-lf-red/15 text-lf-red border-lf-red/20',
    green: 'bg-lf-green/15 text-lf-green border-lf-green/20',
    yellow: 'bg-lf-yellow/15 text-lf-yellow border-lf-yellow/20',
    blue: 'bg-lf-blue/15 text-lf-blue border-lf-blue/20',
    purple: 'bg-lf-purple/15 text-lf-purple border-lf-purple/20',
    orange: 'bg-lf-orange/15 text-lf-orange border-lf-orange/20',
    gray: 'bg-lf-surface text-lf-text border-lf-border',
    cyan: 'bg-lf-cyan/15 text-lf-cyan border-lf-cyan/20',
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold border ${colors[color] || colors.gray} ${className}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${color === 'green' ? 'bg-lf-green live-dot' : `bg-current`}`} />}
      {children}
    </span>
  )
}

export function Tabs({ tabs, active, onChange, size = 'md' }) {
  return (
    <div className="flex gap-0.5 bg-lf-dark rounded-lg p-0.5 border border-lf-border w-fit max-w-full">
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`flex items-center gap-1 sm:gap-1.5 rounded-md font-medium transition-all duration-200 whitespace-nowrap ${
            size === 'sm' ? 'px-2 sm:px-3 py-1.5 text-[11px] sm:text-xs' : 'px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm'
          } ${
            active === t.id
              ? 'bg-lf-card text-white shadow-sm'
              : 'text-lf-text hover:text-white'
          }`}
        >
          {t.icon && <t.icon size={size === 'sm' ? 12 : 13} />}
          <span className="hidden xs:inline sm:inline">{t.label}</span>
          <span className="xs:hidden sm:hidden">{t.label?.slice(0, 4)}</span>
          {t.badge != null && (
            <span className={`ml-0.5 sm:ml-1 px-1 sm:px-1.5 py-0 rounded text-[9px] sm:text-[10px] font-bold ${
              active === t.id ? 'bg-lf-red/20 text-lf-red' : 'bg-lf-surface text-lf-text'
            }`}>{t.badge}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {Icon && <Icon size={36} className="text-lf-muted mb-3" strokeWidth={1.5} />}
      <h3 className="text-sm font-semibold text-lf-text">{title}</h3>
      {description && <p className="text-xs text-lf-muted mt-1 max-w-md">{description}</p>}
    </div>
  )
}

export function Loader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="relative">
        <div className="w-10 h-10 rounded-full border-2 border-lf-border border-t-lf-red animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-3 h-3 rounded-full bg-lf-red/30" />
        </div>
      </div>
    </div>
  )
}
