import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Store:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / 'data/notepilot.db')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY, name TEXT, kind TEXT, path TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS pages (
              document_id TEXT, number INTEGER, text TEXT, original TEXT, status TEXT,
              PRIMARY KEY(document_id, number));
            CREATE TABLE IF NOT EXISTS reviews (
              issue_id TEXT PRIMARY KEY, decision TEXT, note TEXT, updated TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS attempts (
              id INTEGER PRIMARY KEY, concept TEXT, correct INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
            if 'course_id' not in {r['name'] for r in c.execute('PRAGMA table_info(documents)')}:
                c.execute("ALTER TABLE documents ADD COLUMN course_id TEXT DEFAULT 'fluid'")

    def connect(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def rows(self, sql, params=()):
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, params)]

    def documents(self):
        return self.rows('SELECT * FROM documents ORDER BY created DESC, name')

    def pages(self):
        return self.rows('''SELECT p.*, d.name, d.kind, d.path, d.course_id FROM pages p
                           JOIN documents d ON d.id=p.document_id ORDER BY d.name,p.number''')

    def add(self, doc_id, name, kind, path, pages):
        with self.connect() as c:
            if c.execute('SELECT 1 FROM documents WHERE id=?', (doc_id,)).fetchone():
                return False
            c.execute('INSERT INTO documents(id,name,kind,path) VALUES(?,?,?,?)', (doc_id,name,kind,str(path)))
            c.executemany('INSERT INTO pages VALUES(?,?,?,?,?)',
                          [(doc_id,p['number'],p['text'],p['text'],p['status']) for p in pages])
        return True

    def correct(self, doc_id, number, text):
        with self.connect() as c:
            c.execute("UPDATE pages SET text=?,status='verified' WHERE document_id=? AND number=?", (text,doc_id,number))
            # A changed source invalidates previous decisions.
            c.execute('DELETE FROM reviews')

    def review(self, issue_id, decision, note):
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO reviews(issue_id,decision,note) VALUES(?,?,?)', (issue_id,decision,note))

    def attempt(self, concept, correct):
        with self.connect() as c:
            c.execute('INSERT INTO attempts(concept,correct) VALUES(?,?)', (concept,int(correct)))
