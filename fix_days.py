import sqlite3
from datetime import datetime

DATABASE = "orders.db"

with sqlite3.connect(DATABASE) as conn:
    c = conn.cursor()
    
    # Get all orders with missing day
    c.execute("SELECT id, date FROM orders WHERE day IS NULL")
    orders = c.fetchall()
    
    for order_id, date in orders:
        try:
            day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
            c.execute("UPDATE orders SET day = ? WHERE id = ?", (day_name, order_id))
            print(f"✅ Updated order {order_id}: {day_name}")
        except Exception as e:
            print(f"❌ Error updating order {order_id}: {e}")
    
    conn.commit()
    print(f"\n✅ Fixed {len(orders)} orders!")