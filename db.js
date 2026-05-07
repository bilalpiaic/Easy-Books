const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, 'database.db');
const db = new Database(dbPath);

// Initialize schema
db.exec(`
  CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
  );

  CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jv_number TEXT UNIQUE,
    date TEXT NOT NULL,
    description TEXT,
    reference TEXT,
    party TEXT,
    payment_method TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
  );
`);

// Seed initial data if empty
const seed = () => {
  const accountCount = db.prepare('SELECT COUNT(*) as count FROM accounts').get().count;
  if (accountCount === 0) {
    const insertAccount = db.prepare('INSERT INTO accounts (code, name, type) VALUES (?, ?, ?)');
    const accounts = [
      ['1000', 'Cash in Hand', 'Asset'],
      ['1100', 'Accounts Receivable', 'Asset'],
      ['1200', 'Raw Material Inventory', 'Asset'],
      ['1300', 'Work-in-Progress', 'Asset'],
      ['2000', 'Accounts Payable', 'Liability'],
      ['2100', 'Advances Received', 'Liability'],
      ['3000', 'Owner Capital', 'Equity'],
      ['3100', 'Retained Earnings', 'Equity'],
      ['4000', 'CMT Services Income', 'Revenue'],
      ['4100', 'T-Shirt Sales', 'Revenue'],
      ['4200', 'Scrap Sales', 'Revenue'],
      ['4300', 'WC Orders Income', 'Revenue'],
      ['4900', 'Other Income', 'Revenue'],
      ['5000', 'Raw Material Expense', 'Expense'],
      ['5100', 'Labour & Wages', 'Expense'],
      ['5200', 'CMT Processing Expense', 'Expense'],
      ['5300', 'Rent & Utilities', 'Expense'],
      ['5400', 'Transport & Delivery', 'Expense'],
      ['5500', 'Machine Repair & Maintenance', 'Expense'],
      ['5900', 'Other Expenses', 'Expense']
    ];

    const transaction = db.transaction((accs) => {
      for (const acc of accs) insertAccount.run(acc);
    });
    transaction(accounts);
  }

  const settingCount = db.prepare('SELECT COUNT(*) as count FROM settings').get().count;
  if (settingCount === 0) {
    db.prepare('INSERT INTO settings (key, value) VALUES (?, ?)').run('org_name', 'Malik Enterprises');
  }
};

seed();

module.exports = db;
