import React, { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Activity, Brain, FlaskConical, Flag, Settings, Menu, X } from 'lucide-react'
import { Logo, LogoMark } from './components/Logo'
import { Badge } from './components/Card'
import { StartingLights, RacingStripe } from './components/Animations'
import Dashboard from './pages/Dashboard'
import Trading from './pages/Trading'
import Predictions from './pages/Predictions'
import Backtest from './pages/Backtest'
import F1Hub from './pages/F1Hub'
import Config from './pages/Config'
import { api } from './api'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Portfolio' },
  { to: '/trade',       icon: Activity,        label: 'Trading' },
  { to: '/predictions', icon: Brain,           label: 'Predictions' },
  { to: '/f1',          icon: Flag,            label: 'F1 Hub' },
  { to: '/backtest',    icon: FlaskConical,    label: 'Backtest' },
  { to: '/config',      icon: Settings,        label: 'System' },
]

export default function App() {
  const [health, setHealth] = useState(null)
  const [showLights, setShowLights] = useState(() => !sessionStorage.getItem('lf_lights_done'))
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()

  // Close mobile menu on navigation
  useEffect(() => { setMobileMenuOpen(false) }, [location.pathname])

  useEffect(() => {
    const poll = () => api.getHealth().then(setHealth).catch(() => {})
    poll()
    const i = setInterval(poll, 30000)
    return () => clearInterval(i)
  }, [])

  const halted = health?.halted
  const isLive = health?.monitor_mode === 'weekend_active'
  const isConnected = health?.monitor_active

  return (
    <div className="min-h-screen bg-lf-black pb-16 md:pb-0">
      {/* ═══ Starting Lights (first visit only) ═══ */}
      {showLights && (
        <StartingLights onComplete={() => {
          setShowLights(false)
          sessionStorage.setItem('lf_lights_done', '1')
        }} />
      )}

      {/* ═══ Top Navigation (desktop + mobile header) ═══ */}
      <nav className="sticky top-0 z-50 glass border-b border-lf-border/50">
        <div className="max-w-[1400px] mx-auto px-3 sm:px-6 flex items-center h-12 sm:h-14 gap-3 sm:gap-6">
          {/* Logo */}
          <NavLink to="/" className="shrink-0">
            <span className="hidden sm:block"><Logo size="sm" /></span>
            <span className="sm:hidden"><LogoMark size={28} /></span>
          </NavLink>

          {/* Divider */}
          <div className="w-px h-6 bg-lf-border hidden md:block" />

          {/* Desktop Nav Links */}
          <div className="hidden md:flex items-center gap-0.5 flex-1 overflow-x-auto scrollbar-none">
            {NAV.map(n => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === '/'}
                className={({ isActive }) => `
                  relative flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] font-medium
                  transition-all duration-200 whitespace-nowrap
                  ${isActive
                    ? 'text-white bg-lf-surface'
                    : 'text-lf-text hover:text-white hover:bg-white/[0.03]'
                  }
                `}
              >
                {({ isActive }) => (
                  <>
                    <n.icon size={15} className={isActive ? 'text-lf-red' : ''} />
                    <span>{n.label}</span>
                    {isActive && (
                      <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-lf-red rounded-full" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>

          {/* Spacer for mobile */}
          <div className="flex-1 md:hidden" />

          {/* Status Cluster */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {halted && (
              <Badge color="red" dot>HALTED</Badge>
            )}
            {isLive ? (
              <Badge color="green" dot><span className="hidden sm:inline">RACE </span>LIVE</Badge>
            ) : isConnected ? (
              <Badge color="blue" dot><span className="hidden sm:inline">SCAN</span><span className="sm:hidden">ON</span></Badge>
            ) : (
              <Badge color="gray" dot>OFF</Badge>
            )}
          </div>
        </div>
        {/* Animated racing stripe under nav */}
        <RacingStripe />
      </nav>

      {/* ═══ Content ═══ */}
      <main className="max-w-[1400px] mx-auto px-3 sm:px-6 py-4 sm:py-6" key={location.pathname}
        style={{ animation: 'pageEnter 0.35s ease-out' }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/trade" element={<Trading />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/f1" element={<F1Hub />} />
          <Route path="/config" element={<Config />} />
        </Routes>
      </main>

      {/* ═══ Footer (desktop only) ═══ */}
      <footer className="hidden md:block border-t border-lf-border/30 mt-auto">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between text-[11px] text-lf-muted">
          <span>La Formula © 2026 — Autonomous F1 Market Intelligence</span>
          <span className="tabular-nums">
            {health?.boot_number && `Boot #${health.boot_number}`}
            {health?.poll_count != null && ` · ${health.poll_count} polls`}
          </span>
        </div>
      </footer>

      {/* ═══ Mobile Bottom Navigation ═══ */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 glass border-t border-lf-border/50 safe-bottom">
        <div className="flex items-center justify-around h-14 px-1">
          {NAV.map(n => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `
                flex flex-col items-center justify-center gap-0.5 px-2 py-1.5 rounded-lg min-w-[52px]
                transition-all duration-200
                ${isActive
                  ? 'text-lf-red'
                  : 'text-lf-muted'
                }
              `}
            >
              {({ isActive }) => (
                <>
                  <n.icon size={18} strokeWidth={isActive ? 2.5 : 1.5} />
                  <span className="text-[9px] font-medium leading-none">{n.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes pageEnter {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .safe-bottom {
          padding-bottom: env(safe-area-inset-bottom, 0);
        }
      `}</style>
    </div>
  )
}
