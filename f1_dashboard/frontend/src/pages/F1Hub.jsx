import React, { useState, useEffect, useMemo } from 'react'
import { Trophy, Users, Timer, Gauge, Flag, Zap, TrendingUp, MapPin, Target,
         ChevronDown, ChevronUp, ArrowUpRight, ArrowDownRight, Minus, Activity,
         AlertTriangle, BarChart3, GitCompare } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
         LineChart, Line, Area, AreaChart, RadarChart, Radar, PolarGrid,
         PolarAngleAxis, PolarRadiusAxis, ScatterChart, Scatter, ZAxis,
         CartesianGrid, Legend, ReferenceLine, ComposedChart } from 'recharts'
import { Card, SectionTitle, Badge, Tabs, Loader, EmptyState } from '../components/Card'
import { api } from '../api'

// ═══════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════

const TEAM_COLORS = {
  'Red Bull': '#3671C6', 'Mercedes': '#27F4D2', 'Ferrari': '#E8002D',
  'McLaren': '#FF8000', 'Aston Martin': '#229971', 'Alpine': '#FF87BC',
  'Williams': '#64C4FF', 'RB': '#6692FF', 'Kick Sauber': '#52E252',
  'Haas F1 Team': '#B6BABD', 'Haas': '#B6BABD', 'Sauber': '#52E252',
  'Cadillac': '#FFD700',
}

const getColor = (team) => {
  if (!team) return '#3A3A4D'
  for (const [k, v] of Object.entries(TEAM_COLORS)) {
    if (team.toLowerCase().includes(k.toLowerCase())) return v
  }
  return '#3A3A4D'
}

const YEARS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019]

// ═══════════════════════════════════════════
// TOOLTIP COMPONENTS
// ═══════════════════════════════════════════

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-lf-dark/95 backdrop-blur-lg border border-lf-border rounded-lg px-3 py-2 shadow-xl">
      {label && <p className="text-[10px] text-lf-text mb-1">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="text-xs font-bold" style={{ color: p.color || p.fill || '#fff' }}>
          {p.name}: {typeof p.value === 'number' ? (p.value % 1 ? p.value.toFixed(1) : p.value) : p.value}
          {p.unit || ''}
        </p>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════
// ANIMATED NUMBER
// ═══════════════════════════════════════════

function AnimatedNum({ value, suffix = '', decimals = 0 }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    const target = Number(value) || 0
    const step = target / 30
    let current = 0
    const timer = setInterval(() => {
      current += step
      if (current >= target) { setDisplay(target); clearInterval(timer) }
      else setDisplay(current)
    }, 20)
    return () => clearInterval(timer)
  }, [value])
  return <span className="tabular-nums">{display.toFixed(decimals)}{suffix}</span>
}

// ═══════════════════════════════════════════
// MINI SPARKLINE
// ═══════════════════════════════════════════

function Sparkline({ data, color = '#E10600', height = 30, width = 100 }) {
  if (!data?.length) return null
  const max = Math.max(...data, 20)
  const min = Math.min(...data, 1)
  const range = max - min || 1
  const points = data.map((v, i) => 
    `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * (height - 4) - 2}`
  ).join(' ')
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={(data.length - 1) / (data.length - 1) * width} cy={height - ((data[data.length-1] - min) / range) * (height - 4) - 2} r="2.5" fill={color} />
    </svg>
  )
}

// ═══════════════════════════════════════════
// POSITION CHANGE INDICATOR
// ═══════════════════════════════════════════

function PosChange({ grid, finish }) {
  const diff = grid - finish
  if (diff > 0) return <span className="text-lf-green text-xs font-bold flex items-center gap-0.5"><ArrowUpRight size={12} />+{diff}</span>
  if (diff < 0) return <span className="text-lf-red text-xs font-bold flex items-center gap-0.5"><ArrowDownRight size={12} />{diff}</span>
  return <span className="text-lf-muted text-xs flex items-center gap-0.5"><Minus size={12} />0</span>
}

// ═══════════════════════════════════════════
// TEAM COLOR BAR
// ═══════════════════════════════════════════

function TeamBar({ team, className = '' }) {
  return <div className={`w-1 rounded-full ${className}`} style={{ background: getColor(team) }} />
}

// ═══════════════════════════════════════════
// MAIN HUB
// ═══════════════════════════════════════════

export default function F1Hub() {
  const [year, setYear] = useState(2025)
  const [tab, setTab] = useState('standings')
  const [drivers, setDrivers] = useState([])
  const [constructors, setConstructors] = useState([])
  const [lastRace, setLastRace] = useState(null)
  const [qualifying, setQualifying] = useState(null)
  const [seasonRaces, setSeasonRaces] = useState([])
  const [driverHistory, setDriverHistory] = useState([])
  const [qualiBattles, setQualiBattles] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const fetches = [
      api.getDriverStandings(year).then(setDrivers).catch(() => setDrivers([])),
      api.getConstructorStandings(year).then(setConstructors).catch(() => setConstructors([])),
      api.getLastRace(year).then(setLastRace).catch(() => setLastRace(null)),
      api.getQualifying(year).then(setQualifying).catch(() => setQualifying(null)),
    ]
    // Expanded data — only fetch for detailed tabs
    if (year <= 2025) {
      fetches.push(
        api.getSeasonRaces(year).then(setSeasonRaces).catch(() => setSeasonRaces([])),
        api.getDriverHistory(year).then(setDriverHistory).catch(() => setDriverHistory([])),
        api.getQualiBattles(year).then(setQualiBattles).catch(() => setQualiBattles([])),
      )
    }
    Promise.all(fetches).finally(() => setLoading(false))
  }, [year])

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3">
        <div className="overflow-x-auto scrollbar-none -mx-3 px-3 sm:mx-0 sm:px-0">
          <Tabs
            tabs={[
              { id: 'standings', icon: Trophy, label: 'Standings' },
              { id: 'season',    icon: Flag, label: 'Season' },
              { id: 'battles',   icon: GitCompare, label: 'H2H' },
              { id: 'analysis',  icon: BarChart3, label: 'Stats' },
            ]}
            active={tab} onChange={setTab}
          />
        </div>
        <select value={year} onChange={e => setYear(+e.target.value)}
          className="bg-lf-surface border border-lf-border rounded-lg px-3 py-1.5 sm:py-2 text-sm font-medium focus:border-lf-red focus:outline-none transition-colors self-end shrink-0">
          {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {loading ? <Loader /> : (
        <>
          {/* 2026 empty state — season hasn't started */}
          {year >= 2026 && drivers.length === 0 && (
            <Card className="text-center py-12 mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-lf-red/10 mb-4">
                <Flag size={28} className="text-lf-red" />
              </div>
              <h2 className="text-xl font-bold mb-2">The {year} Season Hasn't Started Yet</h2>
              <p className="text-sm text-lf-text max-w-lg mx-auto mb-4">
                First race: Australian GP on March 16, 2026. Once races begin, you'll see live standings, 
                results, teammate battles, and analytics here.
              </p>
              <p className="text-xs text-lf-muted">
                Check the <strong className="text-lf-red">Predictions</strong> tab for pre-race analysis →
              </p>
            </Card>
          )}
          {tab === 'standings' && <StandingsTab drivers={drivers} constructors={constructors} year={year} driverHistory={driverHistory} />}
          {tab === 'season' && <SeasonTab seasonRaces={seasonRaces} lastRace={lastRace} qualifying={qualifying} year={year} />}
          {tab === 'battles' && <BattlesTab qualiBattles={qualiBattles} year={year} />}
          {tab === 'analysis' && <AnalysisTab driverHistory={driverHistory} seasonRaces={seasonRaces} year={year} />}
        </>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════
// TAB: STANDINGS
// ═══════════════════════════════════════════

function StandingsTab({ drivers, constructors, year, driverHistory }) {
  const validDrivers = drivers.filter(d => !d.error)
  const validConstrs = constructors.filter(c => !c.error)
  
  if (validDrivers.length === 0) {
    return <EmptyState icon={Trophy} title="No standings data yet" description={`Standings for ${year} will appear after the first race.`} />
  }
  
  const leader = validDrivers[0]
  
  // Points progression per driver (from driverHistory)
  const progressionData = useMemo(() => {
    if (!driverHistory?.length) return []
    const top5 = driverHistory.filter(d => !d.error).slice(0, 6)
    const maxRounds = Math.max(...top5.flatMap(d => d.races?.map(r => r.round) || [0]))
    const data = []
    for (let r = 1; r <= maxRounds; r++) {
      const entry = { round: `R${r}` }
      top5.forEach(d => {
        const cumPts = d.races?.filter(x => x.round <= r).reduce((s, x) => s + x.points, 0) || 0
        entry[d.code] = cumPts
        entry[`${d.code}_team`] = d.team
      })
      data.push(entry)
    }
    return data
  }, [driverHistory])
  
  const top5Codes = driverHistory?.filter(d => !d.error).slice(0, 6).map(d => d.code) || []

  return (
    <div className="space-y-5">
      {/* Leader Hero Card */}
      {leader && (
        <div className="relative overflow-hidden rounded-xl border border-lf-border bg-gradient-to-r from-lf-card to-lf-surface p-4 sm:p-6">
          <div className="absolute top-0 right-0 w-64 h-64 opacity-[0.03]" style={{
            background: `radial-gradient(circle at center, ${getColor(leader.team)}, transparent 70%)`
          }} />
          <div className="relative flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 sm:gap-5 min-w-0">
              <div className="text-3xl sm:text-5xl font-black text-lf-muted/20 tabular-nums shrink-0">1</div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 sm:gap-3 mb-1">
                  <TeamBar team={leader.team} className="h-6 sm:h-8" />
                  <h2 className="text-lg sm:text-2xl font-bold truncate">{leader.name || leader.driver}</h2>
                </div>
                <p className="text-xs sm:text-sm text-lf-text">{leader.team}</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-2xl sm:text-4xl font-black tabular-nums" style={{ color: getColor(leader.team) }}>
                <AnimatedNum value={leader.points} />
              </div>
              <p className="text-[10px] sm:text-xs text-lf-text mt-1">{leader.wins} win{leader.wins !== 1 ? 's' : ''}</p>
            </div>
          </div>
        </div>
      )}
      
      {/* Championship Progression Chart */}
      {progressionData.length > 0 && (
        <Card>
          <SectionTitle sub="Points accumulated per round">Championship Battle</SectionTitle>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={progressionData} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1C1C28" />
              <XAxis dataKey="round" tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              {top5Codes.map(code => (
                <Line key={code} type="monotone" dataKey={code} name={code}
                  stroke={getColor(progressionData[0]?.[`${code}_team`])}
                  strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Driver + Constructor side by side */}
      <div className="grid lg:grid-cols-5 gap-3 sm:gap-5">
        {/* Driver Standings Table */}
        <Card padding="p-0" className="lg:col-span-3">
          <div className="p-5 pb-3">
            <SectionTitle sub={`${year} World Championship`}>Driver Standings</SectionTitle>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
                  <th className="text-center py-2.5 px-3 font-medium w-12">#</th>
                  <th className="text-left py-2.5 font-medium">Driver</th>
                  <th className="text-left py-2.5 font-medium hidden sm:table-cell">Team</th>
                  <th className="text-center py-2.5 font-medium w-16">Wins</th>
                  <th className="text-right py-2.5 font-medium w-20">Form</th>
                  <th className="text-right py-2.5 px-4 font-medium w-16">Pts</th>
                </tr>
              </thead>
              <tbody>
                {validDrivers.map((d, i) => {
                  const dh = driverHistory?.find(x => x.code === (d.driver || d.name?.split(' ').pop()?.slice(0,3)?.toUpperCase()))
                  const recentPositions = dh?.races?.slice(-5).map(r => r.position) || []
                  return (
                    <tr key={i} className="border-b border-lf-border/15 table-row-hover group">
                      <td className="py-3 px-3 text-center">
                        <span className={`font-bold tabular-nums text-xs ${
                          i === 0 ? 'text-lf-yellow' : i < 3 ? 'text-lf-text' : 'text-lf-muted'
                        }`}>
                          {i === 0 ? '👑' : d.position}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <TeamBar team={d.team} className="h-6 group-hover:h-8 transition-all" />
                          <div>
                            <span className="font-semibold text-[13px]">{d.name || d.driver}</span>
                            <span className="text-lf-muted text-[10px] ml-2 sm:hidden">{d.team}</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 text-lf-text text-xs hidden sm:table-cell">{d.team}</td>
                      <td className="py-3 text-center tabular-nums font-medium">{d.wins}</td>
                      <td className="py-3 text-right pr-1">
                        <Sparkline data={recentPositions} color={getColor(d.team)} height={22} width={60} />
                      </td>
                      <td className="py-3 text-right px-4">
                        <span className="font-bold tabular-nums text-base">{d.points}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Constructor Standings */}
        <Card padding="p-0" className="lg:col-span-2">
          <div className="p-5 pb-3">
            <SectionTitle>Constructors</SectionTitle>
          </div>
          <div className="space-y-0">
            {validConstrs.map((c, i) => {
              const pctOfLeader = validConstrs[0]?.points ? (c.points / validConstrs[0].points * 100) : 0
              return (
                <div key={i} className="flex items-center gap-3 px-5 py-3 border-b border-lf-border/15 table-row-hover">
                  <span className={`text-xs font-bold w-5 tabular-nums ${i < 3 ? 'text-lf-yellow' : 'text-lf-muted'}`}>{c.position}</span>
                  <TeamBar team={c.team} className="h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-baseline">
                      <span className="font-medium text-sm truncate">{c.team}</span>
                      <span className="font-bold tabular-nums ml-2">{c.points}</span>
                    </div>
                    <div className="mt-1 h-1 bg-lf-surface rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-1000 ease-out"
                        style={{ width: `${pctOfLeader}%`, background: getColor(c.team) }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════
// TAB: SEASON
// ═══════════════════════════════════════════

function SeasonTab({ seasonRaces, lastRace, qualifying, year }) {
  const validRaces = seasonRaces?.filter(r => !r.error) || []
  const [selectedRace, setSelectedRace] = useState(null)
  
  if (validRaces.length === 0) {
    return <EmptyState icon={Flag} title="No race results yet" description={`Race results for ${year} will appear after each Grand Prix.`} />
  }
  
  if (!validRaces.length) {
    return (
      <div className="space-y-5">
        {/* Last Race */}
        {lastRace?.results && (
          <Card>
            <SectionTitle sub={lastRace.date}>
              {lastRace.race} — Race Results
            </SectionTitle>
            <RaceResultsTable results={lastRace.results} />
          </Card>
        )}
        
        {/* Qualifying */}
        {qualifying?.grid?.length > 0 && (
          <Card>
            <SectionTitle sub={qualifying.date}>{qualifying.race} — Qualifying</SectionTitle>
            <QualifyingTable grid={qualifying.grid} />
          </Card>
        )}
        
        {!lastRace?.results && !qualifying?.grid?.length && (
          <EmptyState icon={Flag} title={`No season data for ${year}`} description="Results will appear once the season begins" />
        )}
      </div>
    )
  }

  // Season summary stats
  const uniqueWinners = [...new Set(validRaces.map(r => r.winner_code))].length
  const totalDNFs = validRaces.reduce((s, r) => s + (r.dnf_count || 0), 0)
  const avgDNFs = (totalDNFs / validRaces.length).toFixed(1)
  
  // Wins distribution
  const winCounts = {}
  validRaces.forEach(r => {
    if (r.winner_code) winCounts[r.winner_code] = (winCounts[r.winner_code] || 0) + 1
  })
  const winData = Object.entries(winCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([code, wins]) => {
      const race = validRaces.find(r => r.winner_code === code)
      return { driver: code, wins, team: race?.winner_team }
    })

  return (
    <div className="space-y-5">
      {/* Season Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
        <Card glow>
          <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-text">Races</p>
          <p className="text-xl sm:text-2xl font-black tabular-nums mt-1"><AnimatedNum value={validRaces.length} /></p>
        </Card>
        <Card glow>
          <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-text">Winners</p>
          <p className="text-xl sm:text-2xl font-black tabular-nums mt-1 text-lf-yellow"><AnimatedNum value={uniqueWinners} /></p>
        </Card>
        <Card glow>
          <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-text">Avg DNFs</p>
          <p className="text-xl sm:text-2xl font-black tabular-nums mt-1 text-lf-orange"><AnimatedNum value={avgDNFs} decimals={1} /></p>
        </Card>
        <Card glow>
          <p className="text-[9px] sm:text-[10px] uppercase tracking-wider text-lf-text">Total DNFs</p>
          <p className="text-xl sm:text-2xl font-black tabular-nums mt-1 text-lf-red"><AnimatedNum value={totalDNFs} /></p>
        </Card>
      </div>

      {/* Win Distribution Bar Chart */}
      {winData.length > 0 && (
        <Card>
          <SectionTitle sub={`${year} race victories`}>Wins Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={winData} margin={{ left: 0, right: 10 }}>
              <XAxis dataKey="driver" tick={{ fill: '#ddd', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="wins" name="Wins" radius={[6, 6, 0, 0]} barSize={28}>
                {winData.map((d, i) => <Cell key={i} fill={getColor(d.team)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Race-by-Race Timeline */}
      <Card padding="p-0">
        <div className="p-5 pb-3">
          <SectionTitle>Race-by-Race Results</SectionTitle>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
                <th className="text-center py-2.5 px-3 font-medium">Rd</th>
                <th className="text-left py-2.5 font-medium">Race</th>
                <th className="text-left py-2.5 font-medium">Winner</th>
                <th className="text-left py-2.5 font-medium hidden md:table-cell">P2</th>
                <th className="text-left py-2.5 font-medium hidden md:table-cell">P3</th>
                <th className="text-center py-2.5 font-medium">DNFs</th>
              </tr>
            </thead>
            <tbody>
              {validRaces.map((r, i) => (
                <tr key={i} className="border-b border-lf-border/15 table-row-hover cursor-pointer"
                  onClick={() => setSelectedRace(selectedRace === i ? null : i)}>
                  <td className="py-3 px-3 text-center text-xs font-bold tabular-nums text-lf-muted">{r.round}</td>
                  <td className="py-3">
                    <div className="font-medium text-[13px]">{r.name?.replace(' Grand Prix', '')}</div>
                    <div className="text-[10px] text-lf-muted">{r.date}</div>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <TeamBar team={r.winner_team} className="h-5" />
                      <span className="font-semibold">{r.winner || '—'}</span>
                    </div>
                  </td>
                  <td className="py-3 text-lf-text hidden md:table-cell">
                    {r.podium?.[1] && <span className="flex items-center gap-1.5"><TeamBar team={r.podium[1].team} className="h-4" />{r.podium[1].driver}</span>}
                  </td>
                  <td className="py-3 text-lf-text hidden md:table-cell">
                    {r.podium?.[2] && <span className="flex items-center gap-1.5"><TeamBar team={r.podium[2].team} className="h-4" />{r.podium[2].driver}</span>}
                  </td>
                  <td className="py-3 text-center">
                    {r.dnf_count > 0 ? (
                      <Badge color={r.dnf_count > 3 ? 'red' : r.dnf_count > 1 ? 'yellow' : 'gray'}>{r.dnf_count}</Badge>
                    ) : <span className="text-lf-muted">0</span>}
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


// ═══════════════════════════════════════════
// TAB: HEAD TO HEAD BATTLES
// ═══════════════════════════════════════════

function BattlesTab({ qualiBattles, year }) {
  const battles = qualiBattles?.filter(b => !b.error) || []
  
  if (!battles.length) {
    return <EmptyState icon={GitCompare} title={`No qualifying data for ${year}`} description="Teammate battles appear after qualifying sessions" />
  }

  return (
    <div className="space-y-5">
      <SectionTitle sub={`${year} — Based on qualifying head-to-head`}>Teammate Battles</SectionTitle>
      
      <div className="grid md:grid-cols-2 gap-3 sm:gap-4">
        {battles.map((b, i) => {
          const total = b.d1_wins + b.d2_wins
          const d1pct = total > 0 ? (b.d1_wins / total * 100) : 50
          const d2pct = 100 - d1pct
          const color1 = getColor(b.team)
          const color2 = getColor(b.team)
          
          return (
            <Card key={i} className="overflow-hidden">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-lf-muted font-medium">{b.team}</span>
                <Badge color="gray">{total} races</Badge>
              </div>
              
              {/* Battle bar */}
              <div className="flex items-center gap-3 mb-3">
                <div className="text-right flex-1">
                  <div className="font-black text-lg tabular-nums" style={{ color: d1pct > d2pct ? color1 : '#3A3A4D' }}>{b.driver1}</div>
                  <div className="text-2xl font-black tabular-nums">{b.d1_wins}</div>
                </div>
                
                <div className="w-40 h-8 bg-lf-surface rounded-lg overflow-hidden flex">
                  <div className="h-full transition-all duration-1000 ease-out flex items-center justify-end pr-1.5"
                    style={{ width: `${d1pct}%`, background: `${color1}${d1pct > d2pct ? 'CC' : '44'}` }}>
                    <span className="text-[10px] font-bold text-white/80">{d1pct.toFixed(0)}%</span>
                  </div>
                  <div className="h-full transition-all duration-1000 ease-out flex items-center pl-1.5"
                    style={{ width: `${d2pct}%`, background: `${color2}${d2pct > d1pct ? 'CC' : '44'}` }}>
                    <span className="text-[10px] font-bold text-white/80">{d2pct.toFixed(0)}%</span>
                  </div>
                </div>
                
                <div className="flex-1">
                  <div className="font-black text-lg tabular-nums" style={{ color: d2pct > d1pct ? color2 : '#3A3A4D' }}>{b.driver2}</div>
                  <div className="text-2xl font-black tabular-nums">{b.d2_wins}</div>
                </div>
              </div>
              
              {/* Round-by-round dots */}
              <div className="flex gap-1 justify-center">
                {b.rounds?.map((r, j) => (
                  <div key={j} className="group relative">
                    <div className={`w-4 h-4 rounded-sm text-[8px] font-bold flex items-center justify-center transition-transform hover:scale-150 ${
                      r.d1_pos < r.d2_pos ? 'bg-lf-green/20 text-lf-green' : 'bg-lf-red/20 text-lf-red'
                    }`}>
                      {r.d1_pos < r.d2_pos ? '✓' : '✗'}
                    </div>
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
                      <div className="bg-lf-dark border border-lf-border rounded px-2 py-1 text-[10px] whitespace-nowrap shadow-xl">
                        R{r.round}: P{r.d1_pos} vs P{r.d2_pos}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════
// TAB: ANALYTICS (DEEP DATA)
// ═══════════════════════════════════════════

function AnalysisTab({ driverHistory, seasonRaces, year }) {
  const drivers = driverHistory?.filter(d => !d.error) || []
  const races = seasonRaces?.filter(r => !r.error) || []
  
  if (drivers.length === 0 && races.length === 0) {
    return <EmptyState icon={BarChart3} title="No analytics data yet" description={`Analytics for ${year} will appear after race results are available.`} />
  }
  
  // Position heatmap data — each driver's finishing position per round
  const heatmapDrivers = drivers.slice(0, 10)
  
  // Grid vs finish (all drivers, all races)
  const gridVsFinish = []
  drivers.forEach(d => {
    d.races?.forEach(r => {
      if (r.grid > 0 && r.position <= 20) {
        gridVsFinish.push({ grid: r.grid, finish: r.position, driver: d.code, team: d.team })
      }
    })
  })
  
  // Consistency metric — standard deviation of positions
  const consistencyData = drivers.slice(0, 15).map(d => {
    const positions = d.races?.map(r => r.position) || []
    const avg = positions.reduce((s, p) => s + p, 0) / (positions.length || 1)
    const variance = positions.reduce((s, p) => s + (p - avg) ** 2, 0) / (positions.length || 1)
    const stdDev = Math.sqrt(variance)
    return {
      driver: d.code, team: d.team,
      avg: parseFloat(avg.toFixed(1)),
      stdDev: parseFloat(stdDev.toFixed(1)),
      best: Math.min(...positions),
      worst: Math.max(...positions),
      races: positions.length,
    }
  }).sort((a, b) => a.avg - b.avg)

  // Points per race efficiency
  const efficiencyData = drivers.slice(0, 15).map(d => {
    const totalPts = d.races?.reduce((s, r) => s + r.points, 0) || 0
    const raceCount = d.races?.length || 1
    return {
      driver: d.code, team: d.team,
      ppRace: parseFloat((totalPts / raceCount).toFixed(1)),
      total: totalPts,
    }
  }).sort((a, b) => b.ppRace - a.ppRace)

  return (
    <div className="space-y-5">
      {/* Grid vs Finish Scatter */}
      {gridVsFinish.length > 0 && (
        <Card>
          <SectionTitle sub="Below the diagonal = gained positions, above = lost positions">Grid vs Race Finish</SectionTitle>
          <ResponsiveContainer width="100%" height={350}>
            <ScatterChart margin={{ left: 10, right: 10, top: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1C1C28" />
              <XAxis type="number" dataKey="grid" name="Grid" domain={[0, 21]} tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} label={{ value: 'Grid Position', position: 'bottom', fill: '#3A3A4D', fontSize: 10 }} />
              <YAxis type="number" dataKey="finish" name="Finish" domain={[0, 21]} tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} reversed label={{ value: 'Finish Position', angle: -90, position: 'insideLeft', fill: '#3A3A4D', fontSize: 10 }} />
              <ZAxis range={[30, 30]} />
              <Tooltip content={({ active, payload }) => active && payload?.length ? (
                <div className="bg-lf-dark/95 backdrop-blur-lg border border-lf-border rounded-lg px-3 py-2 shadow-xl">
                  <p className="text-xs font-bold">{payload[0].payload.driver}</p>
                  <p className="text-[10px] text-lf-text">Grid P{payload[0].payload.grid} → Finish P{payload[0].payload.finish}</p>
                  <p className="text-[10px]" style={{ color: payload[0].payload.finish < payload[0].payload.grid ? '#00E676' : '#E10600' }}>
                    {payload[0].payload.finish < payload[0].payload.grid ? '+' : ''}{payload[0].payload.grid - payload[0].payload.finish} positions
                  </p>
                </div>
              ) : null} />
              <ReferenceLine segment={[{x:0,y:0},{x:20,y:20}]} stroke="#3A3A4D" strokeDasharray="4 4" />
              <Scatter data={gridVsFinish} fill="#E10600" fillOpacity={0.5}>
                {gridVsFinish.map((d, i) => <Cell key={i} fill={getColor(d.team)} fillOpacity={0.6} />)}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Consistency + Efficiency side by side */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Points per Race */}
        {efficiencyData.length > 0 && (
          <Card>
            <SectionTitle sub="Average points scored per race">Points Efficiency</SectionTitle>
            <ResponsiveContainer width="100%" height={Math.max(250, efficiencyData.length * 28)}>
              <BarChart data={efficiencyData} layout="vertical" margin={{ left: 40 }}>
                <XAxis type="number" tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="driver" tick={{ fill: '#ddd', fontSize: 10, fontWeight: 600, fontFamily: 'JetBrains Mono' }} width={38} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="ppRace" name="Pts/Race" radius={[0, 6, 6, 0]} barSize={18}>
                  {efficiencyData.map((d, i) => <Cell key={i} fill={getColor(d.team)} fillOpacity={0.8} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}

        {/* Consistency (avg position + range) */}
        {consistencyData.length > 0 && (
          <Card>
            <SectionTitle sub="Average finishing position (lower = better)">Consistency Rating</SectionTitle>
            <div className="space-y-2.5 mt-2">
              {consistencyData.map((d, i) => {
                const barWidth = Math.max(5, ((20 - d.avg) / 20) * 100)
                return (
                  <div key={i} className="flex items-center gap-3 group">
                    <span className="text-[11px] font-bold w-8 tabular-nums text-right font-mono" style={{ color: getColor(d.team) }}>{d.driver}</span>
                    <div className="flex-1 h-5 bg-lf-surface rounded relative overflow-hidden">
                      <div className="absolute inset-y-0 left-0 rounded transition-all duration-1000"
                        style={{ width: `${barWidth}%`, background: `${getColor(d.team)}88` }} />
                      {/* Range indicator */}
                      <div className="absolute inset-y-0 flex items-center" 
                        style={{ left: `${((20 - d.worst) / 20) * 100}%`, right: `${100 - ((20 - d.best) / 20) * 100}%` }}>
                        <div className="w-full h-1.5 rounded-full" style={{ background: getColor(d.team) }} />
                      </div>
                    </div>
                    <span className="text-xs tabular-nums w-8 text-right font-medium">{d.avg}</span>
                    <span className="text-[10px] text-lf-muted w-16 text-right tabular-nums hidden sm:inline">
                      P{d.best}–P{d.worst}
                    </span>
                  </div>
                )
              })}
            </div>
          </Card>
        )}
      </div>

      {/* Position Heatmap */}
      {heatmapDrivers.length > 0 && (
        <Card>
          <SectionTitle sub="Finishing position each round — green = podium, red = outside top 10">Season Position Heatmap</SectionTitle>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left py-2 px-2 text-[10px] text-lf-muted font-medium sticky left-0 bg-lf-card z-10">Driver</th>
                  {heatmapDrivers[0]?.races?.map((_, j) => (
                    <th key={j} className="text-center py-2 px-1 text-[10px] text-lf-muted font-medium w-8">R{j + 1}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmapDrivers.map((d, i) => (
                  <tr key={i}>
                    <td className="py-1.5 px-2 font-bold sticky left-0 bg-lf-card z-10" style={{ color: getColor(d.team) }}>{d.code}</td>
                    {d.races?.map((r, j) => {
                      const pos = r.position
                      const bg = pos === 1 ? 'bg-lf-yellow/30 text-lf-yellow' :
                                 pos <= 3 ? 'bg-lf-green/20 text-lf-green' :
                                 pos <= 6 ? 'bg-lf-blue/15 text-lf-blue' :
                                 pos <= 10 ? 'bg-lf-surface text-lf-text' :
                                 'bg-lf-red/10 text-lf-red/70'
                      const dnf = r.status && !['Finished', '+1 Lap', '+2 Laps', '+3 Laps'].includes(r.status)
                      return (
                        <td key={j} className="py-1.5 px-1 text-center">
                          <div className={`w-7 h-7 rounded flex items-center justify-center font-bold tabular-nums transition-transform hover:scale-125 ${dnf ? 'bg-lf-red/20 text-lf-red line-through' : bg}`}
                            title={`R${r.round}: P${pos} (Grid P${r.grid}) ${dnf ? '— DNF: ' + r.status : ''}`}>
                            {dnf ? '✗' : pos}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Base Rate Analysis (always available) */}
      <div className="grid md:grid-cols-2 gap-5">
        <Card>
          <SectionTitle sub="2,553 race results (2019–2024)">Grid → Podium Rate</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={[
              { pos: 'P1', pct: 74 }, { pos: 'P2', pct: 57 }, { pos: 'P3', pct: 43 },
              { pos: 'P4', pct: 28 }, { pos: 'P5', pct: 22 }, { pos: 'P6', pct: 15 },
              { pos: 'P7', pct: 12 }, { pos: 'P8', pct: 8 }, { pos: 'P9', pct: 7 }, { pos: 'P10', pct: 5 }
            ]} margin={{ left: 0, right: 0, top: 5, bottom: 0 }}>
              <defs>
                <linearGradient id="podium-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#E10600" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#E10600" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="pos" tick={{ fill: '#ddd', fontSize: 10, fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="pct" name="Podium %" stroke="#E10600" fill="url(#podium-grad)" strokeWidth={2} dot={{ fill: '#E10600', r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <SectionTitle sub="2,553 race results (2019–2024)">Grid → Win Rate</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={[
              { pos: 'P1', pct: 45 }, { pos: 'P2', pct: 23 }, { pos: 'P3', pct: 12 },
              { pos: 'P4', pct: 7 }, { pos: 'P5', pct: 5 }, { pos: 'P6', pct: 3 },
              { pos: 'P7', pct: 2 }, { pos: 'P8', pct: 1 }, { pos: 'P9', pct: 0.8 }, { pos: 'P10', pct: 0.5 }
            ]} margin={{ left: 0, right: 0, top: 5, bottom: 0 }}>
              <defs>
                <linearGradient id="win-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FFD600" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#FFD600" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="pos" tick={{ fill: '#ddd', fontSize: 10, fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#3A3A4D', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="pct" name="Win %" stroke="#FFD600" fill="url(#win-grad)" strokeWidth={2} dot={{ fill: '#FFD600', r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Strategy Explainer */}
      <Card accent>
        <SectionTitle>How We Use This Data</SectionTitle>
        <div className="grid md:grid-cols-3 gap-6 mt-2">
          <div>
            <Badge color="blue" className="mb-2">SLEEVE A</Badge>
            <h4 className="font-bold text-sm mb-1">Lottery Tickets</h4>
            <p className="text-xs text-lf-text leading-relaxed">
              When Kalshi underprices a midfield driver's podium chance by ≥15% vs our base rates, we buy YES.
              54% hit rate in 2025 backtesting. A 10¢ bet can return $1.
            </p>
          </div>
          <div>
            <Badge color="orange" className="mb-2">SLEEVE B</Badge>
            <h4 className="font-bold text-sm mb-1">Steady Grinder</h4>
            <p className="text-xs text-lf-text leading-relaxed">
              When Kalshi overprices a P2/P3 qualifier's win chance by ≥8%, we sell (buy NO).
              76% hit rate. Small, consistent profits.
            </p>
          </div>
          <div>
            <Badge color="purple" className="mb-2">SLEEVE E</Badge>
            <h4 className="font-bold text-sm mb-1">Value Sweep</h4>
            <p className="text-xs text-lf-text leading-relaxed">
              When any driver outside top 3 is wildly overpriced for the win (≥10% edge, price 15-50¢), we sell.
              Rare but high-conviction.
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}


// ═══════════════════════════════════════════
// REUSABLE TABLE COMPONENTS
// ═══════════════════════════════════════════

function RaceResultsTable({ results }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
            <th className="text-left py-2.5 font-medium w-12">Pos</th>
            <th className="text-left py-2.5 font-medium">Driver</th>
            <th className="text-left py-2.5 font-medium hidden sm:table-cell">Team</th>
            <th className="text-right py-2.5 font-medium">Time</th>
            <th className="text-right py-2.5 font-medium">Pts</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className={`border-b border-lf-border/15 table-row-hover ${i < 3 ? 'bg-lf-yellow/[0.02]' : ''}`}>
              <td className="py-2.5">
                <span className={`font-bold tabular-nums ${i === 0 ? 'text-lf-yellow' : i < 3 ? 'text-lf-text' : 'text-lf-muted'}`}>
                  {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : r.position}
                </span>
              </td>
              <td className="py-2.5">
                <span className="flex items-center gap-2">
                  <TeamBar team={r.team} className="h-5" />
                  <span className="font-medium">{r.name || r.driver}</span>
                  {r.grid && <PosChange grid={parseInt(r.grid)} finish={parseInt(r.position)} />}
                </span>
              </td>
              <td className="py-2.5 text-lf-text text-xs hidden sm:table-cell">{r.team}</td>
              <td className="py-2.5 text-right font-mono text-xs text-lf-text tabular-nums">{r.time}</td>
              <td className="py-2.5 text-right font-bold tabular-nums">{r.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function QualifyingTable({ grid }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-lf-muted border-b border-lf-border">
            <th className="text-left py-2.5 font-medium w-12">Pos</th>
            <th className="text-left py-2.5 font-medium">Driver</th>
            <th className="text-left py-2.5 font-medium hidden sm:table-cell">Team</th>
            <th className="text-right py-2.5 font-medium">Q1</th>
            <th className="text-right py-2.5 font-medium">Q2</th>
            <th className="text-right py-2.5 font-medium">Q3</th>
          </tr>
        </thead>
        <tbody>
          {grid.map((q, i) => (
            <tr key={i} className={`border-b border-lf-border/15 table-row-hover ${i === 0 ? 'bg-lf-yellow/[0.02]' : ''}`}>
              <td className="py-2.5 font-bold tabular-nums">{i === 0 ? '🏁' : `P${q.position}`}</td>
              <td className="py-2.5">
                <span className="flex items-center gap-2"><TeamBar team={q.team} className="h-5" /><span className="font-medium">{q.name || q.driver}</span></span>
              </td>
              <td className="py-2.5 text-lf-text text-xs hidden sm:table-cell">{q.team}</td>
              <td className="py-2.5 text-right font-mono text-xs tabular-nums text-lf-text">{q.q1 || '—'}</td>
              <td className="py-2.5 text-right font-mono text-xs tabular-nums text-lf-text">{q.q2 || '—'}</td>
              <td className="py-2.5 text-right font-mono text-xs tabular-nums text-lf-green">{q.q3 || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
