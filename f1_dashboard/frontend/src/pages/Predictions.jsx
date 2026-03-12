import React, { useState, useEffect } from 'react'
import { Brain, AlertTriangle, TrendingUp, Trophy, Zap, Clock, ChevronDown, ChevronUp, Target, BarChart3 } from 'lucide-react'
import { api } from '../api'
import { AnimatedBar, LivePulse, StaggerChildren, AnimatedCounter, RacingStripe, GridBadge } from '../components/Animations'

const TEAM_COLORS = {
  'Red Bull': '#3671C6', 'Mercedes': '#27F4D2', 'Ferrari': '#E8002D',
  'McLaren': '#FF8000', 'Aston Martin': '#229971', 'Alpine': '#FF87BC',
  'Williams': '#64C4FF', 'RB': '#6692FF', 'Haas': '#B6BABD',
  'Sauber': '#52E252', 'Kick Sauber': '#52E252',
}

function getTeamColor(team) {
  if (!team) return '#666'
  for (const [k, v] of Object.entries(TEAM_COLORS)) {
    if (team.toLowerCase().includes(k.toLowerCase())) return v
  }
  return '#666'
}

export default function Predictions() {
  const [predictions, setPredictions] = useState(null)
  const [contracts, setContracts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedDriver, setExpandedDriver] = useState(null)

  useEffect(() => {
    Promise.all([
      api.getPredictions().catch(() => null),
      api.getContractsAnalysis().catch(() => null),
    ]).then(([p, c]) => {
      setPredictions(p)
      setContracts(c)
      setLoading(false)
    })
  }, [])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-48 rounded-2xl bg-lf-surface animate-pulse" />
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="h-32 rounded-xl bg-lf-surface animate-pulse" />)}
        </div>
      </div>
    )
  }

  const race = predictions?.race || {}
  const circuit = predictions?.circuit || {}
  const drivers = predictions?.predictions || predictions?.drivers || []
  const insights = predictions?.insights || []
  const contractList = contracts?.contracts || []
  
  // Merge contract prices with predictions
  const driversWithPrices = drivers.map(d => {
    const driverCode = d.code || d.driver
    const winContract = contractList.find(c => c.driver_code === driverCode && c.market_type === 'winner')
    const podContract = contractList.find(c => c.driver_code === driverCode && c.market_type === 'podium')
    return { ...d, driverCode, winContract, podContract }
  })

  const hasQualifying = contracts?.qualifying_available
  // win_pct is 0-100 from API
  const maxWinProb = Math.max(...drivers.map(d => d.win_pct || d.win_prob || 0), 0.01)

  return (
    <div className="space-y-6">
      {/* ═══ Race Weekend Hero ═══ */}
      <div className="relative overflow-hidden rounded-2xl border border-lf-border bg-gradient-to-br from-lf-surface via-lf-surface to-lf-red/5">
        {/* Animated accent line at top */}
        <div className="absolute top-0 left-0 right-0 h-[2px]">
          <div className="h-full bg-gradient-to-r from-transparent via-lf-red to-transparent"
            style={{ animation: 'sweepRight 4s ease-in-out infinite' }} />
        </div>
        
        <div className="p-4 sm:p-8">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
                <LivePulse color="red" size={10} />
                <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-widest text-lf-red">
                  {hasQualifying ? 'Grid Locked' : 'Pre-Qualifying'}
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold mb-1">
                {race.name || 'Next Race'} <span className="text-lf-red">{race.round ? `R${race.round}` : ''}</span>
              </h1>
              <p className="text-lf-text text-xs sm:text-sm">
                {race.date || 'Date TBD'} · {race.circuit || 'Circuit TBD'}
              </p>
            </div>
            
            {/* Circuit Stats — shown as row on mobile */}
            <div className="flex sm:hidden gap-4 text-center mt-2">
              {circuit.sc_probability != null && (
                <div>
                  <div className="text-2xl font-bold font-mono text-yellow-400">
                    <AnimatedCounter value={circuit.sc_probability} suffix="%" decimals={0} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-lf-muted mt-1">SC Prob</div>
                </div>
              )}
              {circuit.drs_zones != null && (
                <div>
                  <div className="text-2xl font-bold font-mono text-blue-400">
                    <AnimatedCounter value={circuit.drs_zones} decimals={0} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-lf-muted mt-1">DRS Zones</div>
                </div>
              )}
              {circuit.overtaking_rating != null && (
                <div>
                  <div className="text-2xl font-bold font-mono text-green-400">
                    <AnimatedCounter value={circuit.overtaking_rating} suffix="/10" decimals={1} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-lf-muted mt-1">Overtaking</div>
                </div>
              )}
            </div>
            {/* Desktop circuit stats */}
            <div className="hidden sm:flex gap-6 text-center">
              {circuit.sc_probability != null && (
                <div>
                  <div className="text-2xl font-bold font-mono text-yellow-400">
                    <AnimatedCounter value={circuit.sc_probability} suffix="%" decimals={0} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-lf-muted mt-1">SC Prob</div>
                </div>
              )}
              {circuit.drs_zones != null && (
                <div>
                  <div className="text-2xl font-bold font-mono text-blue-400">
                    <AnimatedCounter value={circuit.drs_zones} decimals={0} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-lf-muted mt-1">DRS Zones</div>
                </div>
              )}
              {circuit.overtaking_rating != null && (
                <div>
                  <div className="text-2xl font-bold font-mono text-green-400">
                    <AnimatedCounter value={circuit.overtaking_rating} suffix="/10" decimals={1} />
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-lf-muted mt-1">Overtaking</div>
                </div>
              )}
            </div>
          </div>

          {/* Insights */}
          {insights.length > 0 && (
            <div className="flex flex-wrap gap-1.5 sm:gap-2 mt-3 sm:mt-5">
              {insights.map((ins, i) => (
                <span key={i} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border
                  ${(ins.type === 'warning' || ins.type === 'chaos') ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                    (ins.type === 'danger' || ins.type === 'caution') ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                    'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                  {(ins.type === 'warning' || ins.type === 'chaos') ? <AlertTriangle size={12} /> :
                   (ins.type === 'danger' || ins.type === 'caution') ? <Zap size={12} /> : <TrendingUp size={12} />}
                  {ins.title || ins.text}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <RacingStripe />

      {/* ═══ Win Probability Chart ═══ */}
      <div className="rounded-2xl border border-lf-border bg-lf-surface p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4 sm:mb-6 gap-2">
          <h2 className="text-base sm:text-lg font-bold flex items-center gap-2">
            <Trophy size={18} className="text-lf-red" />
            Win Probabilities
          </h2>
          <span className="text-[10px] sm:text-xs text-lf-muted text-right">
            {hasQualifying ? 'Grid + historical' : 'Power rankings'}
          </span>
        </div>

        <StaggerChildren delay={40} className="space-y-2">
          {driversWithPrices.slice(0, 12).map((d, i) => {
            const teamColor = getTeamColor(d.team)
            const winPct = d.win_pct || (d.win_prob ? d.win_prob * 100 : 0)
            const kalshiWin = d.winContract?.price ? (d.winContract.price * 100) : null
            const edge = kalshiWin != null ? (winPct - kalshiWin) : null
            
            return (
              <div key={d.driverCode} className="group">
                <div className="flex items-center gap-3 cursor-pointer hover:bg-white/[0.02] rounded-lg p-2 -m-2 transition-colors"
                  onClick={() => setExpandedDriver(expandedDriver === d.driverCode ? null : d.driverCode)}>
                  {/* Position */}
                  <span className="text-xs font-mono text-lf-muted w-5 text-right">{i + 1}.</span>
                  
                  {/* Team color bar */}
                  <div className="w-1 h-8 rounded-full" style={{ backgroundColor: teamColor }} />
                  
                  {/* Driver */}
                  <div className="w-16 sm:w-28">
                    <div className="font-semibold text-xs sm:text-sm truncate">{d.name || d.driverCode}</div>
                    <div className="text-[10px] text-lf-muted truncate hidden sm:block">{d.team || ''}</div>
                  </div>
                  
                  {/* Bar */}
                  <div className="flex-1 flex items-center gap-3">
                    <div className="flex-1 relative">
                      <AnimatedBar value={winPct} max={maxWinProb} color={teamColor} height={20} delay={i * 50} />
                      {/* Model prob label */}
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] font-mono font-semibold text-white/90">
                        {winPct.toFixed(1)}%
                      </span>
                    </div>
                    
                    {/* Kalshi price comparison */}
                    {kalshiWin != null && (
                      <div className="w-20 text-right">
                        <div className="text-xs font-mono">{kalshiWin.toFixed(0)}¢</div>
                        <div className={`text-[10px] font-mono font-semibold ${
                          edge > 5 ? 'text-green-400' : edge < -5 ? 'text-red-400' : 'text-lf-muted'}`}>
                          {edge > 0 ? '+' : ''}{edge?.toFixed(1)}%
                        </div>
                      </div>
                    )}
                    
                    {/* Expand arrow */}
                    {expandedDriver === d.driverCode ? <ChevronUp size={14} className="text-lf-muted" /> : <ChevronDown size={14} className="text-lf-muted" />}
                  </div>
                </div>
                
                {/* Expanded detail */}
                {expandedDriver === d.driverCode && (
                  <div className="ml-2 sm:ml-12 mt-2 mb-3 p-3 sm:p-4 rounded-xl bg-lf-black/50 border border-lf-border/50 space-y-3"
                    style={{ animation: 'fadeSlideUp 0.3s ease-out' }}>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                      <div>
                        <div className="text-lf-muted mb-1">Win Probability</div>
                        <div className="font-mono font-bold text-lg" style={{ color: teamColor }}>
                          {winPct.toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-lf-muted mb-1">Podium Probability</div>
                        <div className="font-mono font-bold text-lg">
                          {(d.podium_pct || (d.podium_prob ? d.podium_prob * 100 : 0)).toFixed(1)}%
                        </div>
                      </div>
                      {d.winContract && (
                        <div>
                          <div className="text-lf-muted mb-1">Kalshi Win Price</div>
                          <div className="font-mono font-bold text-lg">
                            {(d.winContract.price * 100).toFixed(0)}¢
                          </div>
                        </div>
                      )}
                      {d.podContract && (
                        <div>
                          <div className="text-lf-muted mb-1">Kalshi Podium Price</div>
                          <div className="font-mono font-bold text-lg">
                            {(d.podContract.price * 100).toFixed(0)}¢
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Model reasoning */}
                    {(d.winContract?.analysis || d.podContract?.analysis) && (
                      <div className="pt-3 border-t border-lf-border/30">
                        <div className="text-[10px] uppercase tracking-wider text-lf-muted mb-2">Model Analysis</div>
                        {d.winContract?.analysis?.sleeves?.map((s, j) => (
                          <div key={j} className="flex items-start gap-2 text-xs mb-1">
                            <span className={s.action ? 'text-green-400' : 'text-lf-muted'}>
                              {s.action ? '✅' : '—'}
                            </span>
                            <span className="text-lf-text">
                              <strong>{s.sleeve}:</strong> {s.reason}
                            </span>
                          </div>
                        ))}
                        {d.podContract?.analysis?.sleeves?.map((s, j) => (
                          <div key={`p${j}`} className="flex items-start gap-2 text-xs mb-1">
                            <span className={s.action ? 'text-green-400' : 'text-lf-muted'}>
                              {s.action ? '✅' : '—'}
                            </span>
                            <span className="text-lf-text">
                              <strong>{s.sleeve}:</strong> {s.reason}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {!hasQualifying && (
                      <div className="text-[10px] text-lf-muted italic pt-2 border-t border-lf-border/30">
                        ⏳ Full sleeve analysis available after qualifying — grid position determines base rates
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </StaggerChildren>
      </div>

      {/* ═══ Kalshi vs Model Comparison ═══ */}
      {contractList.length > 0 && (
        <div className="rounded-2xl border border-lf-border bg-lf-surface p-4 sm:p-6">
          <h2 className="text-base sm:text-lg font-bold flex items-center gap-2 mb-4">
            <BarChart3 size={18} className="text-lf-red" />
            <span>Model vs Market</span>
          </h2>
          
          {(() => {
            const edged = contractList
              .filter(c => c.analysis?.decision === 'TRADE' || (c.analysis?.edge && Math.abs(c.analysis.edge) > 0.05))
              .sort((a, b) => Math.abs(b.analysis?.edge || 0) - Math.abs(a.analysis?.edge || 0))
            
            if (edged.length === 0) {
              return (
                <div className="text-center py-8 text-lf-muted">
                  <Target size={24} className="mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No significant edges detected right now</p>
                  <p className="text-xs mt-1">Edges typically appear after qualifying when the grid is locked</p>
                </div>
              )
            }
            
            return (
              <div className="space-y-2">
                {edged.slice(0, 10).map((c, i) => {
                  const edge = c.analysis?.edge || 0
                  const isPositive = edge > 0
                  return (
                    <div key={i} className="flex items-center gap-2 sm:gap-3 p-2.5 sm:p-3 rounded-lg bg-lf-black/30 border border-lf-border/30">
                      <div className="w-0.5 h-8 sm:h-10 rounded-full shrink-0" style={{ backgroundColor: getTeamColor(c.team) }} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-semibold text-sm">{c.driver_code}</span>
                          <span className="text-[10px] text-lf-muted">{c.market_type}</span>
                        </div>
                        <div className="flex gap-2 text-[10px] sm:text-xs text-lf-muted mt-0.5">
                          <span>{(c.price * 100).toFixed(0)}¢</span>
                          <span>Fair: {((c.analysis?.base_rate || 0) * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className={`font-mono font-bold text-sm shrink-0 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                        {isPositive ? '+' : ''}{(edge * 100).toFixed(1)}%
                      </div>
                      <span className={`text-[10px] px-1.5 sm:px-2 py-0.5 rounded-full font-semibold shrink-0
                        ${c.analysis?.decision === 'TRADE' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                          'bg-white/5 text-lf-muted border border-lf-border/30'}`}>
                        {c.analysis?.decision || 'PASS'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )
          })()}
        </div>
      )}

      {/* ═══ When no data at all ═══ */}
      {!predictions && contractList.length === 0 && (
        <div className="rounded-2xl border border-lf-border bg-lf-surface p-12 text-center">
          <Clock size={40} className="mx-auto mb-4 text-lf-muted opacity-40" />
          <h2 className="text-xl font-bold mb-2">Waiting for Race Weekend</h2>
          <p className="text-sm text-lf-muted max-w-md mx-auto">
            Predictions appear when we're within a race weekend window.
            The system monitors the calendar and will activate automatically.
          </p>
        </div>
      )}

      <style>{`
        @keyframes sweepRight {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
