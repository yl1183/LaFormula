import React, { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Target, AlertTriangle, Activity, RefreshCw, ShieldAlert, Zap, Flag } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts'
import { Card, StatCard, SectionTitle, Badge, Loader, EmptyState } from '../components/Card'
import { api } from '../api'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-lf-card/95 backdrop-blur border border-lf-border rounded-lg px-3 py-2 shadow-lg">
      <p className="text-xs text-lf-text">{label}</p>
      <p className="text-sm font-bold tabular-nums">${payload[0].value?.toFixed(2)}</p>
    </div>
  )
}

export default function Dashboard() {
  const [state, setState] = useState(null)
  const [config, setConfig] = useState(null)
  const [monitor, setMonitor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const refresh = () => {
    Promise.all([api.getState(), api.getConfig(), api.getMonitorStatus()])
      .then(([s, c, m]) => { setState(s); setConfig(c); setMonitor(m) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    refresh()
    const i = setInterval(refresh, 15000)
    return () => clearInterval(i)
  }, [])

  const syncKalshi = async () => {
    setSyncing(true)
    try { await api.syncKalshi(); setState(await api.getState()) } catch(e) {}
    setSyncing(false)
  }

  if (loading) return <Loader />
  if (!state) return <EmptyState icon={AlertTriangle} title="Failed to load" />

  const pnl = state.bankroll - state.initial_bankroll
  const pnlPct = ((pnl / state.initial_bankroll) * 100).toFixed(1)
  const totalTrades = (state.history || []).length
  const wins = (state.history || []).filter(t => t.won).length
  const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(0) : '—'
  const openCount = (state.positions || []).length
  const drawdown = state.peak_bankroll > 0
    ? (((state.peak_bankroll - state.bankroll) / state.peak_bankroll) * 100).toFixed(1) : '0.0'
  const nextRace = config?.races?.find(r => new Date(r.date) > new Date()) || config?.races?.[0]

  return (
    <div className="space-y-4 sm:space-y-6 animate-fade-in">
      {/* ── Alert Banner ── */}
      {state.halted && (
        <div className="flex items-center gap-3 bg-lf-red/10 border border-lf-red/20 rounded-xl px-4 py-3">
          <ShieldAlert size={18} className="text-lf-red shrink-0" />
          <span className="text-sm text-lf-red font-medium">{state.halt_reason || 'Kill switch active'}</span>
        </div>
      )}

      {/* ── Status Bar ── */}
      <div className="bg-lf-card border border-lf-border rounded-xl px-3 sm:px-5 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className={`w-2 h-2 rounded-full shrink-0 ${monitor?.active ? 'bg-lf-green live-dot' : 'bg-lf-muted'}`} />
            <span className="text-xs text-lf-text truncate">
              {state.kalshi_synced
                ? `Kalshi · $${(state.kalshi_balance || state.bankroll).toFixed(2)}`
                : config?.dry_run ? 'Dry run' : 'Disconnected'}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge color={monitor?.mode === 'weekend_active' ? 'green' : monitor?.mode === 'daily_scan' ? 'blue' : 'gray'} dot>
              <span className="hidden sm:inline">{monitor?.mode === 'weekend_active' ? 'RACE WEEKEND' : monitor?.mode === 'daily_scan' ? 'SCANNING' : 'IDLE'}</span>
              <span className="sm:hidden">{monitor?.mode === 'weekend_active' ? 'LIVE' : monitor?.mode === 'daily_scan' ? 'SCAN' : 'IDLE'}</span>
            </Badge>
            <button onClick={syncKalshi} disabled={syncing}
              className="flex items-center gap-1 text-[11px] text-lf-text hover:text-white px-2 py-1.5 rounded-md bg-lf-surface border border-lf-border hover:border-lf-muted transition-all">
              <RefreshCw size={10} className={syncing ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">Sync</span>
            </button>
          </div>
        </div>
      </div>

      {/* ── Stats Grid — 2 cols mobile, 5 cols desktop ── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 sm:gap-3">
        <StatCard label="Bankroll" value={`$${state.bankroll.toFixed(2)}`} icon={DollarSign}
          color={pnl >= 0 ? 'green' : 'red'} sub={`${pnl >= 0 ? '+' : ''}${pnlPct}%`} />
        <StatCard label="P&L" value={`${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`} icon={TrendingUp}
          color={pnl >= 0 ? 'green' : 'red'} />
        <StatCard label="Win Rate" value={winRate === '—' ? '—' : `${winRate}%`} icon={Target}
          sub={totalTrades > 0 ? `${wins}W/${totalTrades - wins}L` : 'No trades'} />
        <StatCard label="Drawdown" value={`${drawdown}%`} icon={AlertTriangle}
          color={parseFloat(drawdown) > 30 ? 'red' : 'yellow'} />
        <StatCard label="Open" value={openCount} icon={Activity}
          color={openCount > 0 ? 'blue' : 'default'} sub={openCount > 0 ? 'Active' : 'None'} className="col-span-2 lg:col-span-1" />
      </div>

      {/* ── Equity Curve ── */}
      <Card>
        <SectionTitle sub="Portfolio value over time">Equity Curve</SectionTitle>
        {state.pnl_curve && state.pnl_curve.length > 1 ? (
          <div className="-mx-2 sm:mx-0">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={state.pnl_curve}>
                <defs>
                  <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#E10600" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#E10600" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} domain={['auto', 'auto']} width={35} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={100} stroke="#2A2A3A" strokeDasharray="3 3" />
                <Area type="monotone" dataKey="bankroll" stroke="#E10600" strokeWidth={2} fill="url(#equityFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState icon={TrendingUp} title="No trade history yet"
            description="The equity curve will appear once the system places and settles its first trades." />
        )}
      </Card>

      {/* ── Two Columns (stack on mobile) ── */}
      <div className="grid lg:grid-cols-2 gap-3 sm:gap-4">
        {/* Open Positions */}
        <Card>
          <SectionTitle>Open Positions</SectionTitle>
          {(state.positions || []).length === 0 ? (
            <EmptyState icon={Activity} title="No open positions"
              description="Trades are placed automatically during race weekends." />
          ) : (
            <div className="space-y-2">
              {state.positions.map(p => (
                <div key={p.id} className="flex items-center justify-between bg-lf-surface rounded-lg p-3 border border-lf-border/50 gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge color={p.sleeve === 'A' ? 'blue' : p.sleeve === 'B' ? 'orange' : 'purple'}>
                      {p.sleeve}
                    </Badge>
                    <span className="text-sm font-medium truncate">{p.label}</span>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-lf-text tabular-nums">${p.risk?.toFixed(2)}</p>
                    <p className="text-xs text-lf-green tabular-nums">+${p.potential_profit?.toFixed(2)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Next Race */}
        <Card>
          <SectionTitle>Next Race</SectionTitle>
          {nextRace ? (
            <div className="space-y-3">
              <div>
                <h3 className="text-lg sm:text-xl font-bold tracking-tight">{nextRace.name}</h3>
                <p className="text-xs sm:text-sm text-lf-text mt-1">{nextRace.circuit}</p>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <Badge color="gray">Round {nextRace.round}</Badge>
                  <span className="text-xs text-lf-muted">{nextRace.date}</span>
                  {config.sprint_rounds?.includes(nextRace.round) && (
                    <Badge color="purple">Sprint</Badge>
                  )}
                </div>
              </div>
              <div className="bg-lf-surface rounded-lg p-3 sm:p-4 border border-lf-border/50">
                <div className="flex items-center gap-2 mb-2">
                  <Zap size={14} className="text-lf-yellow" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-lf-text">Strategy</span>
                </div>
                <p className="text-sm font-medium">
                  {nextRace.round <= config.calibration_races
                    ? `Half-size (cal ${nextRace.round}/${config.calibration_races})`
                    : 'Full-size'
                  }
                </p>
                <p className="text-xs text-lf-text mt-1 tabular-nums">
                  ${nextRace.round <= config.calibration_races
                    ? (config.flat_bet_size / 2).toFixed(2)
                    : config.flat_bet_size.toFixed(2)} per trade
                </p>
              </div>
            </div>
          ) : (
            <EmptyState icon={Flag} title="No upcoming races" />
          )}
        </Card>
      </div>

      {/* ── Trade History ── */}
      <Card>
        <SectionTitle sub={totalTrades > 0 ? `${totalTrades} settled` : null}>Trade History</SectionTitle>
        {totalTrades === 0 ? (
          <EmptyState icon={Activity} title="No settled trades yet"
            description="Auto-trading begins when qualifying and Kalshi prices are available." />
        ) : (
          <>
            {/* Mobile: card layout */}
            <div className="sm:hidden space-y-2">
              {(state.history || []).map(t => (
                <div key={t.id} className="flex items-center gap-3 bg-lf-surface rounded-lg p-3 border border-lf-border/50">
                  <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                    t.won ? 'bg-lf-green/15 text-lf-green' : 'bg-lf-red/15 text-lf-red'
                  }`}>{t.won ? 'W' : 'L'}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{t.label}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge color={t.sleeve === 'A' ? 'blue' : t.sleeve === 'B' ? 'orange' : 'purple'}>{t.sleeve}</Badge>
                      <span className="text-[11px] text-lf-muted">${t.risk?.toFixed(2)} risk</span>
                    </div>
                  </div>
                  <span className={`text-sm font-bold tabular-nums shrink-0 ${(t.pnl||0) >= 0 ? 'text-lf-green' : 'text-lf-red'}`}>
                    {(t.pnl||0) >= 0 ? '+' : ''}${(t.pnl||0).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
            {/* Desktop: table layout */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wider text-lf-text border-b border-lf-border">
                    <th className="text-left py-3 font-medium">Trade</th>
                    <th className="text-left py-3 font-medium">Sleeve</th>
                    <th className="text-right py-3 font-medium">Risk</th>
                    <th className="text-right py-3 font-medium">P&L</th>
                    <th className="text-right py-3 font-medium">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {(state.history || []).map(t => (
                    <tr key={t.id} className="border-b border-lf-border/30 table-row-hover">
                      <td className="py-3 font-medium">{t.label}</td>
                      <td className="py-3">
                        <Badge color={t.sleeve === 'A' ? 'blue' : t.sleeve === 'B' ? 'orange' : 'purple'}>
                          {t.sleeve}
                        </Badge>
                      </td>
                      <td className="py-3 text-right text-lf-text tabular-nums">${t.risk?.toFixed(2)}</td>
                      <td className={`py-3 text-right font-semibold tabular-nums ${(t.pnl||0) >= 0 ? 'text-lf-green' : 'text-lf-red'}`}>
                        {(t.pnl||0) >= 0 ? '+' : ''}${(t.pnl||0).toFixed(2)}
                      </td>
                      <td className="py-3 text-right">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                          t.won ? 'bg-lf-green/15 text-lf-green' : 'bg-lf-red/15 text-lf-red'
                        }`}>
                          {t.won ? 'W' : 'L'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
