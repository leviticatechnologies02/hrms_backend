import psycopg2

def list_tables():
    conn = psycopg2.connect('postgresql://postgres:1234@localhost:5432/levitica_hr')
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    print("Tables in database:")
    for t in tables:
        print(f"  - {t[0]}")

if __name__ == '__main__':
    list_tables()
