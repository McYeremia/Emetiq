import { redirect } from 'next/navigation';

// Backtest is now merged into the Screener as its "Backtest" tab.
export default function BacktestRedirect() {
  redirect('/screener?tab=backtest');
}
