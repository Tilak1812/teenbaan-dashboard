import sqlite3
import os

DATABASE = "orders.db"

def migrate_database():
    """Complete database migration"""
    if not os.path.exists(DATABASE):
        print("Database doesn't exist. Creating new database...")
        return
    
    print("Starting database migration...")
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Check existing tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in c.fetchall()]
    print(f"Existing tables: {existing_tables}")
    
    # ==================== USERS TABLE ====================
    if 'users' in existing_tables:
        c.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in c.fetchall()]
        
        if 'email' not in user_columns:
            try:
                c.execute("ALTER TABLE users ADD COLUMN email TEXT")
                print("✅ Added 'email' column to users table")
            except:
                pass
        
        if 'role' not in user_columns:
            try:
                c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
                print("✅ Added 'role' column to users table")
            except:
                pass
        
        if 'status' not in user_columns:
            try:
                c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
                print("✅ Added 'status' column to users table")
            except:
                pass
        
        if 'created_at' not in user_columns:
            try:
                c.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print("✅ Added 'created_at' column to users table")
            except:
                pass
        
        if 'last_login' not in user_columns:
            try:
                c.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
                print("✅ Added 'last_login' column to users table")
            except:
                pass
    
    # ==================== ORDERS TABLE ====================
    if 'orders' in existing_tables:
        c.execute("PRAGMA table_info(orders)")
        order_columns = [row[1] for row in c.fetchall()]
        print(f"Orders columns: {order_columns}")
        
        if 'status' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'completed'")
                print("✅ Added 'status' column to orders table")
            except Exception as e:
                print(f"⚠️ Error adding 'status': {e}")
        
        if 'customer_name' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN customer_name TEXT")
                print("✅ Added 'customer_name' column to orders table")
            except Exception as e:
                print(f"⚠️ Error adding 'customer_name': {e}")
        
        if 'customer_email' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN customer_email TEXT")
                print("✅ Added 'customer_email' column to orders table")
            except Exception as e:
                print(f"⚠️ Error adding 'customer_email': {e}")
        
        if 'notes' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN notes TEXT")
                print("✅ Added 'notes' column to orders table")
            except Exception as e:
                print(f"⚠️ Error adding 'notes': {e}")
        
        if 'created_at' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print("✅ Added 'created_at' column to orders table")
            except Exception as e:
                print(f"⚠️ Error adding 'created_at': {e}")
        
        if 'updated_at' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print("✅ Added 'updated_at' column to orders table")
            except Exception as e:
                print(f"⚠️ Error adding 'updated_at': {e}")
    
    # ==================== CATEGORIES TABLE ====================
    if 'categories' not in existing_tables:
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        print("✅ Created 'categories' table")
        
        # Add default categories
        default_categories = [
            ('Electronics', 'Electronic devices and accessories'),
            ('Clothing', 'Apparel and fashion'),
            ('Food', 'Food and beverages'),
            ('Home', 'Home and garden'),
            ('Sports', 'Sports and outdoor')
        ]
        c.executemany('INSERT INTO categories (name, description) VALUES (?, ?)', default_categories)
        print("✅ Added default categories")
    else:
        # Check and add columns to existing categories table
        c.execute("PRAGMA table_info(categories)")
        cat_columns = [row[1] for row in c.fetchall()]
        
        if 'status' not in cat_columns:
            try:
                c.execute("ALTER TABLE categories ADD COLUMN status TEXT DEFAULT 'active'")
                print("✅ Added 'status' column to categories table")
            except:
                pass
        
        if 'created_at' not in cat_columns:
            try:
                c.execute("ALTER TABLE categories ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print("✅ Added 'created_at' column to categories table")
            except:
                pass
    
    # ==================== PRODUCTS TABLE ====================
    if 'products' not in existing_tables:
        c.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            sku TEXT UNIQUE,
            price REAL NOT NULL,
            cost_price REAL DEFAULT 0,
            category_id INTEGER,
            tags TEXT,
            stock INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        print("✅ Created 'products' table")
    else:
        # Check and add columns to existing products table
        c.execute("PRAGMA table_info(products)")
        prod_columns = [row[1] for row in c.fetchall()]
        print(f"Products columns: {prod_columns}")
        
        if 'description' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN description TEXT")
                print("✅ Added 'description' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'description': {e}")
        
        if 'sku' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN sku TEXT")
                print("✅ Added 'sku' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'sku': {e}")
        
        if 'cost_price' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0")
                print("✅ Added 'cost_price' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'cost_price': {e}")
        
        if 'category_id' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN category_id INTEGER")
                print("✅ Added 'category_id' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'category_id': {e}")
        
        if 'tags' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN tags TEXT")
                print("✅ Added 'tags' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'tags': {e}")
        
        if 'stock' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0")
                print("✅ Added 'stock' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'stock': {e}")
        
        if 'status' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN status TEXT DEFAULT 'active'")
                print("✅ Added 'status' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'status': {e}")
        
        if 'image_url' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
                print("✅ Added 'image_url' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'image_url': {e}")
        
        if 'created_at' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print("✅ Added 'created_at' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'created_at': {e}")
        
        if 'updated_at' not in prod_columns:
            try:
                c.execute("ALTER TABLE products ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                print("✅ Added 'updated_at' column to products table")
            except Exception as e:
                print(f"⚠️ Error adding 'updated_at': {e}")
    
    # ==================== REFUNDS TABLE ====================
    if 'refunds' not in existing_tables:
        c.execute('''CREATE TABLE IF NOT EXISTS refunds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            processed_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        print("✅ Created 'refunds' table")
    
    # ==================== ACTIVITY_LOG TABLE ====================
    if 'activity_log' not in existing_tables:
        c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        print("✅ Created 'activity_log' table")
    
    conn.commit()
    conn.close()
    
    print("\n🎉 Migration completed successfully!")
    print("Please restart your Flask application.")

if __name__ == "__main__":
    migrate_database()