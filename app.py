from flask import Flask, render_template, request, redirect, url_for, flash, session, g, Response, send_file
import sqlite3
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import os
import shutil
import csv
import io
import re

app = Flask(__name__)
app.secret_key = 'Teenbaan_secret_key_2024'
DATABASE = "orders.db"
BACKUP_DIR = "backups"

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)

# ============================================
# DATABASE HELPER FUNCTIONS
# ============================================

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# Add this line:
get_db_connection = get_db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        g._database = None

def migrate_database():
    """to existing database""" """Add missing columns"""    
    if not os.path.exists(DATABASE):
        return
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Get existing tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in c.fetchall()]
    
    # Add columns to orders table
    if 'orders' in existing_tables:
        c.execute("PRAGMA table_info(orders)")
        order_columns = [row[1] for row in c.fetchall()]
        
        if 'status' not in order_columns:
            try:
                c.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'completed'")
            except:
                pass
    
    # Create categories table
    if 'categories' not in existing_tables:
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    
    # Create refunds table
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
    
    # Create activity_log table
    if 'activity_log' not in existing_tables:
        c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    
    conn.commit()
    conn.close()
    print("Database migration completed!")

def init_db():
    """Initialize the database with required tables"""
    try:
        with app.app_context():
            db = get_db()
            c = db.cursor()
            
            # Create users table
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )''')
            
            # Create orders table
            c.execute('''CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                day TEXT,
                time TEXT NOT NULL,
                orders INTEGER NOT NULL,
                Amount_spend REAL NOT NULL,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create categories table
            c.execute('''CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create refunds table
            c.execute('''CREATE TABLE IF NOT EXISTS refunds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                processed_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create activity_log table
            c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create admin user if not exists
            c.execute("SELECT id FROM users WHERE username = ?", ('admin',))
            if not c.fetchone():
                hashed_pw = generate_password_hash('admin123')
                c.execute('INSERT INTO users (username, email, password, role, status) VALUES (?, ?, ?, ?, ?)',
                          ('admin', 'admin@Teenbaan.com', hashed_pw, 'admin', 'active'))
                print("Admin user created: admin / admin123")
            
            # Create default categories
            c.execute("SELECT COUNT(*) FROM categories")
            if c.fetchone()[0] == 0:
                default_categories = [
                    ('Electronics', 'Electronic devices and accessories'),
                    ('Clothing', 'Apparel and fashion'),
                    ('Food', 'Food and beverages'),
                    ('Home', 'Home and garden'),
                    ('Sports', 'Sports and outdoor')
                ]
                c.executemany('INSERT INTO categories (name, description) VALUES (?, ?)', default_categories)
                print("Default categories created")
            
            db.commit()
            print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")

# ============================================
# AUTH DECORATORS
# ============================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(user_id, action, details):
    """Log user activity"""
    try:
        db = get_db()
        db.execute('INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)',
                  (user_id, action, details))
        db.commit()
    except:
        pass

# ============================================
# AUTH ROUTES
# ============================================

@app.route('/')
def index():
    """Redirect to login or dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter username and password.', 'error')
            return redirect(url_for('login'))
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if not user:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))
        
        if user['status'] == 'inactive':
            flash('Your account has been deactivated. Contact admin.', 'error')
            return redirect(url_for('login'))
        
        if check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            db.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            db.commit()
            
            log_activity(user['id'], 'login', 'User logged in')
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout', 'User logged out')
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        try:
            db = get_db()
            db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                      (username, email, hashed_password))
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
    
    return render_template('register.html')

# ============================================
# DASHBOARD ROUTE
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM orders")
        total_orders = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(Amount_spend) FROM orders")
        total_revenue = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM categories")
        total_categories = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
        completed_orders = c.fetchone()[0] or 0
        
        c.execute("SELECT id, date, day, time, orders, Amount_spend, status FROM orders ORDER BY id DESC LIMIT 10")
        recent_orders = c.fetchall()
        
        # Convert time to 12-hour format
        recent_orders_list = []
        for row in recent_orders:
            row_list = list(row)
            time_str = str(row[3]) if row[3] else "00:00:00"
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S")
                row_list[3] = time_obj.strftime("%I:%M %p")
            except:
                row_list[3] = time_str
            recent_orders_list.append(tuple(row_list))
        
        # Chart data - Daily Revenue
        c.execute("SELECT date, SUM(Amount_spend) FROM orders GROUP BY date ORDER BY date DESC LIMIT 7")
        revenue_data = list(reversed(c.fetchall()))
        
        revenue_labels = [str(row[0]) for row in revenue_data]
        revenue_values = [float(row[1]) if row[1] else 0 for row in revenue_data]
        
        # Chart data - Time-based Revenue
        c.execute("SELECT date FROM orders ORDER BY date DESC LIMIT 1")
        latest_date = c.fetchone()
        
        revenue_time_labels = []
        revenue_time_values = []
        
        if latest_date:
            c.execute("SELECT time, SUM(Amount_spend) FROM orders WHERE date=? GROUP BY time ORDER BY time", (latest_date[0],))
            for t, amt in c.fetchall():
                time_str = str(t) if t else "00:00:00"
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M:%S")
                    revenue_time_labels.append(time_obj.strftime("%I:%M %p"))
                except:
                    revenue_time_labels.append("12:00 AM")
                revenue_time_values.append(float(amt) if amt else 0)
        
        # Order status data
        c.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        order_status_data_list = [[str(row[0]), int(row[1])] for row in c.fetchall()]
    
    return render_template("dashboard.html",
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           total_categories=total_categories,
                           pending_orders=pending_orders,
                           completed_orders=completed_orders,
                           recent_orders=recent_orders_list,
                           revenue_labels=revenue_labels,
                           revenue_values=revenue_values,
                           revenue_time_labels=revenue_time_labels,
                           revenue_time_values=revenue_time_values,
                           order_status_data=order_status_data_list)

# ============================================
# ORDER MANAGEMENT ROUTES
# ============================================

@app.route('/orders')
@login_required
def orders():
    # Get filter parameters
    date_filter = request.args.get('date', '')
    day_filter = request.args.get('day', '')
    time_filter = request.args.get('time', '')
    orders_op = request.args.get('orders_op', '')
    orders_value = request.args.get('orders', '')
    amount_op = request.args.get('amount_op', '')
    amount_value = request.args.get('amount', '')
    status_filter = request.args.get('status', '')
    
    # Build query
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    
    if date_filter:
        query += " AND date = ?"
        params.append(date_filter)
    
    if day_filter:
        query += " AND day = ?"
        params.append(day_filter)
    
    if time_filter:
        # Convert 12-hour time to 24-hour for comparison
        try:
            time_obj = datetime.strptime(time_filter, "%I:%M %p")
            time_24hr = time_obj.strftime("%H:%M:%S")
            query += " AND time = ?"
            params.append(time_24hr)
        except:
            pass
    
    if orders_op and orders_value:
        orders_int = int(orders_value)
        if orders_op == 'eq':
            query += " AND orders = ?"
        elif orders_op == 'gt':
            query += " AND orders > ?"
        elif orders_op == 'lt':
            query += " AND orders < ?"
        elif orders_op == 'gte':
            query += " AND orders >= ?"
        elif orders_op == 'lte':
            query += " AND orders <= ?"
        params.append(orders_int)
    
    if amount_op and amount_value:
        amount_float = float(amount_value)
        if amount_op == 'eq':
            query += " AND Amount_spend = ?"
        elif amount_op == 'gt':
            query += " AND Amount_spend > ?"
        elif amount_op == 'lt':
            query += " AND Amount_spend < ?"
        elif amount_op == 'gte':
            query += " AND Amount_spend >= ?"
        elif amount_op == 'lte':
            query += " AND Amount_spend <= ?"
        params.append(amount_float)
    
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    
    query += " ORDER BY id DESC"
    
    conn = get_db_connection()
    orders_list = conn.execute(query, params).fetchall()
    
    # Get status counts
    status_counts = conn.execute('''SELECT status, COUNT(*) FROM orders GROUP BY status''').fetchall()
    status_counts = {row[0]: row[1] for row in status_counts}
    
    # Calculate total amount
    total_amount = conn.execute("SELECT SUM(Amount_spend) FROM orders").fetchone()[0] or 0
    
    conn.close()
    
    # Format time for display
    orders_list = [list(row) for row in orders_list]
    for row in orders_list:
        time_str = str(row[3]) if row[3] else "00:00:00"
        try:
            time_obj = datetime.strptime(time_str, "%H:%M:%S")
            row[3] = time_obj.strftime("%I:%M %p")
        except:
            pass
    
    return render_template('orders.html', 
                          orders=orders_list,
                          status_filter=status_filter,
                          status_counts=status_counts,
                          total_amount=total_amount,
                          filters={
                              'date': date_filter,
                              'day': day_filter,
                              'time': time_filter,
                              'orders_op': orders_op,
                              'orders': orders_value,
                              'amount_op': amount_op,
                              'amount': amount_value,
                              'status': status_filter
                          },
                          filters_applied=any([date_filter, day_filter, time_filter, 
                                              orders_op, orders_value, amount_op, 
                                              amount_value, status_filter]))

# ============================================
# ORDER MANAGEMENT ROUTES (continued)
# ============================================

@app.route('/orders/view/<int:id>')
@login_required
def order_detail(id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        c.execute("SELECT * FROM orders WHERE id=?", (id,))
        order = c.fetchone()
        
        if order:
            order = dict(order)
            time_str = str(order['time']) if order['time'] else "00:00:00"
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S")
                order['time'] = time_obj.strftime("%I:%M %p")
            except:
                pass
        
        # Get refund history
        c.execute("SELECT * FROM refunds WHERE order_id=? ORDER BY created_at DESC", (id,))
        refunds = c.fetchall()
    
    return render_template("order_detail.html", order=order, refunds=refunds)

@app.route('/orders/update/<int:id>', methods=['POST'])
@login_required
def update_order_status(id):
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("UPDATE orders SET status=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (new_status, notes, id))
        conn.commit()
    
    log_activity(session['user_id'], 'update_order', f'Updated order #{id} to {new_status}')
    flash(f'Order #{id} status updated to {new_status}!', 'success')
    return redirect(url_for('order_detail', id=id))

@app.route('/orders/refund/<int:id>', methods=['POST'])
@admin_required
def process_refund(id):
    amount = request.form.get('amount')
    reason = request.form.get('reason', '')
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        # Get order details
        c.execute("SELECT Amount_spend FROM orders WHERE id=?", (id,))
        order = c.fetchone()
        
        if order:
            max_refund = float(order[0])
            refund_amount = min(float(amount), max_refund)
            
            # Add refund record
            c.execute("INSERT INTO refunds (order_id, amount, reason, processed_by, status) VALUES (?, ?, ?, ?, 'completed')",
                      (id, refund_amount, reason, session['user_id']))
            
            # Update order status
                        # Update order status
            c.execute("UPDATE orders SET status='refunded', updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
            
            conn.commit()
            
            log_activity(session['user_id'], 'refund', f'Refunded Rs{refund_amount} for order #{id}')
            flash(f'Refund of Rs{refund_amount} processed successfully!', 'success')
    
    return redirect(url_for('order_detail', id=id))

@app.route('/orders/cancel/<int:id>')
@login_required
def cancel_order(id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("UPDATE orders SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
        conn.commit()
    
    log_activity(session['user_id'], 'cancel_order', f'Cancelled order #{id}')
    flash(f'Order #{id} has been cancelled!', 'success')
    return redirect(url_for('orders'))

@app.route('/orders/export')
@admin_required
def export_orders():
    status_filter = request.args.get('status', '')
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        query = "SELECT id, date, day, time, orders, Amount_spend, status FROM orders"
        params = []
        
        if status_filter:
            query += " WHERE status=?"
            params.append(status_filter)
        
        query += " ORDER BY id DESC"
        
        c.execute(query, params)
        orders = c.fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Date', 'Day', 'Time', 'Orders', 'Amount', 'Status'])
    
    # Write data
    for row in orders:
        time_str = str(row[3]) if row[3] else ""
        try:
            time_obj = datetime.strptime(time_str, "%H:%M:%S")
            time_str = time_obj.strftime("%I:%M %p")
        except:
            pass
        
        writer.writerow([row[0], row[1], row[2], time_str, row[4], row[5], row[6]])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=orders_export.csv'})

# ============================================
# ADD ORDER ROUTE
# ============================================

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        date = request.form['date']
        hour = int(request.form['hour'])
        minute = int(request.form['minute'])
        ampm = request.form['ampm']
        orders_count = int(request.form['orders'])
        amount = float(request.form['amount'])
        
        if ampm == 'PM' and hour != 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0
        
        time_str = f"{hour:02d}:{minute:02d}:00"
        day_name = get_day_name(date)
        
        conn = get_db()
        conn.execute('''INSERT INTO orders (date, day, time, orders, Amount_spend) 
                       VALUES (?, ?, ?, ?, ?)''', 
                    (date, day_name, time_str, orders_count, amount))
        conn.commit()
        conn.close()
        
        flash('Order added successfully!', 'success')
        return redirect(url_for('orders'))
    
    return render_template('form.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (id,)).fetchone()
    conn.close()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('orders'))
    
    if request.method == 'POST':
        orders_count = int(request.form['orders'])
        amount = float(request.form['amount'])
        
        conn = get_db()
        conn.execute("UPDATE orders SET orders=?, Amount_spend=? WHERE id=?", 
                    (orders_count, amount, id))
        conn.commit()
        conn.close()
        
        flash('Order updated successfully!', 'success')
        return redirect(url_for('orders'))
    
    order = list(order)
    order[3] = format_time_12hr(order[3])
    
    return render_template('edit.html', data=order)

@app.route('/order/<int:id>')
@login_required
def view(id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (id,)).fetchone()
    conn.close()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('orders'))
    
    order = list(order)
    order[3] = format_time_12hr(order[3])
    
    return render_template('order_detail.html', order=order)

@app.route('/order/<int:id>/cancel')
@login_required
def cancel(id):
    conn = get_db()
    conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    
    flash('Order cancelled!', 'warning')
    return redirect(url_for('orders'))

@app.route('/order/<int:id>/delete')
@login_required
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM orders WHERE id=?", (id,))
    conn.commit()
    conn.close()
    
    flash('Order deleted!', 'error')
    return redirect(url_for('orders'))

# ============================================
# DELETE ORDER ROUTE
# ============================================

@app.route('/delete/<int:id>')
@login_required
def delete_order(id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM orders WHERE id=?", (id,))
        conn.commit()
    
    log_activity(session['user_id'], 'delete_order', f'Deleted order #{id}')
    flash('Order deleted successfully!', 'success')
    return redirect(url_for('orders'))

# ============================================
# CATEGORY MANAGEMENT ROUTES
# ============================================

@app.route('/categories')
@login_required
def categories():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        c.execute("SELECT * FROM categories ORDER BY name")
        categories_list = c.fetchall()
        
        categories_data = []
        for cat in categories_list:
            cat_list = list(cat)
            while len(cat_list) < 5:
                cat_list.append(None)
            categories_data.append(cat_list)
    
    return render_template("categories.html", categories=categories_data)

@app.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO categories (name, description) VALUES (?, ?)",
                         (name, description))
                conn.commit()
                
                log_activity(session['user_id'], 'add_category', f'Added category: {name}')
                flash(f'Category "{name}" added successfully!', 'success')
                return redirect(url_for('categories'))
            except sqlite3.IntegrityError:
                flash('Category name already exists!', 'error')
    
    return render_template("category_form.html", category=None, action='Add')

@app.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description', '')
            status = request.form.get('status', 'active')
            
            try:
                c.execute("UPDATE categories SET name=?, description=?, status=? WHERE id=?",
                         (name, description, status, id))
                conn.commit()
                
                log_activity(session['user_id'], 'edit_category', f'Updated category: {name}')
                flash(f'Category "{name}" updated successfully!', 'success')
                return redirect(url_for('categories'))
            except sqlite3.IntegrityError:
                flash('Category name already exists!', 'error')
        
        c.execute("SELECT * FROM categories WHERE id=?", (id,))
        category = c.fetchone()
    
    return render_template("category_form.html", category=category, action='Edit')

@app.route('/categories/delete/<int:id>')
@admin_required
def delete_category(id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        c.execute("SELECT name FROM categories WHERE id=?", (id,))
        category = c.fetchone()
        
        c.execute("DELETE FROM categories WHERE id=?", (id,))
        conn.commit()
    
    log_activity(session['user_id'], 'delete_category', f'Deleted category: {category[0]}')
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('categories'))

@app.route('/categories/toggle/<int:id>')
@login_required
def toggle_category_status(id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT name, status FROM categories WHERE id=?", (id,))
        category = c.fetchone()
        
        new_status = 'inactive' if category[1] == 'active' else 'active'
        c.execute("UPDATE categories SET status=? WHERE id=?", (new_status, id))
        conn.commit()
    
    log_activity(session['user_id'], 'toggle_category', f'Changed {category[0]} to {new_status}')
    flash(f'Category status changed to {new_status}!', 'success')
    return redirect(url_for('categories'))

# ============================================
# IMPORT/EXPORT ROUTES
# ============================================

@app.route('/import', methods=['GET', 'POST'])
@admin_required
def import_data():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file uploaded!', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            
            if file.filename == '':
                flash('No file selected!', 'error')
                return redirect(request.url)
            
            table_name = request.form.get('table_name', '').strip()
            
            if not table_name:
                table_name = re.sub(r'[^a-zA-Z0-9]', '_', file.filename.split('.')[0].lower())
            
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
                flash('Invalid table name!', 'error')
                return redirect(request.url)
            
            decoded_file = file.read().decode('utf-8')
            csv_reader = csv.reader(decoded_file.splitlines())
            
            headers = next(csv_reader)
            
            if not headers:
                flash('File is empty!', 'error')
                return redirect(request.url)
            
            clean_headers = []
            for h in headers:
                col_name = h.strip().lower().replace(' ', '_')
                col_name = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
                if not col_name:
                    col_name = 'col_' + str(len(clean_headers))
                clean_headers.append(col_name)
            
            rows = list(csv_reader)
            
            if not rows:
                flash('No data in file!', 'error')
                return redirect(request.url)
            
            with sqlite3.connect(DATABASE) as conn:
                c = conn.cursor()
                
                columns_def = ['"' + col + '" TEXT' for col in clean_headers]
                create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(columns_def)})"
                c.execute(create_sql)
                
                for row in rows:
                    values = [val.strip() if val else '' for val in row[:len(clean_headers)]]
                    placeholders = ', '.join(['?' for _ in range(len(values))])
                    insert_sql = f"INSERT INTO {table_name} ({', '.join(['"' + col + '"' for col in clean_headers])}) VALUES ({placeholders})"
                    c.execute(insert_sql, values)
                
                conn.commit()
                
                flash(f'Successfully imported {len(rows)} rows into table "{table_name}"!', 'success')
                return redirect(url_for('view_table', table_name=table_name))
        
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return redirect(request.url)
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [row[0] for row in c.fetchall()]
    
    return render_template("import.html", tables=tables)

@app.route('/table/<table_name>')
@admin_required
def view_table(table_name):
    try:
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            
            c.execute(f"PRAGMA table_info({table_name})")
            columns = c.fetchall()
            
            c.execute(f"SELECT * FROM {table_name} LIMIT 100")
            rows = c.fetchall()
            
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_count = c.fetchone()[0]
        
        return render_template("view_table.html", 
                              table_name=table_name, 
                              columns=columns, 
                              rows=rows,
                              total_count=total_count)
    
    except Exception as e:
        flash(f'Error viewing table: {str(e)}', 'error')
        return redirect(url_for('import_data'))

@app.route('/table/<table_name>/delete', methods=['POST'])
@admin_required
def delete_table(table_name):
    try:
        protected_tables = ['users', 'orders', 'categories', 'refunds', 'activity_log']
        if table_name.lower() in protected_tables:
            flash(f'Cannot delete protected table "{table_name}"!', 'error')
            return redirect(url_for('import_data'))
        
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            
            log_activity(session['user_id'], 'delete_table', f'Deleted table "{table_name}"')
            flash(f'Table "{table_name}" deleted successfully!', 'success')
    
    except Exception as e:
        flash(f'Error deleting table: {str(e)}', 'error')
    
    return redirect(url_for('import_data'))

@app.route('/table/<table_name>/export')
@admin_required
def export_table_csv(table_name):
    try:
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute(f"SELECT * FROM {table_name}")
            rows = c.fetchall()
            c.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in c.fetchall()]
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        
        for row in rows:
            writer.writerow(row)
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment;filename={table_name}_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
    
    except Exception as e:
        flash(f'Error exporting table: {str(e)}', 'error')
        return redirect(url_for('import_data'))

# ============================================
# UPLOAD CSV ROUTE
# ============================================

@app.route('/upload-csv', methods=['GET', 'POST'])
@admin_required
def upload_csv():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file uploaded!', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            
            if file.filename == '':
                flash('No file selected!', 'error')
                return redirect(request.url)
            
            if not file.filename.endswith('.csv'):
                flash('Only CSV files are allowed!', 'error')
                return redirect(request.url)
            
            table_name = request.form.get('table_name', '').strip()
            
            if not table_name:
                table_name = file.filename.split('.')[0].lower()
                table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name)
            
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
                flash('Invalid table name!', 'error')
                return redirect(request.url)
            
            decoded_file = file.read().decode('utf-8')
            csv_reader = csv.reader(decoded_file.splitlines())
            
            headers = next(csv_reader)
            
            if not headers:
                flash('CSV file is empty!', 'error')
                return redirect(request.url)
            
            clean_headers = []
            for h in headers:
                col_name = h.strip().lower().replace(' ', '_')
                col_name = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
                if not col_name:
                    col_name = 'col_' + str(len(clean_headers))
                clean_headers.append(col_name)
            
            rows = list(csv_reader)
            
            if not rows:
                flash('CSV file has no data!', 'error')
                return redirect(request.url)
            
            with sqlite3.connect(DATABASE) as conn:
                c = conn.cursor()
                
                columns_def = [f'"{col}" TEXT' for col in clean_headers]
                create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(columns_def)})"
                c.execute(create_sql)
                
                for row in rows:
                    values = [val.strip() if val else '' for val in row[:len(clean_headers)]]
                    placeholders = ', '.join(['?' for _ in values])
                    insert_sql = f"INSERT INTO {table_name} ({', '.join(['"' + col + '"' for col in clean_headers])}) VALUES ({placeholders})"
                    c.execute(insert_sql, values)
                
                conn.commit()
                
                flash(f'Successfully created table "{table_name}" with {len(rows)} rows!', 'success')
                return redirect(url_for('view_table', table_name=table_name))
        
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            import traceback
            traceback.print_exc()
            return redirect(request.url)
    
    return render_template("upload_csv.html")

# ============================================
# COMPARE ROUTE
# ============================================

# ============================================
# COMPARE ROUTE
# ============================================

@app.route('/compare', methods=['GET'])
@login_required
def compare():
    dates_str = request.args.get('dates', '')
    
    # Always ensure selected_dates is a list
    if dates_str:
        selected_dates = [d.strip() for d in dates_str.split(',') if d.strip()]
    else:
        selected_dates = []
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        c.execute("SELECT DISTINCT date FROM orders ORDER BY date")
        available_dates = [row[0] for row in c.fetchall()]
        
        all_data = []
        
        for d in selected_dates:
            c.execute("SELECT id, date, day, time, orders, Amount_spend, status FROM orders WHERE date=?", (d,))
            data = c.fetchall()
            
            if not data:
                continue
            
            c.execute("SELECT SUM(orders) FROM orders WHERE date=?", (d,))
            total_orders = c.fetchone()[0] or 0
            
            c.execute("SELECT SUM(Amount_spend) FROM orders WHERE date=?", (d,))
            total_revenue = c.fetchone()[0] or 0
            
            c.execute("SELECT time, SUM(Amount_spend) FROM orders WHERE date=? GROUP BY time ORDER BY time", (d,))
            time_data = c.fetchall()
            
            time_labels = []
            time_values = []
            
            for t, amt in time_data:
                time_str = str(t) if t else "00:00:00"
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M:%S")
                    time_12hr = time_obj.strftime("%I:%M %p")
                except:
                    time_12hr = "12:00 AM"
                
                time_labels.append(time_12hr)
                time_values.append(float(amt) if amt else 0)
            
            # Also get order counts per time
                        # Also get order counts per time
            c.execute("SELECT time, SUM(orders) FROM orders WHERE date=? GROUP BY time ORDER BY time", (d,))
            orders_per_time = c.fetchall()
            
            orders_time_values = []
            for t, o in orders_per_time:
                orders_time_values.append(int(o) if o else 0)
            
            data_12hr = []
            for row in data:
                row_list = list(row)
                time_str = str(row[3]) if row[3] else "00:00:00"
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M:%S")
                    row_list[3] = time_obj.strftime("%I:%M %p")
                except:
                    pass
                row_list[4] = int(row[4]) if row[4] else 0
                row_list[5] = float(row[5]) if row[5] else 0.0
                data_12hr.append(tuple(row_list))
            
            all_data.append({
                'date': d,
                'data': data_12hr,
                'total_orders': int(total_orders) if total_orders else 0,
                'total_revenue': float(total_revenue) if total_revenue else 0,
                'time_labels': time_labels,
                'time_values': time_values,
                'orders_values': orders_time_values
            })
    
    return render_template("dashboard_compare.html",
                           all_data=all_data,
                           selected_dates=selected_dates,
                           available_dates=available_dates)
# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    message = ""
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM orders")
        orders_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM activity_log")
        activity_count = c.fetchone()[0]
        
        c.execute("SELECT id, username, role FROM users ORDER BY id")
        users = c.fetchall()
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall() if row[0] != 'sqlite_sequence']
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == "truncate_orders":
                c.execute("DELETE FROM orders")
                message = "All orders deleted successfully."
                log_activity(session['user_id'], 'db_action', 'Deleted all orders')
                orders_count = 0
            
            elif action == "reset_id_orders":
                c.execute("DELETE FROM sqlite_sequence WHERE name='orders'")
                message = "Orders auto increment reset successfully."
            
            elif action == "add_column":
                column_name = request.form.get('column_name')
                column_type = request.form.get('column_type')
                table_name = request.form.get('table_name')
                try:
                    c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    message = f"Column '{column_name}' added to {table_name}."
                    log_activity(session['user_id'], 'db_action', f'Added column: {column_name} to {table_name}')
                except Exception as e:
                    message = f"Error: {e}"
            
            elif action == "create_table":
                table_name = request.form.get('table_name')
                columns = request.form.get('columns', '')
                try:
                    c.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})")
                    message = f"Table '{table_name}' created successfully."
                    log_activity(session['user_id'], 'db_action', f'Created table: {table_name}')
                    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in c.fetchall() if row[0] != 'sqlite_sequence']
                except Exception as e:
                    message = f"Error: {e}"
            
            elif action == "drop_table":
                table_name = request.form.get('table_name')
                try:
                    c.execute(f"DROP TABLE IF EXISTS {table_name}")
                    message = f"Table '{table_name}' dropped successfully."
                    log_activity(session['user_id'], 'db_action', f'Dropped table: {table_name}')
                    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in c.fetchall() if row[0] != 'sqlite_sequence']
                except Exception as e:
                    message = f"Error: {e}"
            
            elif action == "custom_sql":
                sql = request.form.get('custom_sql')
                sql_upper = sql.upper().strip()
                if sql_upper.startswith('SELECT') or sql_upper.startswith('INSERT') or \
                   sql_upper.startswith('UPDATE') or sql_upper.startswith('DELETE'):
                    try:
                        c.execute(sql)
                        message = "SQL executed successfully."
                        log_activity(session['user_id'], 'custom_sql', f'Executed: {sql[:50]}...')
                    except Exception as e:
                        message = f"Error: {e}"
                else:
                    message = "Error: Only SELECT, INSERT, UPDATE, DELETE allowed!"
            
            conn.commit()
    
    return render_template("admin.html", 
                          message=message,
                          orders_count=orders_count,
                          users_count=users_count,
                          activity_count=activity_count,
                          users=users,
                          tables=tables)

# ============================================
# DATABASE MANAGEMENT ROUTES
# ============================================

@app.route('/admin/create-database', methods=['POST'])
@admin_required
def create_database():
    try:
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()
            g._database = None
        
        if os.path.exists(DATABASE):
            try:
                os.remove(DATABASE)
            except PermissionError:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                old_path = f"{DATABASE}_old_{timestamp}"
                os.rename(DATABASE, old_path)
        
        init_db()
        
        log_activity(session['user_id'], 'create_db', 'Created new database')
        flash('New database created successfully!', 'success')
        
    except Exception as e:
        flash(f'Error creating database: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/backup-database', methods=['POST'])
@admin_required
def backup_database():
    try:
        if not os.path.exists(DATABASE):
            flash('No database found to backup!', 'error')
            return redirect(url_for('admin'))
        
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()
            g._database = None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f'orders_backup_{timestamp}.db')
        
        shutil.copy2(DATABASE, backup_path)
        
        log_activity(session['user_id'], 'backup_db', f'Created backup: {backup_path}')
        flash(f'Database backed up successfully to: {backup_path}', 'success')
        
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/backups')
@admin_required
def list_backups():
    backups = []
    if os.path.exists(BACKUP_DIR):
        for f in os.listdir(BACKUP_DIR):
            if f.endswith('.db'):
                filepath = os.path.join(BACKUP_DIR, f)
                size = os.path.getsize(filepath)
                modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                backups.append({
                    'name': f,
                    'size': f'{size/1024:.1f} KB',
                    'modified': modified.strftime('%Y-%m-%d %H:%M:%S')
                })
    
    backups.sort(key=lambda x: x['modified'], reverse=True)
    return render_template('backups.html', backups=backups)

@app.route('/download/backup/<path:filename>')
@admin_required
def download_backup(filename):
    backup_path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(backup_path):
        return send_file(backup_path, as_attachment=True)
    flash('Backup file not found!', 'error')
    return redirect(url_for('list_backups'))

@app.route('/delete/backup/<path:filename>')
@admin_required
def delete_backup(filename):
    backup_path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(backup_path):
        os.remove(backup_path)
        flash(f'Backup {filename} deleted!', 'success')
    return redirect(url_for('list_backups'))

@app.route('/restore/backup/<path:filename>')
@admin_required
def restore_backup(filename):
    try:
        backup_path = os.path.join(BACKUP_DIR, filename)
        
        if not os.path.exists(backup_path):
            flash('Backup file not found!', 'error')
            return redirect(url_for('list_backups'))
        
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()
            g._database = None
        
        if os.path.exists(DATABASE):
            os.remove(DATABASE)
        
        shutil.copy2(backup_path, DATABASE)
        
        log_activity(session['user_id'], 'restore_backup', f'Restored from: {filename}')
        flash(f'Database restored from {filename} successfully!', 'success')
        
    except Exception as e:
        flash(f'Error restoring backup: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

# ============================================
# PDF EXPORT ROUTES
# ============================================

@app.route('/export/dashboard/pdf')
@login_required
def export_dashboard_pdf():
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT COUNT(*) FROM orders")
        total_orders = int(c.fetchone()[0] or 0)
        
        c.execute("SELECT SUM(Amount_spend) FROM orders")
        total_revenue = float(c.fetchone()[0] or 0)
        
        c.execute("SELECT SUM(orders) FROM orders")
        total_items = int(c.fetchone()[0] or 0)
        
        avg_order = total_revenue / total_orders if total_orders > 0 else 0
        
        c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20")
        recent_orders = []
        for row in c.fetchall():
            time_str = str(row[3]) if row[3] else "00:00:00"
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S")
                time_12hr = time_obj.strftime("%I:%M %p")
            except:
                time_12hr = "12:00 AM"
            
            recent_orders.append({
                'id': int(row[0]) if row[0] else 0,
                'date': str(row[1]) if row[1] else '',
                'day': str(row[2]) if row[2] else '',
                'time': time_12hr,
                'orders': int(row[4]) if row[4] else 0,
                'Amount_spend': float(row[5]) if row[5] else 0,
                'status': str(row[6]) if row[6] else 'completed'
            })
        
        c.execute("SELECT date, SUM(orders), SUM(Amount_spend) FROM orders GROUP BY date ORDER BY date DESC LIMIT 10")
        chart_data = []
        for row in c.fetchall():
            chart_data.append({
                'date': str(row[0]) if row[0] else '',
                'orders': int(row[1]) if row[1] else 0,
                'revenue': float(row[2]) if row[2] else 0
            })
        
        html_content = render_template('pdf_dashboard.html',
                                       total_orders=total_orders,
                                       total_revenue=total_revenue,
                                       total_items=total_items,
                                       avg_order=avg_order,
                                       recent_orders=recent_orders,
                                       chart_data=chart_data,
                                       generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                       username=session['username'])
        
        return Response(
            html_content,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'attachment; filename=dashboard_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            }
        )
    
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/export/orders/pdf')
@admin_required
def export_orders_pdf():
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT id, date, day, time, orders, Amount_spend, status FROM orders ORDER BY date DESC, time DESC")
        orders = []
        for row in c.fetchall():
            time_str = str(row[3]) if row[3] else "00:00:00"
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S")
                time_12hr = time_obj.strftime("%I:%M %p")
            except:
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M")
                    time_12hr = time_obj.strftime("%I:%M %p")
                except:
                    time_12hr = time_str
            
            orders.append({
                'id': int(row[0]) if row[0] else 0,
                'date': str(row[1]) if row[1] else '',
                'day': str(row[2]) if row[2] else '',
                'time': time_12hr,
                'orders': int(row[4]) if row[4] else 0,
                'Amount_spend': float(row[5]) if row[5] else 0,
                'status': str(row[6]) if row[6] else 'completed'
            })
        
        html_content = render_template('pdf_orders.html',
                                       orders=orders,
                                       generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                       username=session['username'])
        
        return Response(
            html_content,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'attachment; filename=all_orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            }
        )
    
    except Exception as e:
        flash(f'Error generating orders PDF: {str(e)}', 'error')
        return redirect(url_for('orders'))

@app.route('/export/comparison/pdf')
@login_required
def export_comparison_pdf():
    try:
        dates_str = request.args.get('dates', '')
        
        if dates_str:
            dates = [d.strip() for d in dates_str.split(',') if d.strip()]
        else:
            dates = []
        
        if not dates:
            flash('No dates selected for comparison!', 'error')
            return redirect(url_for('compare'))
        
        db = get_db()
        c = db.cursor()
        
        all_data = []
        
        for d in dates:
            c.execute("SELECT id, date, day, time, orders, Amount_spend, status FROM orders WHERE date=?", (d,))
            orders = c.fetchall()
            
            if not orders:
                continue
            
            orders_list = []
            time_labels = []
            time_values = []
            
            for row in orders:
                time_raw = row[3]
                
                if time_raw:
                    time_str = str(time_raw)
                    try:
                        time_obj = datetime.strptime(time_str, "%H:%M:%S")
                        time_display = time_obj.strftime("%I:%M %p")
                    except:
                        try:
                            time_obj = datetime.strptime(time_str, "%H:%M")
                            time_display = time_obj.strftime("%I:%M %p")
                        except:
                            time_display = time_str
                else:
                    time_display = "12:00 AM"
                
                orders_list.append({
                    'id': int(row[0]) if row[0] else 0,
                    'date': str(row[1]) if row[1] else '',
                    'day': str(row[2]) if row[2] else '',
                    'time': time_display,
                    'orders': int(row[4]) if row[4] else 0,
                    'Amount_spend': float(row[5]) if row[5] else 0,
                    'status': str(row[6]) if row[6] else 'completed'
                })
                
                time_labels.append(time_display)
                time_values.append(float(row[5]) if row[5] else 0)
            
            c.execute("SELECT SUM(orders), SUM(Amount_spend) FROM orders WHERE date=?", (d,))
            totals = c.fetchone()
            
            all_data.append({
                'date': d,
                'total_orders': int(totals[0]) if totals[0] else 0,
                'total_revenue': float(totals[1]) if totals[1] else 0,
                'order_count': len(orders),
                'orders': orders_list,
                'time_labels': time_labels,
                'time_values': time_values
            })
        
        if not all_data:
            flash('No data found for selected dates!', 'error')
            return redirect(url_for('compare'))
        
        html_content = render_template('pdf_comparison.html',
                                       all_data=all_data,
                                       generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                       username=session['username'])
        
        return Response(
            html_content,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'attachment; filename=comparison_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            }
        )
    
    except Exception as e:
        flash(f'Error generating comparison PDF: {str(e)}', 'error')
        return redirect(url_for('compare'))

# ============================================
# USER MANAGEMENT ROUTES
# ============================================

@app.route('/users')
@admin_required
def users():
    db = get_db()
    all_users = db.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
    
    users_list = []
    for user in all_users:
        user_dict = dict(user)
        user_dict.setdefault('email', None)
        user_dict.setdefault('role', 'user')
        user_dict.setdefault('status', 'active')
        user_dict.setdefault('created_at', None)
        user_dict.setdefault('last_login', None)
        users_list.append(user_dict)
    
    return render_template('users.html', users=users_list)

@app.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        hashed_password = generate_password_hash(password)
        
        try:
            db = get_db()
            db.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                      (username, email, hashed_password, role))
            db.commit()
            
            log_activity(session['user_id'], 'add_user', f'Created user: {username}')
            flash(f'User "{username}" created successfully!', 'success')
            return redirect(url_for('users'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')
    
    return render_template('add_user.html')

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_user(id):
    db = get_db()
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        status = request.form.get('status')
        
        if id == session['user_id'] and role != 'admin':
            flash('Cannot change your own admin role!', 'error')
            return redirect(url_for('edit_user', id=id))
        
        password = request.form.get('password')
        
        if password:
            hashed_password = generate_password_hash(password)
            db.execute('''UPDATE users SET username=?, email=?, password=?, role=?, status=? 
                        WHERE id=?''', (username, email, hashed_password, role, status, id))
        else:
            db.execute('''UPDATE users SET username=?, email=?, role=?, status=? 
                        WHERE id=?''', (username, email, role, status, id))
        
        db.commit()
        
        log_activity(session['user_id'], 'edit_user', f'Updated user: {username}')
        flash(f'User "{username}" updated successfully!', 'success')
        return redirect(url_for('users'))
    
    user = db.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
    user_dict = dict(user)
    
    return render_template('edit_user.html', user=user_dict)

@app.route('/users/delete/<int:id>')
@admin_required
def delete_user(id):
    if id == session['user_id']:
        flash('Cannot delete your own account!', 'error')
        return redirect(url_for('users'))
    
    db = get_db()
    user = db.execute('SELECT username FROM users WHERE id = ?', (id,)).fetchone()
    
    db.execute('DELETE FROM users WHERE id = ?', (id,))
    db.commit()
    
    log_activity(session['user_id'], 'delete_user', f'Deleted user: {user["username"]}')
    flash(f'User "{user["username"]}" deleted successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/users/toggle/<int:id>')
@admin_required
def toggle_user_status(id):
    if id == session['user_id']:
        flash('Cannot toggle your own status!', 'error')
        return redirect(url_for('users'))
    
    db = get_db()
    user = db.execute('SELECT username, status FROM users WHERE id = ?', (id,)).fetchone()
    
    new_status = 'active' if user['status'] == 'inactive' else 'inactive'
    db.execute('UPDATE users SET status = ? WHERE id = ?', (new_status, id))
    db.commit()
    
    log_activity(session['user_id'], 'toggle_status', f'Changed {user["username"]} to {new_status}')
    flash(f'User "{user["username"]}" is now {new_status}!', 'success')
    return redirect(url_for('users'))

# ============================================
# PROFILE ROUTE
# ============================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_dict = dict(user)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            username = request.form.get('username')
            email = request.form.get('email')
            
            existing = db.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                                (username, session['user_id'])).fetchone()
            if existing:
                flash('Username already exists!', 'error')
                return redirect(url_for('profile'))
            
            db.execute('UPDATE users SET username = ?, email = ? WHERE id = ?',
                      (username, email, session['user_id']))
            db.commit()
            
            session['username'] = username
            log_activity(session['user_id'], 'update_profile', 'Updated profile')
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        
        elif action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not check_password_hash(user['password'], current_password):
                flash('Current password is incorrect!', 'error')
                return redirect(url_for('profile'))
            
            if new_password != confirm_password:
                flash('New passwords do not match!', 'error')
                return redirect(url_for('profile'))
            
            hashed_password = generate_password_hash(new_password)
            db.execute('UPDATE users SET password = ? WHERE id = ?', 
                      (hashed_password, session['user_id']))
            db.commit()
            
            log_activity(session['user_id'], 'change_password', 'Changed password')
            flash('Password changed successfully!', 'success')
            return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user_dict)

# ============================================
# ACTIVITY LOG ROUTES
# ============================================

@app.route('/activity')
@admin_required
def activity():
    db = get_db()
    activities = db.execute('''
        SELECT al.*, u.username 
        FROM activity_log al 
        LEFT JOIN users u ON al.user_id = u.id 
        ORDER BY al.timestamp DESC LIMIT 100
    ''').fetchall()
    return render_template('activity.html', activities=activities)

@app.route('/activity/clear')
@admin_required
def clear_activity():
    db = get_db()
    db.execute('DELETE FROM activity_log')
    db.commit()
    
    log_activity(session['user_id'], 'clear_activity', 'Cleared all activity logs')
    flash('Activity log cleared successfully!', 'success')
    return redirect(url_for('activity'))

# ============================================
# SETTINGS ROUTE
# ============================================

@app.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'backup_db':
            try:
                if os.path.exists(DATABASE):
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_path = os.path.join(BACKUP_DIR, f'orders_backup_{timestamp}.db')
                    shutil.copy2(DATABASE, backup_path)
                    message = f"Database backup created: {backup_path}"
                    log_activity(session['user_id'], 'backup_db', f'Created backup: {backup_path}')
            except Exception as e:
                message = f"Backup failed: {e}"
        
        elif action == 'clear_logs':
            db = get_db()
            db.execute("DELETE FROM activity_log")
            db.commit()
            message = "Activity logs cleared!"
            log_activity(session['user_id'], 'clear_logs', 'Cleared activity logs')
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM orders")
    orders_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM categories")
    categories_count = c.fetchone()[0]
    
    return render_template("settings.html", message=message, 
                          orders_count=orders_count, 
                          users_count=users_count,
                          categories_count=categories_count)

# ============================================
# API ROUTES
# ============================================

@app.route('/api/health')
def api_health():
    return {
        'status': 'healthy',
        'message': 'Teenbaan API is running',
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat()
    }

@app.route('/api/stats')
@login_required
def api_stats():
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT COUNT(*) FROM orders")
        total_orders = int(c.fetchone()[0] or 0)
        
        c.execute("SELECT SUM(Amount_spend) FROM orders")
        total_revenue = float(c.fetchone()[0] or 0)
        
        c.execute("SELECT SUM(orders) FROM orders")
        total_items = int(c.fetchone()[0] or 0)
        
        avg_order = total_revenue / total_orders if total_orders > 0 else 0
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = int(c.fetchone()[0] or 0)
        
        c.execute("SELECT COUNT(*) FROM categories")
        total_categories = int(c.fetchone()[0] or 0)
        
        return {
            'status': 'success',
            'data': {
                'orders': {
                    'total': total_orders,
                    'total_items': total_items,
                    'total_revenue': round(total_revenue, 2),
                    'average_order': round(avg_order, 2)
                },
                'categories': {
                    'total': total_categories
                },
                'users': {
                    'total': total_users
                },
                'generated_at': datetime.now().isoformat()
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500

@app.route('/api/orders')
@login_required
def api_orders():
    try:
        db = get_db()
        c = db.cursor()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)
        offset = (page - 1) * limit
        
        c.execute("SELECT COUNT(*) FROM orders")
        total = c.fetchone()[0]
        
        c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        orders = []
        for row in c.fetchall():
            time_str = str(row[3]) if row[3] else "00:00:00"
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S")
                time_12hr = time_obj.strftime("%I:%M %p")
            except:
                time_12hr = "12:00 AM"
            
            orders.append({
                'id': int(row[0]) if row[0] else 0,
                'date': str(row[1]) if row[1] else '',
                'day': str(row[2]) if row[2] else '',
                'time': time_12hr,
                'orders': int(row[4]) if row[4] else 0,
                'Amount_spend': float(row[5]) if row[5] else 0,
                'status': str(row[6]) if row[6] else 'completed'
            })
        
        return {
            'status': 'success',
            'data': {
                'orders': orders,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': int(total),
                    'pages': (total + limit - 1) // limit
                }
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500

# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    print("=" * 50)
    print("Teenbaan Order Management System v2.0")
    print("=" * 50)
    
    # Run migration
    migrate_database()
    
    # Initialize database
    init_db()
    
    print("\nStarting Flask server...")
    app.run(debug=True)