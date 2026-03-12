import React, { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
  BarChart, Bar, Cell, Area, AreaChart
} from 'recharts'
import { Card, StatCard, SectionTitle, Badge, Tabs, Loader, EmptyState } from '../components/Card'
import { TrendingUp, Target, AlertTriangle, Hash, Sliders, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../api'

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-lf-card/95 backdrop-blur border border-lf-border rounded-lg px-3 py-2 shadow-lg">
      <p className="text-[10px] text-lf-muted">{label}</p>
      <p className="text-sm font-bold tabular-nums">{typeof payload[0].value === 'number' ? `$${payload[0].value.toFixed(2)}` : payload[0].value}</p>
    </div>
  )
}

export default function Backtest() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [showBuilder, setShowBuilder] = useState(false)

  const [betSize, setBetSize] = useState(5.0)
  const [sleeveA, setSleeveA] = useState(true)
  const [sleeveB, setSleeveB] = useState(true)
  const [sleeveE, setSleeveE] = useState(true)
  const [edgeA, setEdgeA] = useState(15)
  const [edgeB, setEdgeB] = useState(8)
  const [edgeE, setEdgeE] = useState(10)

  const runBacktest = useCallback(() => {
    setLoading(true)
    api.getBacktest({ betSize, sleeveA, sleeveB, sleeveE, edgeA: edgeA/100, edgeB: edgeB/100, edgeE: edgeE/100 })
      .then(setData).catch(console.error).finally(() => setLoading(false))
  }, [betSize, sleeveA, sleeveB, sleeveE, edgeA, edgeB, edgeE])

  useEffect(() => { runBacktest() }, [runBacktest])

  if (loading && !data) return <Loader />
  if (!data) return <EmptyState icon={AlertTriangle} title="Failed to load backtest" />

  const filtered = filter === 'all' ? data.trades : data.trades.filter(t => t.sleeve === filter)
  const curveData = data.curve.map((v, i) => ({ trade: i, bankroll: v }))
  const byRace = {}
  data.trades.forEach(t => { byRace[t.race] = (byRace[t.race] || 0) + t.pnl })
  const racePnl = Object.entries(byRace).map(([race, pnl]) => ({ race: race.replace(' Grand Prix', '').replace('Grand Prix', ''), pnl: Math.round(pnl * 100) / 100 }))

  const isDefault = betSize === 5 && sleeveA && sleeveB && sleeveE && edgeA === 15 && edgeB === 8 && edgeE === 10

  return (
    <div className="space-y-4 sm:space-y-5 animate-fade-in">
      {/* ── Strategy Builder ── */}
      <Card>
        <button className="w-full flex items-center justify-between" onClick={() => setShowBuilder(!showBuilder)}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="p-2 rounded-lg bg-lf-yellow/10 shrink-0">
              <Sliders size={16} className="text-lf-yellow" />
            </div>
            <div className="text-left min-w-0">
              <h2 className="text-sm font-semibold">Strategy Builder</h2>
              <p className="text-[11px] text-lf-muted truncate">
                {isDefault ? 'Default (verified)' : 'Custom — what-if mode'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {!isDefault && <Badge color="yellow">Modified</Badge>}
            {showBuilder ? <ChevronUp size={16} className="text-lf-muted" /> : <ChevronDown size={16} className="text-lf-muted" />}
          </div>
        </button>

        {showBuilder && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-5 pt-4 sm:pt-5 mt-3 sm:mt-4 border-t border-lf-border animate-slide-up">
            <div>
              <label className="text-[10px] sm:text-[11px] uppercase tracking-wider text-lf-muted block mb-1.5 sm:mb-2">Bet Size</label>
              <div className="bg-lf-surface rounded-lg p-2.5 sm:p-3 border border-lf-border/50">
                <p className="text-lg sm:text-xl font-bold tabular-nums">${betSize.toFixed(1)}</p>
                <input type="range" min={1} max={15} step={0.5} value={betSize}
                  onChange={e => setBetSize(parseFloat(e.target.value))} className="w-full mt-2" />
              </div>
            </div>
            <div>
              <label className="text-[10px] sm:text-[11px] uppercase tracking-wider text-lf-muted block mb-1.5 sm:mb-2">Sleeves</label>
              <div className="flex gap-1.5 sm:gap-2">
                {[
                  { k: 'A', v: sleeveA, s: setSleeveA, c: 'blue' },
                  { k: 'B', v: sleeveB, s: setSleeveB, c: 'orange' },
                  { k: 'E', v: sleeveE, s: setSleeveE, c: 'purple' },
                ].map(x => (
                  <button key={x.k} onClick={() => x.s(!x.v)}
                    className={`flex-1 py-2 sm:py-2.5 rounded-lg text-xs font-semibold transition-all border ${
                      x.v ? `bg-lf-${x.c}/15 text-lf-${x.c} border-lf-${x.c}/30` : 'bg-lf-surface text-lf-muted border-lf-border'
                    }`}>
                    {x.k}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2 sm:space-y-3">
              <div>
                <label className="text-[10px] text-lf-muted block mb-1">A: <strong className="text-lf-blue">{edgeA}%</strong></label>
                <input type="range" min={5} max={40} value={edgeA} onChange={e => setEdgeA(+e.target.value)} className="w-full" disabled={!sleeveA} />
              </div>
              <div>
                <label className="text-[10px] text-lf-muted block mb-1">B: <strong className="text-lf-orange">{edgeB}%</strong></label>
                <input type="range" min={3} max={25} value={edgeB} onChange={e => setEdgeB(+e.target.value)} className="w-full" disabled={!sleeveB} />
              </div>
            </div>
            <div className="space-y-2 sm:space-y-3">
              <div>
                <label className="text-[10px] text-lf-muted block mb-1">E: <strong className="text-lf-purple">{edgeE}%</strong></label>
                <input type="range" min={5} max={30} value={edgeE} onChange={e => setEdgeE(+e.target.value)} className="w-full" disabled={!sleeveE} />
              </div>
              {!isDefault && (
                <button onClick={() => { setBetSize(5); setSleeveA(true); setSleeveB(true); setSleeveE(true); setEdgeA(15); setEdgeB(8); setEdgeE(10) }}
                  className="text-xs text-lf-red hover:text-lf-red-glow font-medium transition-colors">
                  ← Reset defaults
                </button>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* ── Stats ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
        <StatCard label="Final" value={`$${data.final_bankroll}`} icon={TrendingUp}
          color={data.final_bankroll > 100 ? 'green' : 'red'}
          sub={`${data.total_return_pct > 0 ? '+' : ''}${data.total_return_pct}%`} />
        <StatCard label="Win Rate" value={`${data.win_rate}%`} icon={Target}
          sub={`${data.wins}W/${data.total_trades - data.wins}L`} />
        <StatCard label="Drawdown" value={`${data.max_drawdown_pct}%`} icon={AlertTriangle}
          color={data.max_drawdown_pct > 30 ? 'red' : 'yellow'} />
        <StatCard label="Trades" value={data.total_trades} icon={Hash} sub="2025 season" />
      </div>

      {/* ── Equity Curve ── */}
      <Card>
        <SectionTitle sub={`$100 → $${data.final_bankroll} over ${data.total_trades} trades`}>Equity Curve</SectionTitle>
        <div className="-mx-2 sm:mx-0">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={curveData}>
              <defs>
                <linearGradient id="btFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#E10600" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#E10600" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="trade" tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} domain={['auto', 'auto']} width={35} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={100} stroke="#2A2A3A" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="bankroll" stroke="#E10600" strokeWidth={2} fill="url(#btFill)"
                dot={{ fill: '#E10600', r: 1.5, strokeWidth: 0 }} activeDot={{ r: 4, fill: '#E10600', stroke: '#fff', strokeWidth: 2 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* ── P&L by Race ── */}
      <Card>
        <SectionTitle sub="Green = profit, Red = loss">P&L by Race</SectionTitle>
        <div className="-mx-2 sm:mx-0">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={racePnl}>
              <XAxis dataKey="race" tick={{ fill: '#3A3A4D', fontSize: 8 }} tickLine={false} axisLine={false}
                angle={-45} textAnchor="end" height={55} interval={0} />
              <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} width={30} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={0} stroke="#2A2A3A" />
              <Bar dataKey="pnl" radius={[3, 3, 0, 0]} maxBarSize={24}>
                {racePnl.map((r, i) => (
                  <Cell key={i} fill={r.pnl >= 0 ? '#00E676' : '#E10600'} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* ── Trade Log ── */}
      <Card>
        <div className="flex items-center justify-between mb-3 sm:mb-4">
          <SectionTitle sub={`${filtered.length} trades`}>Trade Log</SectionTitle>
          <div className="flex gap-0.5 sm:gap-1">
            {['all', 'A', 'B', 'E'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-md text-[10px] sm:text-xs font-medium transition-all border ${
                  filter === f
                    ? 'bg-lf-card text-white border-lf-border'
                    : 'text-lf-muted hover:text-white border-transparent'
                }`}>
                {f === 'all' ? 'All' : f}
              </button>
            ))}
          </div>
        </div>
        {/* Mobile: card layout */}
        <div className="sm:hidden space-y-1.5">
          {filtered.map((t, i) => (
            <div key={i} className="flex items-center gap-2.5 py-2 border-b border-lf-border/20">
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                t.won ? 'bg-lf-green/15 text-lf-green' : 'bg-lf-red/15 text-lf-red'
              }`}>{t.won ? 'W' : 'L'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <Badge color={t.sleeve === 'A' ? 'blue' : t.sleeve === 'B' ? 'orange' : 'purple'}>{t.sleeve}</Badge>
                  <span className="text-xs font-medium truncate">{t.driver}</span>
                  <span className="text-[10px] text-lf-muted font-mono">P{t.grid}</span>
                </div>
                <p className="text-[10px] text-lf-muted truncate">{t.race}</p>
              </div>
              <div className="text-right shrink-0">
                <span className={`text-xs font-bold tabular-nums font-mono ${t.pnl >= 0 ? 'text-lf-green' : 'text-lf-red'}`}>
                  {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}
                </span>
                <p className="text-[10px] text-lf-muted tabular-nums">${t.bankroll.toFixed(0)}</p>
              </div>
            </div>
          ))}
        </div>
        {/* Desktop: table */}
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
                <th className="py-3 text-left font-medium">#</th>
                <th className="py-3 text-left font-medium">Race</th>
                <th className="py-3 text-left font-medium">Driver</th>
                <th className="py-3 text-left font-medium">Sleeve</th>
                <th className="py-3 text-right font-medium">Grid</th>
                <th className="py-3 text-right font-medium">Price</th>
                <th className="py-3 text-right font-medium">Fair</th>
                <th className="py-3 text-right font-medium">P&L</th>
                <th className="py-3 text-right font-medium">Bankroll</th>
                <th className="py-3 text-center font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t, i) => (
                <tr key={i} className="border-b border-lf-border/20 table-row-hover">
                  <td className="py-2.5 text-lf-muted tabular-nums">{i + 1}</td>
                  <td className="py-2.5 text-lf-text">{t.race}</td>
                  <td className="py-2.5 font-medium">{t.driver}</td>
                  <td className="py-2.5">
                    <Badge color={t.sleeve === 'A' ? 'blue' : t.sleeve === 'B' ? 'orange' : 'purple'}>{t.sleeve}</Badge>
                  </td>
                  <td className="py-2.5 text-right text-lf-muted tabular-nums font-mono">P{t.grid}</td>
                  <td className="py-2.5 text-right tabular-nums font-mono">{(t.price * 100).toFixed(0)}¢</td>
                  <td className="py-2.5 text-right text-lf-muted tabular-nums font-mono">{(t.base * 100).toFixed(0)}%</td>
                  <td className={`py-2.5 text-right font-semibold tabular-nums font-mono ${t.pnl >= 0 ? 'text-lf-green' : 'text-lf-red'}`}>
                    {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}
                  </td>
                  <td className="py-2.5 text-right tabular-nums font-mono">${t.bankroll.toFixed(2)}</td>
                  <td className="py-2.5 text-center">
                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold ${
                      t.won ? 'bg-lf-green/15 text-lf-green' : 'bg-lf-red/15 text-lf-red'
                    }`}>{t.won ? 'W' : 'L'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
