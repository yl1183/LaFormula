import React, { useState, useEffect } from 'react'
import { Shield, RefreshCw, Activity, Calendar, Cpu, Zap } from 'lucide-react'
import { Card, SectionTitle, Badge, EmptyState } from '../components/Card'
import { api } from '../api'

function ConfigRow({ label, value, highlight, mono }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-lf-border/20 last:border-0 gap-2">
      <span className="text-xs sm:text-sm text-lf-text shrink-0">{label}</span>
      <span className={`text-xs sm:text-sm font-medium text-right ${mono ? 'font-mono tabular-nums' : ''} ${highlight ? 'text-lf-red' : ''}`}>{value}</span>
    </div>
  )
}

function StatusPill({ label, value, ok, alert }) {
  return (
    <div className="bg-lf-surface rounded-lg p-2.5 sm:p-3 border border-lf-border/50">
      <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-muted mb-0.5 sm:mb-1">{label}</p>
      <p className={`text-xs sm:text-sm font-semibold ${alert ? 'text-lf-red' : ok ? 'text-lf-green' : 'text-lf-text'}`}>{value}</p>
    </div>
  )
}

export default function Config() {
  const [config, setConfig] = useState(null)
  const [state, setState] = useState(null)
  const [health, setHealth] = useState(null)
  const [resetConfirm, setResetConfirm] = useState(false)

  useEffect(() => {
    Promise.all([api.getConfig(), api.getState(), api.getHealth().catch(() => null)])
      .then(([c, s, h]) => { setConfig(c); setState(s); setHealth(h) })
      .catch(console.error)
  }, [])

  const handleReset = async () => {
    if (!resetConfirm) { setResetConfirm(true); return }
    await api.resetState()
    setState(await api.getState())
    setResetConfirm(false)
  }

  if (!config) return null

  return (
    <div className="space-y-4 sm:space-y-5 animate-fade-in">
      {/* ── System Health ── */}
      {health && (
        <Card>
          <SectionTitle sub={health.boot_number ? `Boot #${health.boot_number}` : null}>
            <span className="flex items-center gap-2"><Cpu size={16} className="text-lf-blue" /> System Health</span>
          </SectionTitle>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
            <StatusPill label="Server" value="Running" ok />
            <StatusPill label="Monitor" value={health.monitor_active ? 'Active' : 'Off'} ok={health.monitor_active} />
            <StatusPill label="Mode" value={health.monitor_mode?.replace('_', ' ') || 'idle'} />
            <StatusPill label="Trading" value={health.halted ? 'HALTED' : 'Active'} ok={!health.halted} alert={health.halted} />
          </div>
          <div className="mt-3 pt-3 border-t border-lf-border/30 flex items-center gap-3 sm:gap-4 text-[10px] sm:text-[11px] text-lf-muted tabular-nums flex-wrap">
            <span>{health.poll_count} polls</span>
            {health.last_poll && <span>Last: {new Date(health.last_poll).toLocaleTimeString()}</span>}
          </div>
        </Card>
      )}

      {/* ── Configuration (stack on mobile) ── */}
      <div className="grid lg:grid-cols-2 gap-3 sm:gap-4">
        <Card>
          <SectionTitle>
            <span className="flex items-center gap-2"><Shield size={16} className="text-lf-green" /> Safety</span>
          </SectionTitle>
          <div className="space-y-0">
            <ConfigRow label="Mode" value={config.dry_run ? '🔒 DRY RUN' : '🟢 LIVE'} highlight={!config.dry_run} />
            <ConfigRow label="Initial" value={`$${config.initial_bankroll}`} mono />
            <ConfigRow label="Current" value={`$${state?.bankroll?.toFixed(2) || '—'}`} mono />
            <ConfigRow label="Stop-Loss" value={`$${config.stop_loss_floor}`} mono />
            <ConfigRow label="Bet Size" value={`$${config.flat_bet_size}/trade`} mono />
            <ConfigRow label="Calibration" value={`${config.calibration_races} races (½)`} />
            <ConfigRow label="Status" value={state?.halted ? '⛔ HALTED' : '✅ ACTIVE'} highlight={state?.halted} />
          </div>
        </Card>

        <Card>
          <SectionTitle>
            <span className="flex items-center gap-2"><Zap size={16} className="text-lf-yellow" /> Strategy</span>
          </SectionTitle>
          <div className="space-y-0">
            <ConfigRow label="Sleeve A" value="YES podium ≥15%" />
            <ConfigRow label="Sleeve B" value="NO winner P2/P3 ≥8%" />
            <ConfigRow label="Sleeve E" value="NO winner P4+ ≥10%" />
            <ConfigRow label="Max/trade" value={`${(config.max_per_trade_pct * 100)}%`} />
            <ConfigRow label="Max/weekend" value={`${(config.max_per_weekend_pct * 100)}%`} />
            <ConfigRow label="Auto-halt" value="$50 floor" />
            <ConfigRow label="Sprints" value={config.sprint_rounds?.join(', ') || '—'} />
          </div>
        </Card>
      </div>

      {/* ── 2026 Calendar ── */}
      <Card>
        <SectionTitle sub="23 races">
          <span className="flex items-center gap-2"><Calendar size={16} className="text-lf-red" /> 2026 Calendar</span>
        </SectionTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5 sm:gap-2">
          {config.races.map(r => {
            const isPast = new Date(r.date) < new Date()
            const allPast = config.races.filter(x => new Date(x.date) < new Date())
            const isNext = !isPast && allPast.length + 1 === r.round
            const isSprint = config.sprint_rounds?.includes(r.round)

            return (
              <div key={r.round}
                className={`flex items-center gap-2 sm:gap-3 px-2.5 sm:px-3 py-2 sm:py-2.5 rounded-lg text-sm transition-colors ${
                  isNext ? 'bg-lf-red/10 border border-lf-red/20' :
                  isPast ? 'bg-lf-surface/50 text-lf-muted' : 'bg-lf-surface border border-lf-border/30'
                }`}>
                <span className={`font-bold w-5 sm:w-6 text-right tabular-nums text-[11px] sm:text-xs shrink-0 ${
                  isNext ? 'text-lf-red' : 'text-lf-muted'
                }`}>{r.round}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className={`truncate text-xs sm:text-sm ${isNext ? 'text-white font-medium' : ''}`}>{r.name}</span>
                    {isNext && <Badge color="red">NEXT</Badge>}
                    {isSprint && <Badge color="purple">S</Badge>}
                  </div>
                </div>
                <span className="text-[10px] sm:text-[11px] text-lf-muted tabular-nums shrink-0">{r.date}</span>
              </div>
            )
          })}
        </div>
      </Card>

      {/* ── Danger Zone ── */}
      <Card className="border-lf-red/20">
        <SectionTitle sub="Erase all trades, positions, history.">Danger Zone</SectionTitle>
        <button onClick={handleReset}
          className={`flex items-center gap-2 px-4 sm:px-5 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-all border ${
            resetConfirm
              ? 'bg-lf-red text-white border-lf-red shadow-glow-red'
              : 'bg-lf-red/10 text-lf-red border-lf-red/20 hover:bg-lf-red/20'
          }`}>
          <RefreshCw size={14} />
          {resetConfirm ? 'Confirm reset' : 'Reset All State'}
        </button>
      </Card>
    </div>
  )
}
