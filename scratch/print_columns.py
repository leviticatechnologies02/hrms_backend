import psycopg2

def print_columns():
    conn = psycopg2.connect('postgresql://postgres:1234@localhost:5432/levitica_hr')
    cur = conn.cursor()
    
    for table in ['employees', 'employee_profiles', 'employee_permissions']:
        print(f"\nColumns in '{table}':")
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
    print_columns()
