'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  visible: boolean;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const ICON: Record<ToastType, string> = {
  success: '✓',
  error: '✕',
  info: '◆',
};

const COLOR: Record<ToastType, string> = {
  success: '#22C55E',
  error: '#EF4444',
  info: '#3B82F6',
};

let _idCounter = 0;
const MAX_TOASTS = 3;
const AUTO_DISMISS_MS = 3500;
const ANIM_OUT_MS = 300;

function ToastItem({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  return (
    <div
      style={{
        transform: item.visible ? 'translateX(0)' : 'translateX(110%)',
        opacity: item.visible ? 1 : 0,
        transition: `transform ${ANIM_OUT_MS}ms cubic-bezier(0.4,0,0.2,1), opacity ${ANIM_OUT_MS}ms ease`,
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        background: '#1a1a1a',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '12px',
        padding: '12px 14px',
        minWidth: '240px',
        maxWidth: '320px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        fontFamily: 'var(--font-geist-mono, monospace)',
        fontSize: '11px',
        letterSpacing: '0.01em',
        color: '#e5e5e5',
        pointerEvents: 'all',
        cursor: 'default',
      }}
    >
      <span
        style={{
          color: COLOR[item.type],
          fontWeight: 900,
          fontSize: '13px',
          lineHeight: '1',
          marginTop: '1px',
          flexShrink: 0,
        }}
      >
        {ICON[item.type]}
      </span>
      <span style={{ flex: 1, lineHeight: '1.5', wordBreak: 'break-word' }}>
        {item.message}
      </span>
      <button
        onClick={() => onDismiss(item.id)}
        style={{
          background: 'none',
          border: 'none',
          color: 'rgba(255,255,255,0.3)',
          cursor: 'pointer',
          fontSize: '13px',
          lineHeight: '1',
          padding: '0 0 0 4px',
          flexShrink: 0,
          marginTop: '1px',
        }}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    // Animate out first
    setToasts(prev => prev.map(t => t.id === id ? { ...t, visible: false } : t));
    const removeTimer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, ANIM_OUT_MS);
    // Clean up old auto-dismiss timer if exists
    const existing = timersRef.current.get(id);
    if (existing) {
      clearTimeout(existing);
      timersRef.current.delete(id);
    }
    timersRef.current.set(-id, removeTimer); // store with negative id to avoid collision
  }, []);

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = ++_idCounter;

    setToasts(prev => {
      // If already at max, mark the oldest as invisible so it animates out
      let next = prev;
      if (prev.length >= MAX_TOASTS) {
        const oldest = prev[0];
        next = prev.slice(1); // remove oldest immediately when we're at max
        // Cancel its auto-dismiss timer
        const t = timersRef.current.get(oldest.id);
        if (t) {
          clearTimeout(t);
          timersRef.current.delete(oldest.id);
        }
      }
      return [...next, { id, message, type, visible: false }];
    });

    // Animate in after next paint
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setToasts(prev => prev.map(t => t.id === id ? { ...t, visible: true } : t));
      });
    });

    // Auto-dismiss
    const timer = setTimeout(() => {
      dismiss(id);
    }, AUTO_DISMISS_MS);
    timersRef.current.set(id, timer);
  }, [dismiss]);

  // Cleanup on unmount
  useEffect(() => {
    const ref = timersRef.current;
    return () => {
      ref.forEach(t => clearTimeout(t));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          alignItems: 'flex-end',
          pointerEvents: 'none',
        }}
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map(item => (
          <ToastItem key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used inside <ToastProvider>');
  }
  return ctx;
}
