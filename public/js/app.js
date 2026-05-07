// ─── STATE & CONFIG ──────────────────────────────────────────────────
const API_BASE = ''; // Same origin
let state = {
  user: {name:'', role:'Owner'},
  orgName: 'Malik Enterprises',
  accounts: [],
  cashAccountId: null,
  jvCounter: 110,
};
let charts = {};
let currentRole = 'Owner';
let txType = 'Revenue';
let txCatId = null;

// ─── DATA FETCHING ───────────────────────────────────────────────────
async function api(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'API Error');
  }
  return res.json();
}

async function loadInitialData() {
  try {
    const [settings, accounts] = await Promise.all([
      api('/api/settings'),
      api('/api/accounts')
    ]);
    state.orgName = settings.org_name || 'Malik Enterprises';
    state.accounts = accounts;
    
    // Dynamically find Cash account ID
    const cashAcc = accounts.find(a => a.name === 'Cash in Hand');
    state.cashAccountId = cashAcc ? cashAcc.id : 1; // Fallback to 1 if not found

    updateOrgUI();
    populateAccountLOVs();
  } catch (e) {
    showToast('Error loading data: ' + e.message);
  }
}

function updateOrgUI() {
  document.querySelectorAll('.login-title, .header-name').forEach(el => el.textContent = state.orgName);
  const initials = state.orgName.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
  document.querySelectorAll('.login-logo, .header-logo').forEach(el => el.textContent = initials);
}

function populateAccountLOVs() {
  const coaSels = [document.getElementById('ledAccount')];
  state.accounts.forEach(acc => {
    const opt = `<option value="${acc.id}">${acc.code} - ${acc.name}</option>`;
    coaSels.forEach(sel => { if(sel) sel.innerHTML += opt; });
  });
}

// ─── LOGIN ────────────────────────────────────────────────────────────
function selectRole(el) {
  document.querySelectorAll('.role-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
}

async function doLogin() {
  const name = document.getElementById('loginName').value.trim() || 'User';
  const roleEl = document.querySelector('.role-card.selected');
  const role = roleEl ? roleEl.dataset.role : 'Owner';

  state.user = {name, role};
  currentRole = role;

  await loadInitialData();

  document.getElementById('loginScreen').style.display = 'none';
  const app = document.getElementById('app');
  app.classList.add('visible');

  const initials = name.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
  document.getElementById('headerAvatar').textContent = initials;
  document.getElementById('headerRole').textContent = role.toUpperCase();
  document.getElementById('sidebarName').textContent = name;
  document.getElementById('sidebarRole').textContent = role;
  document.getElementById('sidebarAvatar').textContent = initials;

  if (role === 'Manager') {
    document.querySelector('[data-page="entry"]').style.display = 'none';
  }

  initApp();
  navigate('dashboard');
}

function logout() {
  document.getElementById('loginScreen').style.display = 'flex';
  document.getElementById('app').classList.remove('visible');
  destroyCharts();
}

// ─── HELPERS ─────────────────────────────────────────────────────────
const fmt = n => Math.round(n||0).toLocaleString('en-PK');
const fmtPKR = n => 'PKR ' + fmt(n);
const pct = (a,b) => b ? ((a/b)*100).toFixed(1)+'%' : '0%';

function showToast(msg, dur=2800) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), dur);
}

// ─── NAVIGATION ───────────────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const target = document.getElementById('page-'+page);
  if (target) target.classList.add('active');
  document.querySelector('[data-page="'+page+'"]')?.classList.add('active');

  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('overlay').classList.remove('open');

  const renders = {
    dashboard: renderDashboard,
    journal: renderJournal,
    ledger: renderLedger,
    coa: renderCOA,
    trialbalance: renderTB,
    pl: renderPL,
    balance: renderBS,
    cashflow: renderCF
  };
  if (renders[page]) renders[page]();
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('open');
}

// ─── DASHBOARD ────────────────────────────────────────────────────────
function destroyCharts() {
  Object.values(charts).forEach(c => { try{c.destroy()}catch(e){} });
  charts = {};
}

async function renderDashboard() {
  destroyCharts();
  const data = await api('/api/reports/dashboard');
  const totalRev = data.summary.total_revenue || 0;
  const totalExp = data.summary.total_expense || 0;
  const netP = totalRev - totalExp;

  document.getElementById('kpiGrid').innerHTML = `
    <div class="kpi"><div class="kpi-label">Total Revenue</div><div class="kpi-value kpi-sm">PKR ${fmt(totalRev)}</div></div>
    <div class="kpi green"><div class="kpi-label">Net Profit</div><div class="kpi-value kpi-sm">PKR ${fmt(netP)}</div></div>
    <div class="kpi red"><div class="kpi-label">Total Expenses</div><div class="kpi-value kpi-sm">PKR ${fmt(totalExp)}</div></div>
    <div class="kpi blue"><div class="kpi-label">Transactions</div><div class="kpi-value kpi-sm">${data.recent.length}</div></div>
  `;

  document.getElementById('recentTbody').innerHTML = data.recent.map(e => `
    <tr onclick="viewEntry(${e.id})" style="cursor:pointer">
      <td class="td-mono">${e.jv_number}</td>
      <td>${e.date}</td>
      <td>Transaction</td>
      <td>General</td>
      <td>${e.description}</td>
      <td class="td-right">${fmt(e.total_amount)}</td>
      <td class="td-right">0</td>
    </tr>
  `).join('');
}

// ─── NEW REPORTS ──────────────────────────────────────────────────────

async function renderJournal() {
  const start = document.getElementById('jouStart').value;
  const end = document.getElementById('jouEnd').value;
  const search = document.getElementById('jouSearch').value.toLowerCase();

  let path = '/api/reports/journal';
  if (start && end) path += `?start=${start}&end=${end}`;

  const data = await api(path);
  const filtered = search ? data.filter(r =>
    r.description.toLowerCase().includes(search) ||
    r.jv_number.toLowerCase().includes(search) ||
    r.account_name.toLowerCase().includes(search)
  ) : data;

  document.getElementById('jouTbody').innerHTML = filtered.map(r => `
    <tr onclick="viewEntry(${r.id})" style="cursor:pointer">
      <td class="td-mono">${r.jv_number}</td>
      <td>${r.date}</td>
      <td>${r.account_name}</td>
      <td>${r.description}</td>
      <td class="td-right">${r.debit > 0 ? fmt(r.debit) : '—'}</td>
      <td class="td-right">${r.credit > 0 ? fmt(r.credit) : '—'}</td>
    </tr>
  `).join('');
}

async function renderLedger() {
  const accId = document.getElementById('ledAccount').value;
  if (!accId) return;

  const start = document.getElementById('ledStart').value;
  const end = document.getElementById('ledEnd').value;
  let path = `/api/reports/ledger/${accId}`;
  if (start && end) path += `?start=${start}&end=${end}`;

  const data = await api(path);
  let balance = 0;

  document.getElementById('ledTbody').innerHTML = data.map(r => {
    balance += (r.debit - r.credit);
    return `
      <tr onclick="viewEntry(${r.id})" style="cursor:pointer">
        <td>${r.date}</td>
        <td class="td-mono">${r.jv_number}</td>
        <td>${r.description}</td>
        <td class="td-right">${r.debit > 0 ? fmt(r.debit) : '—'}</td>
        <td class="td-right">${r.credit > 0 ? fmt(r.credit) : '—'}</td>
        <td class="td-right">${fmt(Math.abs(balance))} ${balance >= 0 ? 'Dr' : 'Cr'}</td>
      </tr>
    `;
  }).join('');
}

async function renderCOA() {
  const data = await api('/api/accounts');
  document.getElementById('coaTbody').innerHTML = data.map(a => `
    <tr>
      <td class="td-mono">${a.code}</td>
      <td>${a.name}</td>
      <td>${a.type}</td>
      <td><span class="pill pill-green">Active</span></td>
    </tr>
  `).join('');
}

async function renderTB() {
  const date = document.getElementById('tbDate').value;
  let path = '/api/reports/trial-balance';
  if (date) path += `?date=${date}`;

  const data = await api(path);
  let totalDr = 0, totalCr = 0;

  document.getElementById('tbTbody').innerHTML = data.map(r => {
    totalDr += r.total_debit || 0;
    totalCr += r.total_credit || 0;
    return `
      <tr>
        <td class="td-mono">${r.code}</td>
        <td>${r.name}</td>
        <td class="td-right">${r.total_debit > 0 ? fmt(r.total_debit) : '—'}</td>
        <td class="td-right">${r.total_credit > 0 ? fmt(r.total_credit) : '—'}</td>
      </tr>
    `;
  }).join('');

  document.getElementById('tbTotalDr').textContent = fmt(totalDr);
  document.getElementById('tbTotalCr').textContent = fmt(totalCr);
}

// ─── TRANSACTION ENTRY ────────────────────────────────────────────────
function setType(t) {
  txType = t;
  document.getElementById('btnRev').className = 'type-btn' + (t==='Revenue' ? ' act-rev' : '');
  document.getElementById('btnExp').className = 'type-btn' + (t==='Expense' ? ' act-exp' : '');
}

function selCat(el) {
  document.querySelectorAll('.cat-chip').forEach(c => c.classList.remove('sel'));
  el.classList.add('sel');
  const catName = el.textContent;
  const acc = state.accounts.find(a => a.name.includes(catName) || catName.includes(a.name));
  txCatId = acc ? acc.id : null;
}

function updBal() {
  const dr = parseFloat(document.getElementById('txDebit').value) || 0;
  const cr = parseFloat(document.getElementById('txCredit').value) || 0;
  const diff = dr - cr;
  const el = document.getElementById('balVal');
  if (diff === 0 && (dr>0||cr>0)) { el.textContent='✓ Balanced'; el.className='bal-val ok'; }
  else { el.textContent='PKR ' + fmt(diff); el.className='bal-val off'; }
}

async function viewEntry(id) {
  const data = await api(`/api/transactions/${id}`);
  // Populate form in view mode (simplified for now)
  navigate('entry');
  document.getElementById('txDate').value = data.date;
  document.getElementById('txDesc').value = data.description;
  document.getElementById('txRef').value = data.reference;
  document.getElementById('txParty').value = data.party;
  // This is a basic view, usually you'd show all entries
  showToast('Viewing Entry ' + data.jv_number);
}

document.getElementById('txForm').addEventListener('submit', async e => {
  e.preventDefault();
  const dr = parseFloat(document.getElementById('txDebit').value) || 0;
  const cr = parseFloat(document.getElementById('txCredit').value) || 0;

  if (!txCatId) return showToast('Please select a category');

  // Revenue: Dr Cash, Cr Income (txCatId)
  // Expense: Dr Expense (txCatId), Cr Cash
  const entries = txType === 'Revenue' ? [
    { account_id: state.cashAccountId, debit: cr, credit: 0 },
    { account_id: txCatId, debit: 0, credit: cr }
  ] : [
    { account_id: txCatId, debit: dr, credit: 0 },
    { account_id: state.cashAccountId, debit: 0, credit: dr }
  ];

  const payload = {
    date: document.getElementById('txDate').value,
    description: document.getElementById('txDesc').value,
    reference: document.getElementById('txRef').value,
    party: document.getElementById('txParty').value,
    payment_method: document.getElementById('txMethod').value,
    entries: entries
  };

  try {
    const res = await api('/api/transactions', { method: 'POST', body: JSON.stringify(payload) });
    showToast('✓ Entry ' + res.jv_number + ' posted');
    e.target.reset();
    navigate('journal');
  } catch (err) {
    showToast('Error: ' + err.message);
  }
});

// ─── PLACEHOLDERS FOR REMAINING REPORTS ───────────────────────────────
async function renderPL() {
  const data = await api('/api/reports/income-statement');
  const rev = data.filter(r => r.type === 'Revenue');
  const exp = data.filter(r => r.type === 'Expense');
  
  const totalRev = rev.reduce((s, r) => s + (r.total_credit - r.total_debit), 0);
  const totalExp = exp.reduce((s, r) => s + (r.total_debit - r.total_credit), 0);
  const netP = totalRev - totalExp;

  const row = (label, amt, cls='') => `
    <div class="report-row ${cls}">
      <div style="padding-left:1rem">${label}</div>
      <div class="rr-val">${amt >= 0 ? fmt(amt) : '(' + fmt(-amt) + ')'}</div>
      <div class="rr-pct">${totalRev ? pct(Math.abs(amt), totalRev) : ''}</div>
    </div>`;

  document.getElementById('plContent').innerHTML = `
    <div class="card" style="margin-bottom:1.2rem;overflow:hidden">
      <div class="report-row header"><div>Revenue</div><div class="rr-val">Amount</div><div class="rr-pct">% Revenue</div></div>
      ${rev.map(r => row(r.name, r.total_credit - r.total_debit)).join('')}
      <div class="report-row subtotal"><div>TOTAL REVENUE</div><div class="rr-val">${fmt(totalRev)}</div><div class="rr-pct">100%</div></div>
    </div>
    <div class="card" style="margin-bottom:1.2rem;overflow:hidden">
      <div class="report-row header"><div>Expenses</div><div class="rr-val">Amount</div><div class="rr-pct">% Revenue</div></div>
      ${exp.map(r => row(r.name, r.total_debit - r.total_credit)).join('')}
      <div class="report-row subtotal"><div>TOTAL EXPENSES</div><div class="rr-val">${fmt(totalExp)}</div><div class="rr-pct">${pct(totalExp, totalRev)}</div></div>
    </div>
    <div class="card" style="overflow:hidden">
      <div class="report-row total"><div>NET PROFIT</div><div class="rr-val">PKR ${fmt(netP)}</div><div class="rr-pct">${totalRev ? pct(netP, totalRev) : ''}</div></div>
    </div>
  `;
}
function renderBS() { document.getElementById('bsContent').innerHTML = '<div class="empty-state">Report under migration</div>'; }
function renderCF() { document.getElementById('cfContent').innerHTML = '<div class="empty-state">Report under migration</div>'; }

// ─── INIT ─────────────────────────────────────────────────────────────
function initApp() {
  document.getElementById('txDate').value = new Date().toISOString().split('T')[0];
}

// Start app
loadInitialData();
