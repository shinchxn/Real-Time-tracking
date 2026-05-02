import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def setup_supabase():
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url or "your-supabase-connection-string" in db_url:
        print("❌ Error: Please update the DATABASE_URL in your .env file with your Supabase connection string.")
        return

    print(f"🚀 Connecting to Supabase...")
    try:
        # We use a sync engine for the setup script
        engine = create_engine(db_url.replace("postgresql+asyncpg://", "postgresql://"))
        
        sql_path = os.path.join(os.path.dirname(__file__), '..', 'storage', 'migrations', '001_initial.sql')
        
        with open(sql_path, 'r') as f:
            sql_script = f.read()

        # Split by BEGIN/COMMIT or just run as one block if supported
        # Supabase/Postgres handles BEGIN/COMMIT blocks fine via text()
        with engine.connect() as conn:
            print("📜 Executing schema migration...")
            conn.execute(text(sql_script))
            conn.commit()
            
        print("✅ Success! Database tables created on Supabase.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    setup_supabase()
