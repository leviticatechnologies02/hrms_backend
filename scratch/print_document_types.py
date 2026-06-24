import psycopg2

def print_document_types():
    conn = psycopg2.connect('postgresql://postgres:1234@localhost:5432/levitica_hr')
    cur = conn.cursor()
    
    cur.execute("SELECT DISTINCT document_type FROM employee_documents")
    rows = cur.fetchall()
    print("Distinct document types in employee_documents:")
    for row in rows:
        print(f"  - {row[0]}")
        
    cur.execute("SELECT id, employee_id, document_type, document_name, file_path FROM employee_documents")
    docs = cur.fetchall()
    print("\nAll employee documents:")
    for doc in docs:
        print(f"  ID: {doc[0]}, EmpID: {doc[1]}, Type: {doc[2]}, Name: {doc[3]}, Path: {doc[4]}")

if __name__ == '__main__':
    print_document_types()
