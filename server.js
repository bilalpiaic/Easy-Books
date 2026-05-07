const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');
const db = require('./db');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));

// --- Settings API ---
app.get('/api/settings', (req, res) => {
  const settings = db.prepare('SELECT * FROM settings').all();
  const result = {};
  settings.forEach(s => result[s.key] = s.value);
  res.json(result);
});

app.patch('/api/settings', (req, res) => {
  const { org_name } = req.body;
  if (org_name) {
    db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)').run('org_name', org_name);
  }
  res.json({ success: true });
});

// --- Accounts API ---
app.get('/api/accounts', (req, res) => {
  const accounts = db.prepare('SELECT * FROM accounts ORDER BY code').all();
  res.json(accounts);
});

// --- Transactions API ---
app.get('/api/transactions/:id', (req, res) => {
  const transaction = db.prepare('SELECT * FROM transactions WHERE id = ?').get(req.params.id);
  if (!transaction) return res.status(404).json({ error: 'Not found' });

  const entries = db.prepare(`
    SELECT je.*, a.name as account_name, a.type as account_type
    FROM journal_entries je
    JOIN accounts a ON je.account_id = a.id
    WHERE transaction_id = ?
  `).all(req.params.id);

  res.json({ ...transaction, entries });
});

app.post('/api/transactions', (req, res) => {
  const { date, description, reference, party, payment_method, notes, entries } = req.body;

  // Basic validation: Dr must equal Cr
  const totalDr = entries.reduce((s, e) => s + (parseFloat(e.debit) || 0), 0);
  const totalCr = entries.reduce((s, e) => s + (parseFloat(e.credit) || 0), 0);

  if (Math.abs(totalDr - totalCr) > 0.01) {
    return res.status(400).json({ error: 'Transaction not balanced' });
  }

  // Validate account IDs exist
  const accountIds = entries.map(e => e.account_id);
  const existingAccounts = db.prepare(`SELECT id FROM accounts WHERE id IN (${accountIds.map(() => '?').join(',')})`).all(accountIds);
  if (existingAccounts.length !== new Set(accountIds).size) {
    return res.status(400).json({ error: 'One or more invalid account IDs' });
  }

  const transaction = db.transaction(() => {
    // Generate JV number
    const lastJv = db.prepare('SELECT jv_number FROM transactions ORDER BY id DESC LIMIT 1').get();
    let nextNum = 110;
    if (lastJv) {
      const match = lastJv.jv_number.match(/JV-(\d+)/);
      if (match) nextNum = parseInt(match[1]) + 1;
    }
    const jv_number = `JV-${nextNum}`;

    const info = db.prepare(`
      INSERT INTO transactions (jv_number, date, description, reference, party, payment_method, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(jv_number, date, description, reference, party, payment_method, notes);

    const transactionId = info.lastInsertRowid;
    const insertEntry = db.prepare(`
      INSERT INTO journal_entries (transaction_id, account_id, debit, credit)
      VALUES (?, ?, ?, ?)
    `);

    for (const entry of entries) {
      insertEntry.run(transactionId, entry.account_id, entry.debit || 0, entry.credit || 0);
    }

    return { id: transactionId, jv_number };
  });

  try {
    const result = transaction();
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// --- Reports API ---
app.get('/api/reports/journal', (req, res) => {
  const { start, end } = req.query;
  let query = `
    SELECT t.id, t.jv_number, t.date, t.description, t.party,
           je.debit, je.credit, a.name as account_name
    FROM transactions t
    JOIN journal_entries je ON t.id = je.transaction_id
    JOIN accounts a ON je.account_id = a.id
  `;
  const params = [];
  if (start && end) {
    query += ` WHERE t.date BETWEEN ? AND ?`;
    params.push(start, end);
  }
  query += ` ORDER BY t.date DESC, t.id DESC`;

  const rows = db.prepare(query).all(params);
  res.json(rows);
});

app.get('/api/reports/trial-balance', (req, res) => {
  const { date } = req.query;
  let query = `
    SELECT a.code, a.name, a.type,
           SUM(je.debit) as total_debit,
           SUM(je.credit) as total_credit
    FROM accounts a
    LEFT JOIN journal_entries je ON a.id = je.account_id
    LEFT JOIN transactions t ON je.transaction_id = t.id
  `;
  const params = [];
  if (date) {
    query += ` WHERE t.date <= ? OR t.date IS NULL`;
    params.push(date);
  }
  query += ` GROUP BY a.id HAVING total_debit > 0 OR total_credit > 0 ORDER BY a.code`;

  const rows = db.prepare(query).all(params);
  res.json(rows);
});

app.get('/api/reports/ledger/:accountId', (req, res) => {
  const { start, end } = req.query;
  const accountId = req.params.accountId;

  let query = `
    SELECT t.id, t.date, t.jv_number, t.description, je.debit, je.credit
    FROM journal_entries je
    JOIN transactions t ON je.transaction_id = t.id
    WHERE je.account_id = ?
  `;
  const params = [accountId];
  if (start && end) {
    query += ` AND t.date BETWEEN ? AND ?`;
    params.push(start, end);
  }
  query += ` ORDER BY t.date ASC, t.id ASC`;

  const rows = db.prepare(query).all(params);
  res.json(rows);
});

app.get('/api/reports/dashboard', (req, res) => {
  // Simple summary for dashboard
  const summary = db.prepare(`
    SELECT
      SUM(CASE WHEN a.type = 'Revenue' THEN je.credit - je.debit ELSE 0 END) as total_revenue,
      SUM(CASE WHEN a.type = 'Expense' THEN je.debit - je.credit ELSE 0 END) as total_expense
    FROM journal_entries je
    JOIN accounts a ON je.account_id = a.id
  `).get();

  const recent = db.prepare(`
    SELECT t.id, t.jv_number, t.date, t.description,
           SUM(je.debit) as total_amount
    FROM transactions t
    JOIN journal_entries je ON t.id = je.transaction_id
    GROUP BY t.id
    ORDER BY t.date DESC, t.id DESC
    LIMIT 10
  `).all();

  res.json({ summary, recent });
});

app.get('/api/reports/income-statement', (req, res) => {
  const { start, end } = req.query;
  let query = `
    SELECT a.name, a.type,
           SUM(je.debit) as total_debit,
           SUM(je.credit) as total_credit
    FROM accounts a
    LEFT JOIN journal_entries je ON a.id = je.account_id
    LEFT JOIN transactions t ON je.transaction_id = t.id
    WHERE a.type IN ('Revenue', 'Expense')
  `;
  const params = [];
  if (start && end) {
    query += ` AND t.date BETWEEN ? AND ?`;
    params.push(start, end);
  }
  query += ` GROUP BY a.id ORDER BY a.type DESC, a.code`;

  const rows = db.prepare(query).all(params);
  res.json(rows);
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
