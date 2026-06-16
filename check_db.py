import psycopg2
conn = psycopg2.connect('postgresql://postgres:1234@localhost:5432/levitica_hr')
cur = conn.cursor()
cur.execute("SELECT id, employee_id, form_token FROM onboarding_forms WHERE form_token IN ('0a0f7b51-9fbb-46df-b47e-842647deb3cb', '7aca554f-9984-4eab-a7e4-e138607424b6')")
print('Emp IDs for doc tokens:', cur.fetchall())
