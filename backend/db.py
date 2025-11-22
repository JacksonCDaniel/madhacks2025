import sqlite3
import json
import uuid
from datetime import datetime

_default_db_path = './data.db'


def _now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def init_db(db_path: str = None):
    """Initialize the SQLite DB and create tables if they don't exist."""
    path = db_path or _default_db_path
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            user_id TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            system_message TEXT,
            metadata TEXT,
            last_summary_message_id TEXT
        )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)')

        cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tokens_est INTEGER,
            created_at TEXT NOT NULL,
            metadata TEXT
        )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_messages_conv_created_at ON messages(conversation_id, created_at)')
        conn.commit()
    finally:
        conn.close()


def _connect(db_path: str = None):
    path = db_path or _default_db_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def create_conversation(user_id=None, system_message=None, metadata=None, db_path: str = None):
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        conv_id = str(uuid.uuid4())
        now = _now_iso()
        meta_text = json.dumps(metadata or {})
        cur.execute(
            "INSERT INTO conversations (id, created_at, updated_at, user_id, system_message, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, now, now, user_id, system_message, meta_text),
        )
        conn.commit()
        return conv_id
    finally:
        conn.close()


def get_conversation(conversation_id, db_path: str = None):
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row['id'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'user_id': row['user_id'],
            'status': row['status'],
            'system_message': row['system_message'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {},
            'last_summary_message_id': row['last_summary_message_id'],
        }
    finally:
        conn.close()


def delete_conversation(conversation_id, db_path: str = None):
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        deleted = cur.rowcount > 0
        if deleted:
            cur.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
        conn.commit()
        return deleted
    finally:
        conn.close()


def insert_message(conversation_id, role, content, metadata=None, db_path: str = None):
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        msg_id = str(uuid.uuid4())
        created_at = _now_iso()
        tokens_est = max(1, int(len(content) / 4)) if content else None
        meta_text = json.dumps(metadata or {})
        cur.execute(
            "INSERT INTO messages (id, conversation_id, role, content, tokens_est, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, tokens_est, created_at, meta_text),
        )
        # update conversation updated_at
        cur.execute('UPDATE conversations SET updated_at = ? WHERE id = ?', (created_at, conversation_id))
        conn.commit()
        return msg_id
    finally:
        conn.close()


def get_messages(conversation_id, since=None, limit=100, db_path: str = None):
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        if since:
            cur.execute('SELECT * FROM messages WHERE conversation_id = ? AND created_at > ? ORDER BY created_at ASC LIMIT ?', (conversation_id, since, limit))
        else:
            cur.execute('SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?', (conversation_id, limit))
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                'id': r['id'],
                'conversation_id': r['conversation_id'],
                'role': r['role'],
                'content': r['content'],
                'tokens_est': r['tokens_est'],
                'created_at': r['created_at'],
                'metadata': json.loads(r['metadata']) if r['metadata'] else {},
            })
        return out
    finally:
        conn.close()


def mark_messages_summarized(message_ids, summary_message_id, db_path: str = None):
    if not message_ids:
        return
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        for mid in message_ids:
            # set metadata.summarized = true
            cur.execute('SELECT metadata FROM messages WHERE id = ?', (mid,))
            row = cur.fetchone()
            if not row:
                continue
            meta = json.loads(row['metadata']) if row['metadata'] else {}
            meta['summarized'] = True
            cur.execute('UPDATE messages SET metadata = ? WHERE id = ?', (json.dumps(meta), mid))
        # update conversation last_summary_message_id
        cur.execute('UPDATE conversations SET last_summary_message_id = ? WHERE id = (SELECT conversation_id FROM messages WHERE id = ?)', (summary_message_id, message_ids[0]))
        conn.commit()
    finally:
        conn.close()

