const BASE = '/api'

async function get(path) {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

async function post(path, body) {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

export const api = {
  // State
  getState: () => get('/state'),
  resetState: () => post('/state/reset'),

  // Monitor
  getMonitorStatus: () => get('/monitor/status'),
  getRecentSignals: (limit = 50) => get(`/monitor/signals?limit=${limit}`),

  // Kill switch
  getKillStatus: () => get('/kill/status'),
  kill: (pin) => post(`/kill?pin=${pin}`),
  unkill: (pin) => post(`/unkill?pin=${pin}`),

  // Strategy
  getBacktest: (params = {}) => {
    const q = new URLSearchParams()
    if (params.betSize != null) q.set('bet_size', params.betSize)
    if (params.sleeveA != null) q.set('sleeve_a', params.sleeveA)
    if (params.sleeveB != null) q.set('sleeve_b', params.sleeveB)
    if (params.sleeveE != null) q.set('sleeve_e', params.sleeveE)
    if (params.edgeA != null) q.set('edge_a', params.edgeA)
    if (params.edgeB != null) q.set('edge_b', params.edgeB)
    if (params.edgeE != null) q.set('edge_e', params.edgeE)
    return get('/backtest?' + q.toString())
  },

  // Contracts analysis
  getContractsAnalysis: () => get('/contracts/analysis'),

  // Trading (read-only)
  getOpenTrades: () => get('/trades/open'),
  getTradeHistory: () => get('/trades/history'),

  // Kalshi
  getBalance: () => get('/kalshi/balance'),
  getMarkets: (ticker) => get(`/kalshi/markets/${ticker}`),
  syncKalshi: () => post('/kalshi/sync'),

  // Prices
  getPriceHistory: (ticker, limit = 100) => get(`/prices/history?${ticker ? `ticker=${ticker}&` : ''}limit=${limit}`),

  // Audit
  getAuditLog: (type, limit = 200) => get(`/audit?${type ? `event_type=${type}&` : ''}limit=${limit}`),

  // F1
  getDriverStandings: (year = 2025) => get(`/f1/standings/drivers?year=${year}`),
  getConstructorStandings: (year = 2025) => get(`/f1/standings/constructors?year=${year}`),
  getLastRace: (year = 2025) => get(`/f1/results/last?year=${year}`),
  getQualifying: (year = 2025, round = null) => get(`/f1/qualifying?year=${year}${round ? `&round=${round}` : ''}`),
  getRaceResults: (year, round) => get(`/f1/race/${year}/${round}`),
  getLiveTiming: () => get('/f1/timing'),

  // Expanded F1 Hub
  getSeasonRaces: (year = 2025) => get(`/f1/season/${year}`),
  getDriverHistory: (year = 2025) => get(`/f1/driver-history/${year}`),
  getQualiBattles: (year = 2025) => get(`/f1/quali-battles/${year}`),
  getPredictions: () => get('/f1/predictions'),

  // Config
  getConfig: () => get('/config'),

  // Health
  getHealth: () => get('/health'),
}
