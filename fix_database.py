import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "orders.db"

def fix_database():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        # Add missing columns to users table
        try:
            c.execute("ALTER TABLE users ADD COLUMN email TEXT")
            print("✅ Added 'email' column")
        except:
            print("⚠️ 'email' column already exists")
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            print("✅ Added 'role' column")
        except:
            print("⚠️ 'role' column already exists")
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
            print("✅ Added 'status' column")
        except:
            print("⚠️ 'status' column already exists")
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
            print("✅ Added 'created_at' column")
        except:
            print("⚠️ 'created_at' column already exists")
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
            print("✅ Added 'last_login' column")
        except:
            print("⚠️ 'last_login' column already exists")
        
        # Add missing column to orders table
        try:
            c.execute("ALTER TABLE orders ADD COLUMN day TEXT")
            print("✅ Added 'day' column to orders")
        except:
            print("⚠️ 'day' column already exists in orders")
        
        # Create activity_log table
        c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        print("✅ Created activity_log table")
        
        # Update existing users with missing data
        c.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        c.execute("UPDATE users SET status = 'active' WHERE status IS NULL")
        c.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
        
        # Ensure admin exists
        c.execute("SELECT id FROM users WHERE username = ?", ('admin',))
        if not c.fetchone():
            hashed_pw = generate_password_hash('admin123')
            c.execute('INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                      ('admin', 'admin@teenbaan.com', hashed_pw, 'admin', 'active', 'CURRENT_TIMESTAMP'))
            print("✅ Created admin user")
        
        conn.commit()
        print("\n✅ Database fixed successfully!")

if __name__ == '__main__':
    fix_database()