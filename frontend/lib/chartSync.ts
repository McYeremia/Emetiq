// Sync via time range (not logical/bar index) so charts with different
// data lengths (RSI starts at bar 14, MACD at bar 25, etc.) always show
// the same date window.
export type ChartSyncCoordinator = {
  register: (id: string, apply: (from: unknown, to: unknown) => void) => () => void;
  notify: (sourceId: string, from: unknown, to: unknown) => void;
};

export function createChartSync(): ChartSyncCoordinator {
  const handlers = new Map<string, (from: unknown, to: unknown) => void>();
  let busy = false;
  return {
    register(id, apply) {
      handlers.set(id, apply);
      return () => { handlers.delete(id); };
    },
    notify(sourceId, from, to) {
      if (busy) return;
      busy = true;
      handlers.forEach((fn, id) => { if (id !== sourceId) fn(from, to); });
      busy = false;
    },
  };
}
