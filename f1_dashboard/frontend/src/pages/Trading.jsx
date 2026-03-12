import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity, Radio, AlertTriangle, ShieldAlert, ShieldCheck, Clock,
  Eye, EyeOff, BarChart3, TrendingUp, TrendingDown, Zap, ChevronDown,
  ChevronRight, Search, Filter
} from 'lucide-react'
import { Card, SectionTitle, Badge, Tabs, EmptyState, Loader } from '../components/Card'
import { api } from '../api'

// ═══════════════════════════════════════════════════════════════
// TEAM COLORS
// ═══════════════════════════════════════════════════════════════
const TEAM_COLORS = {
  'Red Bull': '#3671C6', 'Mercedes': '#27F4D2', 'Ferrari': '#E8002D',
  'McLaren': '#FF8000', 'Aston Martin': '#229971', 'Alpine': '#FF87BC',
  'Williams': '#64C4FF', 'RB': '#6692FF', 'Kick Sauber': '#52E252',
  'Haas': '#B6BABD', 'Cadillac': '#FFD700',
}

function getTeamColor(team) {
  if (!team) return '#3A3A4D'
  for (const [k, v] of Object.entries(TEAM_COLORS)) {
    if (team.toLowerCase().includes(k.toLowerCase())) return v
  }
  return '#3A3A4D'
}

// ═══════════════════════════════════════════════════════════════
// HERO CARD — Actionable contracts
// ═══════════════════════════════════════════════════════════════
function HeroContract({ contract: c }) {
  const [open, setOpen] = useState(false)
  const teamColor = getTeamColor(c.team)
  const isAction = c.decision === 'TRADE'

  return (
    <div
      className={`relative rounded-xl border overflow-hidden transition-all duration-200 cursor-pointer ${
        isAction
          ? 'bg-gradient-to-r from-lf-green/[0.06] to-transparent border-lf-green/30 hover:border-lf-green/50 shadow-glow-green'
          : c.decision === 'BLOCKED'
          ? 'bg-gradient-to-r from-lf-yellow/[0.06] to-transparent border-lf-yellow/30 hover:border-lf-yellow/50'
          : 'bg-lf-card border-lf-border hover:border-lf-muted'
      }`}
      onClick={() => setOpen(!open)}
    >
      {/* Team color accent */}
      <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl" style={{ background: teamColor }} />

      <div className="p-3 sm:p-5 pl-4 sm:pl-5">
        {/* Top section — stacks on mobile */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          {/* Driver info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-lg sm:text-xl font-bold tracking-tight">{c.driver}</span>
              {c.driver_name && (
                <span className="text-xs sm:text-sm text-lf-text">{c.driver_name}</span>
              )}
              <Badge color={c.market === 'winner' ? 'red' : 'cyan'}>
                {c.market === 'winner' ? 'Winner' : 'Podium'}
              </Badge>
              {c.grid_pos && (
                <span className="text-xs font-mono text-lf-muted bg-lf-surface px-1.5 py-0.5 rounded">
                  P{c.grid_pos}
                </span>
              )}
            </div>
            {c.team && <p className="text-xs text-lf-muted mt-0.5">{c.team}</p>}
            {c.sleeve_match && (
              <div className="mt-1.5">
                <Badge color={c.sleeve_match === 'A' ? 'blue' : c.sleeve_match === 'B' ? 'orange' : 'purple'}>
                  Sleeve {c.sleeve_match}: {c.sleeve_match === 'A' ? 'Lottery' : c.sleeve_match === 'B' ? 'Grinder' : 'Value'}
                </Badge>
              </div>
            )}
          </div>

          {/* Price / Rate / Edge / Decision — grid on mobile, flex on desktop */}
          <div className="grid grid-cols-4 sm:flex sm:items-center gap-3 sm:gap-5 shrink-0">
            <div className="text-center sm:text-right">
              <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-muted">Price</p>
              <p className="text-base sm:text-lg font-bold tabular-nums font-mono">{(c.price * 100).toFixed(0)}¢</p>
            </div>
            {c.base_rate !== null && (
              <div className="text-center sm:text-right">
                <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-muted">Fair</p>
                <p className="text-base sm:text-lg font-semibold tabular-nums font-mono text-lf-text">
                  {(c.base_rate * 100).toFixed(0)}%
                </p>
              </div>
            )}
            <div className="text-center sm:text-right">
              <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-muted">Edge</p>
              <p className={`text-base sm:text-lg font-bold tabular-nums font-mono ${
                c.edge >= 0.15 ? 'text-lf-green' :
                c.edge >= 0.08 ? 'text-lf-yellow' :
                c.edge > 0 ? 'text-lf-text' : 'text-lf-red'
              }`}>
                {c.edge != null ? `${(c.edge * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-muted sm:hidden">Status</p>
              <span className={`inline-block px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[10px] sm:text-xs font-bold ${
                c.decision === 'TRADE'   ? 'bg-lf-green/20 text-lf-green' :
                c.decision === 'BLOCKED' ? 'bg-lf-yellow/20 text-lf-yellow' :
                c.decision === 'WAITING' ? 'bg-lf-blue/20 text-lf-blue' :
                                           'bg-lf-surface text-lf-muted'
              }`}>
                {c.decision === 'TRADE' ? 'TRADE' :
                 c.decision === 'BLOCKED' ? 'BLOCKED' :
                 c.decision === 'WAITING' ? 'WAIT' : 'PASS'}
              </span>
            </div>
          </div>
        </div>

        {/* Signal summary */}
        {c.signal && (
          <div className="mt-2.5 flex items-center gap-3 sm:gap-4 text-xs flex-wrap">
            <span className="flex items-center gap-1 text-lf-text">
              {c.signal.action === 'BUY_YES'
                ? <><TrendingUp size={12} className="text-lf-green" /> Buy YES</>
                : <><TrendingDown size={12} className="text-lf-orange" /> Buy NO</>
              }
            </span>
            <span className="text-lf-muted">{c.signal.contracts} ct</span>
            <span className="text-lf-yellow tabular-nums">${c.signal.risk?.toFixed(2)} risk</span>
            <span className="text-lf-green tabular-nums">+${c.signal.profit?.toFixed(2)}</span>
          </div>
        )}

        {c.blocked_by && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-lf-yellow">
            <AlertTriangle size={12} />
            <span className="truncate">{c.blocked_by}</span>
          </div>
        )}

        {/* Expandable detail */}
        {open && (
          <div className="mt-3 pt-3 border-t border-lf-border/50 space-y-3 animate-slide-up">
            {c.reasons?.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-lf-muted mb-1">Decision</p>
                {c.reasons.map((r, i) => (
                  <p key={i} className="text-xs sm:text-sm text-lf-text leading-relaxed">{r}</p>
                ))}
              </div>
            )}
            {c.sleeves?.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] uppercase tracking-wider text-lf-muted">Sleeve Analysis</p>
                {c.sleeves.map((s, i) => (
                  <div key={i} className={`rounded-lg p-2.5 sm:p-3 text-xs sm:text-sm ${
                    s.qualifies ? 'bg-lf-green/[0.06] border border-lf-green/15' : 'bg-lf-surface border border-lf-border/50'
                  }`}>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Badge color={s.sleeve === 'A' ? 'blue' : s.sleeve === 'B' ? 'orange' : 'purple'}>
                        {s.sleeve}
                      </Badge>
                      <span className="text-xs text-lf-text">{s.name}</span>
                      <span className={`text-[10px] font-semibold ${s.qualifies ? 'text-lf-green' : 'text-lf-muted'}`}>
                        {s.qualifies ? '● QUALIFIES' : '○ No match'}
                      </span>
                    </div>
                    <p className="text-xs text-lf-text leading-relaxed">{s.reasoning}</p>
                    <div className="flex gap-3 mt-1 text-[10px] text-lf-muted tabular-nums flex-wrap">
                      <span>Base: {(s.base_rate * 100).toFixed(1)}%</span>
                      <span>Edge: {(s.edge * 100).toFixed(1)}%</span>
                      <span>Min: {(s.threshold * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2 sm:gap-3 text-[10px] text-lf-muted pt-1">
              <span>Ticker: <code className="text-lf-text break-all">{c.ticker}</code></span>
              {c.volume > 0 && <span>Vol: {c.volume.toLocaleString()}</span>}
            </div>
          </div>
        )}

        {/* Expand hint */}
        <div className="flex items-center justify-end mt-1.5 text-lf-muted">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// COMPACT TABLE ROW — For "no edge" contracts
// ═══════════════════════════════════════════════════════════════
function CompactRow({ contract: c }) {
  const teamColor = getTeamColor(c.team)
  return (
    <tr className="border-b border-lf-border/20 table-row-hover text-sm">
      <td className="py-2.5 pl-3 sm:pl-4">
        <div className="flex items-center gap-2">
          <div className="w-0.5 h-5 rounded-full shrink-0" style={{ background: teamColor }} />
          <span className="font-medium">{c.driver}</span>
        </div>
      </td>
      <td className="py-2.5">
        <Badge color={c.market === 'winner' ? 'red' : 'cyan'}>
          {c.market === 'winner' ? 'Win' : 'Pod'}
        </Badge>
      </td>
      <td className="py-2.5 text-right tabular-nums font-mono hidden sm:table-cell">{c.grid_pos ? `P${c.grid_pos}` : '—'}</td>
      <td className="py-2.5 text-right tabular-nums font-mono font-semibold">{(c.price * 100).toFixed(0)}¢</td>
      <td className="py-2.5 text-right tabular-nums font-mono text-lf-text hidden sm:table-cell">
        {c.base_rate != null ? `${(c.base_rate * 100).toFixed(0)}%` : '—'}
      </td>
      <td className={`py-2.5 text-right tabular-nums font-mono font-semibold ${
        c.edge >= 0.15 ? 'text-lf-green' : c.edge >= 0.08 ? 'text-lf-yellow' : c.edge > 0 ? 'text-lf-text' : 'text-lf-muted'
      }`}>
        {c.edge != null ? `${(c.edge * 100).toFixed(1)}%` : '—'}
      </td>
      <td className="py-2.5 text-right pr-3 sm:pr-4">
        <span className={`text-[10px] font-semibold ${
          c.decision === 'WAITING' ? 'text-lf-blue' : 'text-lf-muted'
        }`}>
          {c.decision === 'WAITING' ? 'WAIT' : 'PASS'}
        </span>
      </td>
    </tr>
  )
}

// ═══════════════════════════════════════════════════════════════
// MOBILE COMPACT CARD — For smaller screens
// ═══════════════════════════════════════════════════════════════
function MobileCompactCard({ contract: c }) {
  const teamColor = getTeamColor(c.team)
  return (
    <div className="flex items-center gap-2.5 py-2.5 border-b border-lf-border/20">
      <div className="w-0.5 h-8 rounded-full shrink-0" style={{ background: teamColor }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium">{c.driver}</span>
          <Badge color={c.market === 'winner' ? 'red' : 'cyan'}>
            {c.market === 'winner' ? 'W' : 'P'}
          </Badge>
        </div>
      </div>
      <div className="text-right tabular-nums font-mono">
        <span className="text-sm font-semibold">{(c.price * 100).toFixed(0)}¢</span>
      </div>
      <div className={`text-right tabular-nums font-mono text-xs w-12 ${
        c.edge >= 0.15 ? 'text-lf-green' : c.edge >= 0.08 ? 'text-lf-yellow' : 'text-lf-muted'
      }`}>
        {c.edge != null ? `${(c.edge * 100).toFixed(1)}%` : '—'}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// MAIN TRADING PAGE
// ═══════════════════════════════════════════════════════════════
export default function Trading() {
  const [state, setState] = useState(null)
  const [monitor, setMonitor] = useState(null)
  const [signals, setSignals] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [killStatus, setKillStatus] = useState(null)
  const [killPin, setKillPin] = useState('')
  const [showPin, setShowPin] = useState(false)
  const [killMsg, setKillMsg] = useState(null)
  const [contractsData, setContractsData] = useState(null)
  const [tab, setTab] = useState('contracts')
  const [marketFilter, setMarketFilter] = useState('all')
  const [showAllRest, setShowAllRest] = useState(false)

  const refresh = useCallback(() => {
    api.getState().then(setState).catch(console.error)
    api.getMonitorStatus().then(setMonitor).catch(console.error)
    api.getRecentSignals(50).then(setSignals).catch(console.error)
    api.getKillStatus().then(setKillStatus).catch(console.error)
    api.getAuditLog(null, 50).then(setAuditLog).catch(console.error)
    api.getContractsAnalysis().then(setContractsData).catch(console.error)
  }, [])

  useEffect(() => {
    refresh()
    const i = setInterval(refresh, 10000)
    return () => clearInterval(i)
  }, [refresh])

  const handleKill = async () => {
    if (!killPin || killPin.length < 6) { setKillMsg({ t: 'err', m: 'Enter 6-digit PIN' }); return }
    try {
      const res = killStatus?.halted ? await api.unkill(killPin) : await api.kill(killPin)
      setKillMsg({ t: 'ok', m: res.message }); setKillPin(''); refresh()
    } catch(e) { setKillMsg({ t: 'err', m: e.message }) }
  }

  const isHalted = killStatus?.halted || state?.halted
  const contracts = contractsData?.contracts || []

  const filtered = marketFilter === 'all' ? contracts
    : contracts.filter(c => c.market === marketFilter)

  const actionable = filtered.filter(c => c.decision === 'TRADE' || c.decision === 'BLOCKED')
  const rest = filtered.filter(c => c.decision !== 'TRADE' && c.decision !== 'BLOCKED')
  const restToShow = showAllRest ? rest : rest.slice(0, 20)

  return (
    <div className="space-y-4 sm:space-y-5 animate-fade-in">
      {/* ── Halt Banner ── */}
      {isHalted && (
        <div className="flex items-center gap-3 bg-lf-red/10 border border-lf-red/20 rounded-xl px-4 py-3">
          <ShieldAlert size={18} className="text-lf-red shrink-0" />
          <div className="min-w-0">
            <p className="text-sm text-lf-red font-semibold">Trading Halted</p>
            <p className="text-xs text-lf-red/70 truncate">{killStatus?.reason || 'Kill switch active'}</p>
          </div>
        </div>
      )}

      {/* ── Monitor Bar ── */}
      <Card padding="p-3 sm:p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <div className={`p-1.5 sm:p-2 rounded-lg shrink-0 ${monitor?.active ? 'bg-lf-green/10' : 'bg-lf-surface'}`}>
              <Radio size={14} className={monitor?.active ? 'text-lf-green' : 'text-lf-muted'} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs sm:text-sm font-semibold truncate">Monitor</span>
                <Badge color={monitor?.mode === 'weekend_active' ? 'green' : 'blue'} dot>
                  {monitor?.mode === 'weekend_active' ? 'LIVE' : 'SCAN'}
                </Badge>
              </div>
              <p className="text-[10px] text-lf-muted mt-0.5 truncate">
                {monitor?.poll_count || 0} polls
                {monitor?.last_poll && ` · ${new Date(monitor.last_poll).toLocaleTimeString()}`}
              </p>
            </div>
          </div>
          {/* Mobile: condensed stats */}
          <div className="hidden sm:flex items-center gap-4 text-xs text-lf-muted shrink-0">
            {contractsData && (
              <>
                <span>💰 <strong className="text-white">${contractsData.bankroll?.toFixed(2)}</strong></span>
                <span>📊 <strong className="text-lf-yellow">${contractsData.weekend_risk?.toFixed(2)}</strong>
                  /{contractsData.max_weekend_risk?.toFixed(2)}</span>
              </>
            )}
          </div>
        </div>
        {/* Mobile stats row */}
        {contractsData && (
          <div className="sm:hidden flex items-center gap-3 mt-2 pt-2 border-t border-lf-border/30 text-[11px] text-lf-muted">
            <span>Bank: <strong className="text-white">${contractsData.bankroll?.toFixed(2)}</strong></span>
            <span>Risk: <strong className="text-lf-yellow">${contractsData.weekend_risk?.toFixed(2)}</strong>/${contractsData.max_weekend_risk?.toFixed(2)}</span>
            <span>Bet: <strong className="text-lf-text">${contractsData.bet_size?.toFixed(2)}</strong></span>
          </div>
        )}
      </Card>

      {/* ── Tab Bar (scrollable on mobile) ── */}
      <div className="overflow-x-auto scrollbar-none -mx-3 px-3 sm:mx-0 sm:px-0">
        <Tabs
          tabs={[
            { id: 'contracts', icon: BarChart3, label: 'Contracts', badge: contracts.length || null },
            { id: 'signals', icon: Zap, label: 'Signals' },
            { id: 'audit', icon: Activity, label: 'Audit' },
            { id: 'kill', icon: ShieldAlert, label: 'Kill' },
          ]}
          active={tab}
          onChange={setTab}
        />
      </div>

      {/* ════════════════════════════════════════════════════════ */}
      {/* CONTRACTS TAB                                          */}
      {/* ════════════════════════════════════════════════════════ */}
      {tab === 'contracts' && (
        <div className="space-y-4 sm:space-y-5">
          {contractsData && !contractsData.has_prices && (
            <Card>
              <EmptyState icon={BarChart3} title="No Kalshi contracts yet"
                description={contractsData.is_weekend
                  ? "Race weekend active. Polling every 5 minutes."
                  : `Next: ${contractsData.race?.name || 'TBD'} on ${contractsData.race?.date || 'TBD'}.`
                } />
            </Card>
          )}

          {contractsData?.has_prices && !contractsData.has_grid && (
            <div className="flex items-center gap-3 bg-lf-blue/[0.07] border border-lf-blue/20 rounded-xl px-4 py-3">
              <Clock size={18} className="text-lf-blue shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-lf-blue font-semibold">Waiting for Qualifying</p>
                <p className="text-xs text-lf-blue/60">{contracts.length} contracts loaded.</p>
              </div>
            </div>
          )}

          {/* Market type filter */}
          {contracts.length > 0 && (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <Filter size={13} className="text-lf-muted shrink-0" />
                <div className="flex gap-1">
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'winner', label: 'Winner' },
                    { id: 'podium', label: 'Podium' },
                  ].map(f => (
                    <button key={f.id} onClick={() => setMarketFilter(f.id)}
                      className={`px-2.5 sm:px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        marketFilter === f.id
                          ? 'bg-lf-card text-white border border-lf-border'
                          : 'text-lf-muted hover:text-white'
                      }`}>
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
              {contractsData?.has_grid && (
                <div className="flex items-center gap-2 text-[10px] sm:text-xs shrink-0">
                  <span className="text-lf-green font-semibold">{actionable.filter(c=>c.decision==='TRADE').length} trade</span>
                  <span className="text-lf-yellow font-semibold">{actionable.filter(c=>c.decision==='BLOCKED').length} blocked</span>
                  <span className="text-lf-muted hidden sm:inline">{rest.length} pass</span>
                </div>
              )}
            </div>
          )}

          {/* ACTIONABLE: Hero cards */}
          {actionable.length > 0 && (
            <div className="space-y-2 sm:space-y-3">
              <h3 className="text-xs uppercase tracking-wider text-lf-green font-semibold flex items-center gap-2">
                <Zap size={12} /> Actionable
              </h3>
              {actionable.map((c, i) => (
                <HeroContract key={c.ticker + i} contract={c} />
              ))}
            </div>
          )}

          {/* REST: Table on desktop, cards on mobile */}
          {rest.length > 0 && (
            <div>
              <h3 className="text-xs uppercase tracking-wider text-lf-muted font-semibold mb-2 sm:mb-3 flex items-center gap-2">
                <Search size={12} /> All Contracts ({rest.length})
              </h3>
              {/* Desktop table */}
              <Card padding="p-0" className="hidden sm:block">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
                        <th className="text-left py-3 pl-4 font-medium">Driver</th>
                        <th className="text-left py-3 px-2 font-medium">Market</th>
                        <th className="text-right py-3 px-2 font-medium hidden sm:table-cell">Grid</th>
                        <th className="text-right py-3 px-2 font-medium">Price</th>
                        <th className="text-right py-3 px-2 font-medium hidden sm:table-cell">Fair</th>
                        <th className="text-right py-3 px-2 font-medium">Edge</th>
                        <th className="text-right py-3 pr-4 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {restToShow.map((c, i) => (
                        <CompactRow key={c.ticker + i} contract={c} />
                      ))}
                    </tbody>
                  </table>
                </div>
                {rest.length > 20 && !showAllRest && (
                  <div className="border-t border-lf-border p-3 text-center">
                    <button onClick={() => setShowAllRest(true)}
                      className="text-xs text-lf-text hover:text-white font-medium">
                      Show all {rest.length} ↓
                    </button>
                  </div>
                )}
              </Card>
              {/* Mobile compact cards */}
              <Card padding="px-3 py-1" className="sm:hidden">
                {restToShow.map((c, i) => (
                  <MobileCompactCard key={c.ticker + i} contract={c} />
                ))}
                {rest.length > 20 && !showAllRest && (
                  <div className="py-3 text-center">
                    <button onClick={() => setShowAllRest(true)}
                      className="text-xs text-lf-text hover:text-white font-medium">
                      Show all {rest.length} ↓
                    </button>
                  </div>
                )}
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════ */}
      {/* SIGNALS TAB                                            */}
      {/* ════════════════════════════════════════════════════════ */}
      {tab === 'signals' && (
        <Card>
          <SectionTitle sub="Read-only feed. Trades placed automatically.">Signals</SectionTitle>
          {signals.length === 0 ? (
            <EmptyState icon={Zap} title="No signals yet"
              description="Signals appear during race weekends." />
          ) : (
            <div className="space-y-2">
              {signals.map((s, i) => (
                <div key={s.id || i} className={`rounded-lg p-3 sm:p-4 border transition-colors ${
                  s.acted_on ? 'bg-lf-green/[0.04] border-lf-green/20' :
                  s.skip_reason ? 'bg-lf-surface border-lf-border/50' :
                  'bg-lf-yellow/[0.04] border-lf-yellow/20'
                }`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Badge color={s.sleeve === 'A' ? 'blue' : s.sleeve === 'B' ? 'orange' : 'purple'}>
                          {s.sleeve}
                        </Badge>
                        <span className="text-xs sm:text-sm font-semibold truncate">{s.label}</span>
                        {s.acted_on ? <Badge color="green">TRADED</Badge> :
                         s.skip_reason ? <Badge color="gray">SKIP</Badge> :
                         <Badge color="yellow">PENDING</Badge>}
                      </div>
                      <p className="text-xs text-lf-text mt-1 leading-relaxed line-clamp-2">{s.reasoning}</p>
                      {s.skip_reason && (
                        <p className="text-[11px] text-lf-muted mt-1 truncate">Skip: {s.skip_reason}</p>
                      )}
                      <div className="flex gap-3 mt-1.5 text-[11px] text-lf-muted tabular-nums flex-wrap">
                        <span>Edge: <strong className="text-lf-green">{(s.edge * 100).toFixed(1)}%</strong></span>
                        <span>Risk: <strong className="text-lf-yellow">${s.risk?.toFixed(2)}</strong></span>
                        <span>Profit: <strong className="text-lf-green">+${s.potential_profit?.toFixed(2)}</strong></span>
                      </div>
                    </div>
                    <div className="text-right shrink-0 hidden sm:block">
                      <p className="text-[10px] text-lf-muted">{s.created_at ? new Date(s.created_at).toLocaleString() : ''}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ════════════════════════════════════════════════════════ */}
      {/* AUDIT TAB                                              */}
      {/* ════════════════════════════════════════════════════════ */}
      {tab === 'audit' && (
        <Card>
          <SectionTitle>Audit Log</SectionTitle>
          {auditLog.length === 0 ? (
            <EmptyState icon={Activity} title="No entries yet" />
          ) : (
            <>
              {/* Mobile: card layout */}
              <div className="sm:hidden space-y-2">
                {auditLog.map((a, i) => (
                  <div key={a.id || i} className="border-b border-lf-border/20 pb-2">
                    <div className="flex items-center gap-2 mb-0.5">
                      <Badge color={
                        a.event_type === 'TRADE_PLACED' ? 'green' :
                        a.event_type === 'TRADE_SETTLED' ? 'blue' :
                        a.event_type === 'ERROR' || a.event_type === 'KILL' ? 'red' : 'gray'
                      }>{a.event_type}</Badge>
                      <span className="text-[10px] text-lf-muted tabular-nums">
                        {a.created_at ? new Date(a.created_at).toLocaleTimeString() : ''}
                      </span>
                    </div>
                    <p className="text-xs text-lf-text truncate">{a.detail}</p>
                  </div>
                ))}
              </div>
              {/* Desktop: table */}
              <div className="hidden sm:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
                      <th className="text-left py-3 font-medium">Time</th>
                      <th className="text-left py-3 font-medium">Event</th>
                      <th className="text-left py-3 font-medium">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLog.map((a, i) => (
                      <tr key={a.id || i} className="border-b border-lf-border/20 table-row-hover">
                        <td className="py-2.5 text-xs text-lf-muted tabular-nums whitespace-nowrap">
                          {a.created_at ? new Date(a.created_at).toLocaleString() : ''}
                        </td>
                        <td className="py-2.5">
                          <Badge color={
                            a.event_type === 'TRADE_PLACED' ? 'green' :
                            a.event_type === 'TRADE_SETTLED' ? 'blue' :
                            a.event_type === 'ERROR' || a.event_type === 'KILL' ? 'red' : 'gray'
                          }>{a.event_type}</Badge>
                        </td>
                        <td className="py-2.5 text-xs text-lf-text">{a.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>
      )}

      {/* ════════════════════════════════════════════════════════ */}
      {/* KILL SWITCH TAB                                        */}
      {/* ════════════════════════════════════════════════════════ */}
      {tab === 'kill' && (
        <Card>
          <div className="flex items-center gap-3 mb-5 sm:mb-6">
            <div className={`p-2.5 sm:p-3 rounded-xl shrink-0 ${isHalted ? 'bg-lf-red/10' : 'bg-lf-green/10'}`}>
              {isHalted ? <ShieldAlert size={20} className="text-lf-red" /> : <ShieldCheck size={20} className="text-lf-green" />}
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold">{isHalted ? 'Halted' : 'Active'}</h2>
              <p className="text-xs text-lf-text">
                {isHalted ? 'No new trades. Positions settle naturally.' : 'Auto-trades on signals.'}
              </p>
            </div>
          </div>

          {killMsg && (
            <div className={`rounded-lg p-3 text-sm mb-4 ${
              killMsg.t === 'err' ? 'bg-lf-red/10 text-lf-red border border-lf-red/20' : 'bg-lf-green/10 text-lf-green border border-lf-green/20'
            }`}>{killMsg.m}</div>
          )}

          <div className="bg-lf-surface rounded-xl p-4 sm:p-5 border border-lf-border">
            <p className="text-sm text-lf-text mb-3 sm:mb-4">
              {isHalted ? 'Enter PIN to resume:' : 'Enter PIN to halt:'}
            </p>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <div className="relative">
                <input
                  type={showPin ? 'text' : 'password'}
                  value={killPin}
                  onChange={e => setKillPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="6-digit PIN"
                  maxLength={6}
                  className="w-full sm:w-40 bg-lf-dark border border-lf-border rounded-lg px-4 py-2.5 text-sm font-mono text-center tracking-[0.3em] focus:border-lf-red focus:outline-none focus:ring-1 focus:ring-lf-red/30 transition-all"
                />
                <button onClick={() => setShowPin(!showPin)}
                  className="absolute right-3 top-2.5 text-lf-muted hover:text-white">
                  {showPin ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <button onClick={handleKill}
                className={`px-6 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                  isHalted
                    ? 'bg-lf-green/15 hover:bg-lf-green/25 text-lf-green border border-lf-green/30'
                    : 'bg-lf-red hover:bg-lf-red/90 text-white shadow-glow-red'
                }`}>
                {isHalted ? 'Resume' : 'KILL SWITCH'}
              </button>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
