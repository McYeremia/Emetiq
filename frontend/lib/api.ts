import { getAccessToken } from './authToken';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// Pembungkus fetch yang menyisipkan header Authorization (Supabase access token)
// bila user sedang login. Endpoint publik tetap jalan tanpa token.
async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return globalThis.fetch(input, { ...init, headers });
}

export interface Stock {
  ticker: string;
  name: string;
  sector: string;
  last_price: number | null;
  prev_close: number | null;
  change_pct: number | null;
  last_date: string | null;
  market_cap: number | null;
  pe_ratio: number | null;
  pbv_ratio: number | null;
  dividend_yield: number | null;
}

export interface OHLCV {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PortfolioItem {
  ticker: string;
  shares: number;
  avg_price: number;
  current_price: number;
  last_date: string | null;
  cost_basis: number;
  unrealized_pnl: number;
  strategy?: string;
  notes?: string;
}

export interface AgentPortfolio {
  modal: number;
  invested: number;
  unrealized: number;
  realized: number;
  total_value: number;
  assets: PortfolioItem[];
}

export interface MultiPortfolioResponse {
  USER: AgentPortfolio;
  GEMINI: AgentPortfolio;
  CLAUDE: AgentPortfolio;
  AI: AgentPortfolio;
}

// ── AI Porto (dev-only) ──────────────────────────────────────────────────────
export interface AiPortoHolding {
  ticker: string;
  lots: number;
  shares: number;
  avg_price: number;
  current_price: number;
  cost_basis: number;
  unrealized_pnl: number;
  unrealized_pct: number | null;
}
export interface AiPortoSnapshot {
  cash: number;
  invested: number;
  unrealized: number;
  realized: number;
  total_value: number;
  position_count: number;
  holdings: AiPortoHolding[];
}
export interface AiPortoOrder {
  ticker: string;
  action: 'BUY' | 'SELL';
  lots: number;
  price?: number;
  reason: string;
}
export interface AiPortoResponse {
  reply: string;
  strategy_note: string;
  executed: AiPortoOrder[];
  skipped: AiPortoOrder[];
  snapshot: AiPortoSnapshot;
}

export interface TradeHistory {
  id: number;
  ticker: string;
  action: 'BUY' | 'SELL';
  date: string;
  price: number;
  quantity: number;
  total_value: number;
  pnl: number | null;
  pnl_pct: number | null;
  strategy: string;
  notes: string;
}

export interface BrokerFlowEntry {
  broker_code: string;
  broker_name: string;
  total_value: number;
  volume: number;
  frequency: number;
}

export interface BrokerFlowResponse {
  date: string | null;
  data: BrokerFlowEntry[];
}

export interface BacktestResult {
  strategy_id: string;
  ticker: string;
  metrics: {
    win_rate: number;
    total_return_pct: number;
    total_trades: number;
    wins: number;
    losses: number;
    max_drawdown_pct: number;
    initial_capital: number;
    final_value: number;
  };
  equity_curve: { date: string; value: number }[];
  trades: {
    date: string;
    type: string;
    price: number;
    lots: number;
    shares: number;
    total_value: number;
    capital_after: number;
    hold_days?: number;
    exit_reason?: string;
    pnl?: number;
    pnl_pct?: number;
  }[];
}

export const api = {
  async getStocks(): Promise<Stock[]> {
    const res = await apiFetch(`${API_BASE_URL}/stocks`);
    return res.json();
  },

  async getOHLCV(ticker: string, from?: string): Promise<{ data: OHLCV[] }> {
    const url = from
      ? `${API_BASE_URL}/stocks/${ticker}/ohlcv?from=${from}`
      : `${API_BASE_URL}/stocks/${ticker}/ohlcv`;
    const res = await apiFetch(url);
    return res.json();
  },

  async getIndicators(ticker: string) {
    const res = await apiFetch(`${API_BASE_URL}/stocks/${ticker}/indicators`);
    return res.json();
  },

  async getPortfolio(): Promise<MultiPortfolioResponse> {
    const res = await apiFetch(`${API_BASE_URL}/trades/portfolio`);
    return res.json();
  },

  async executeTrade(
    ticker: string,
    action: 'BUY' | 'SELL',
    quantity: number,
    price?: number,
    tradeType: string = 'MANUAL',
    notes?: string,
    strategyId?: string
  ) {
    const res = await apiFetch(`${API_BASE_URL}/trades`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker,
        action,
        quantity,
        price,
        trade_type: tradeType,
        notes,
        strategy_id: strategyId,
      }),
    });
    return res.json();
  },

  async refreshData(ticker?: string) {
    const url = ticker
      ? `${API_BASE_URL}/stocks/${ticker}/refresh`
      : `${API_BASE_URL}/stocks/refresh`;
    const res = await apiFetch(url, { method: 'POST' });
    return res.json();
  },

  async getSyncStatus(): Promise<{
    is_running: boolean;
    phase: string;
    phase_label: string;
    total: number;
    done: number;
    current: string;
    errors: number;
    message: string;
  }> {
    const res = await apiFetch(`${API_BASE_URL}/stocks/sync-status`);
    return res.json();
  },

  async runBacktest(ticker: string, strategyId: string, capital: number = 10_000_000): Promise<BacktestResult> {
    const res = await apiFetch(`${API_BASE_URL}/backtest/run/${ticker}/${strategyId}?capital=${capital}`);
    return res.json();
  },

  async screenStocks(strategyId: string) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120_000); // 2 menit
    try {
      const res = await apiFetch(`${API_BASE_URL}/backtest/screen/${strategyId}`, {
        signal: controller.signal,
      });
      return res.json();
    } finally {
      clearTimeout(timeout);
    }
  },

  async addStock(ticker: string) {
    const res = await apiFetch(`${API_BASE_URL}/stocks/${ticker}`, { method: 'POST' });
    return res.json();
  },

  async getSignals() {
    const res = await apiFetch(`${API_BASE_URL}/stocks/signals`);
    return res.json();
  },

  async triggerScan() {
    const res = await apiFetch(`${API_BASE_URL}/stocks/scan`, { method: 'POST' });
    return res.json();
  },

  async getPortfolioGrowth(): Promise<Record<'USER' | 'GEMINI' | 'CLAUDE' | 'AI', { date: string; value: number }[]>> {
    const res = await apiFetch(`${API_BASE_URL}/trades/growth`);
    return res.json();
  },

  async getTradeHistory(agent: 'USER' | 'GEMINI' | 'CLAUDE' | 'AI'): Promise<TradeHistory[]> {
    const res = await apiFetch(`${API_BASE_URL}/trades/history?agent=${agent}`);
    return res.json();
  },

  async getBrokerFlow(date?: string): Promise<BrokerFlowResponse> {
    const url = date
      ? `${API_BASE_URL}/broker-flow?date=${date}`
      : `${API_BASE_URL}/broker-flow`;
    const res = await apiFetch(url);
    return res.json();
  },

  async getBrokerFlowDates(): Promise<{ dates: string[] }> {
    const res = await apiFetch(`${API_BASE_URL}/broker-flow/available-dates`);
    return res.json();
  },

  async scrapeBrokerFlow(date?: string): Promise<{ status: string; brokers_saved?: number; detail?: string }> {
    const url = date
      ? `${API_BASE_URL}/broker-flow/scrape?date=${date}`
      : `${API_BASE_URL}/broker-flow/scrape`;
    const res = await apiFetch(url, { method: 'POST' });
    return res.json();
  },

  async getTradeDetail(id: number): Promise<{
    id: number;
    ticker: string;
    name: string;
    sector: string;
    agent: 'USER' | 'GEMINI' | 'CLAUDE';
    action: 'BUY' | 'SELL';
    date: string;
    price: number;
    quantity_lots: number;
    quantity_shares: number;
    total_value: number;
    avg_buy_price: number | null;
    pnl: number | null;
    pnl_pct: number | null;
    strategy: string;
    notes: string;
    ohlcv: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
  }> {
    const res = await apiFetch(`${API_BASE_URL}/trades/${id}`);
    return res.json();
  },

  async advisorChat(payload: {
    message: string;
    history?: AdvisorTurn[];
    form?: Record<string, unknown>;
  }): Promise<AdvisorResponse> {
    const res = await apiFetch(`${API_BASE_URL}/advisor/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.status === 429) {
      const err = await res.json().catch(() => ({}));
      return {
        reply: err?.detail?.message || 'Kuota harian advisor habis.',
        intent: 'error',
        data: null,
        quota: err?.detail?.quota ?? null,
        confidence: null,
      };
    }
    if (!res.ok) {
      return { reply: 'Gagal menghubungi advisor. Periksa koneksi backend.', intent: 'error', data: null, quota: null, confidence: null };
    }
    return res.json();
  },

  // ── AI Porto (khusus tier dev) ──────────────────────────────────────────────
  async aiPortoChat(payload: { message: string; history?: AdvisorTurn[] }): Promise<AiPortoResponse> {
    const res = await apiFetch(`${API_BASE_URL}/ai-porto/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async getAiPorto(): Promise<AiPortoSnapshot> {
    const res = await apiFetch(`${API_BASE_URL}/ai-porto/portfolio`);
    return res.json();
  },

  // ── Watchlist (per user, butuh login) ──────────────────────────────────────
  async getWatchlist(): Promise<string[]> {
    const res = await apiFetch(`${API_BASE_URL}/watchlist`);
    if (!res.ok) return [];
    return (await res.json()).tickers ?? [];
  },

  async addWatchlist(ticker: string): Promise<boolean> {
    const res = await apiFetch(`${API_BASE_URL}/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker }),
    });
    return res.ok;
  },

  async removeWatchlist(ticker: string): Promise<boolean> {
    const res = await apiFetch(`${API_BASE_URL}/watchlist/${ticker}`, { method: 'DELETE' });
    return res.ok;
  },
};

export interface AdvisorTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface AdvisorQuota {
  used: number;
  limit: number | null;
  remaining: number | null;
}

export interface AdvisorResponse {
  reply: string;
  intent: string;
  data: any;
  quota: AdvisorQuota | null;
  confidence: number | null;
}
