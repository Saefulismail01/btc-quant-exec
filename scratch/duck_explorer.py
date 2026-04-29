import duckdb

def explore_duck(db_path):
    conn = duckdb.connect(db_path)
    
    print("Listing tables...")
    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    
    for table_row in tables:
        table_name = table_row[0]
        print(f"\n--- Table: {table_name} ---")
        
        count = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        print(f"Total rows: {count}")
        
        cols = conn.execute(f"DESCRIBE {table_name}").fetchall()
        print(f"Columns: {[c[0] for c in cols]}")
        
        if count > 0:
            print("Sample data (first 3 rows):")
            sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
            for row in sample:
                print(row)

if __name__ == "__main__":
    explore_duck('btc-quant.db')
