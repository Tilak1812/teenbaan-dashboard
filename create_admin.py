import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "orders.db"

def create_admin():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        # Check if admin exists
        c.execute("SELECT * FROM users WHERE username = ?", ('admin',))
        admin = c.fetchone()
        
        if admin:
            print(f"✅ Admin user exists: {admin}")
            # Update password
            hashed_pw = generate_password_hash('admin123')
            c.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, 'admin'))
            conn.commit()
            print("✅ Password updated to: admin123")
        else:
            # Create admin user
            hashed_pw = generate_password_hash('admin123')
            c.execute('''
                INSERT INTO users (username, email, password, role)
                VALUES (?, ?, ?, ?)
            ''', ('admin', 'admin@teenbaan.com', hashed_pw, 'admin'))
            conn.commit()
            print("✅ Admin user created successfully!")
            print("   Username: admin")
            print("   Password: admin123")
        
        # Verify
        c.execute("SELECT id, username, role FROM users WHERE username = ?", ('admin',))
        result = c.fetchone()
        print(f"\n📋 Database Status: {result}")

if __name__ == '__main__':
    create_admin()