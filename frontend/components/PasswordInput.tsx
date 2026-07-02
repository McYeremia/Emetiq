'use client';

import { useState } from 'react';

const HAIR = '#ECEBE6';
const MUTED = '#56564F';
const INK = '#14140F';

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '11px 44px 11px 14px', borderRadius: 11, border: `1px solid ${HAIR}`,
  background: '#fff', fontSize: 14.5, color: INK, outline: 'none',
};

const EyeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeOffIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.9 4.2A9.8 9.8 0 0 1 12 4c6.5 0 10 8 10 8a17.6 17.6 0 0 1-2.4 3.5M6.1 6.1A17.6 17.6 0 0 0 2 12s3.5 7 10 7a9.8 9.8 0 0 0 4.1-.9" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M3 3l18 18" />
  </svg>
);

// Input password dengan tombol mata untuk toggle tampil/sembunyi.
// Menerima props <input> standar (value, onChange, placeholder, minLength, dll).
export default function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input {...props} type={show ? 'text' : 'password'} style={inputStyle} />
      <button
        type="button"
        onClick={() => setShow(s => !s)}
        aria-label={show ? 'Sembunyikan password' : 'Tampilkan password'}
        style={{
          position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer', padding: 6,
          display: 'flex', alignItems: 'center', color: MUTED, lineHeight: 0,
        }}
      >
        {show ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  );
}
