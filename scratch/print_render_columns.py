import psycopg2

def print_render_columns():
    db_url = 'postgresql://levitica_hr_38nm_user:yUu6E00p44mOikLwZrt3k4uUoZ58Lq6U@dpg-cpi5u4aj1k6c738tldp0-a.singapore-postgres.render.com/levitica_hr_38nm?sslmode=require'
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    for table in ['employees', 'employee_profiles', 'employee_permissions']:
        print(f"\nColumns in Render table '{table}':")
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        for col in cols:
            print(f"  {col[0]} ({col[1]})")

if __name__ == '__main__':
    print_render_columns()
