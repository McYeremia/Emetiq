// IDX index membership (constituent tickers).
//
// NOTE: These lists are STATIC and APPROXIMATE. The backend does not yet store
// index membership, so the dashboard filters against this hardcoded map. IDX
// rebalances most indices twice a year (Feb & Aug) — refresh these arrays then,
// or move membership into the backend/data layer later.

export type IndexKey = 'IDX30' | 'LQ45' | 'SRI-KEHATI' | 'JII' | 'ISSI';

const IDX30: string[] = [
  'BBCA', 'BBRI', 'BMRI', 'BBNI', 'TLKM', 'ASII', 'UNTR', 'ICBP', 'INDF', 'KLBF',
  'GOTO', 'ADRO', 'ANTM', 'MDKA', 'AMRT', 'CPIN', 'ITMG', 'MEDC', 'PGAS', 'PGEO',
  'BRPT', 'SMGR', 'AKRA', 'INCO', 'ARTO', 'AMMN', 'BRIS', 'ISAT', 'TPIA', 'UNVR',
];

const LQ45: string[] = [
  ...IDX30,
  'BBTN', 'EXCL', 'HRUM', 'INKP', 'JPFA', 'MAPI', 'MAPA', 'MTEL', 'PTBA', 'SIDO',
  'TOWR', 'TKIM', 'ACES', 'CTRA', 'ESSA',
];

const SRI_KEHATI: string[] = [
  'ASII', 'BBCA', 'BBNI', 'BBRI', 'BMRI', 'BDMN', 'KLBF', 'TLKM', 'UNVR', 'UNTR',
  'JPFA', 'SMGR', 'AKRA', 'ANTM', 'PGAS', 'WIKA', 'WTON', 'BSDE', 'CTRA', 'INDF',
  'ICBP', 'MAPI', 'SIDO', 'TBIG', 'PJAA',
];

const JII: string[] = [
  'ADRO', 'AKRA', 'AMRT', 'AMMN', 'ANTM', 'ASII', 'BRPT', 'CPIN', 'ESSA', 'EXCL',
  'HRUM', 'ICBP', 'INCO', 'INDF', 'INKP', 'INTP', 'ITMG', 'KLBF', 'MDKA', 'MEDC',
  'MTEL', 'PGAS', 'PGEO', 'PTBA', 'SMGR', 'TLKM', 'TPIA', 'UNTR', 'UNVR', 'MAPI',
];

// ISSI = broad sharia universe. Not exhaustive (real ISSI has 600+ members);
// covers the sharia-compliant names likely present in this app's universe.
const ISSI: string[] = Array.from(new Set([
  ...JII,
  ...SRI_KEHATI.filter(t => !['BBCA', 'BBNI', 'BBRI', 'BMRI', 'BDMN'].includes(t)),
  'SIDO', 'JPFA', 'MAPA', 'ACES', 'CTRA', 'BSDE', 'PWON', 'SMRA', 'WIKA', 'WTON',
  'PTPP', 'ADHI', 'ERAA', 'RALS', 'LPPF', 'MNCN', 'SCMA', 'TOWR', 'TBIG', 'EMTK',
  'INKP', 'TKIM', 'INTP', 'SMBR', 'TINS', 'ELSA', 'AALI', 'LSIP', 'BWPT', 'DSNG',
]));

export const INDEX_MEMBERS: Record<IndexKey, string[]> = {
  'IDX30': IDX30,
  'LQ45': LQ45,
  'SRI-KEHATI': SRI_KEHATI,
  'JII': JII,
  'ISSI': ISSI,
};

export const INDEX_TABS: { key: 'ALL' | IndexKey; label: string }[] = [
  { key: 'ALL', label: 'Semua' },
  { key: 'IDX30', label: 'IDX30' },
  { key: 'LQ45', label: 'LQ45' },
  { key: 'SRI-KEHATI', label: 'SRI-KEHATI' },
  { key: 'JII', label: 'JII' },
  { key: 'ISSI', label: 'ISSI' },
];
