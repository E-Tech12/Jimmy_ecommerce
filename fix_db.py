import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

database_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if not database_url:
    print("No database URL found.")
    exit(1)

engine = create_engine(database_url)

with engine.connect() as conn:
    try:
        print("Adding 'url' column to 'product_image' table...")
        conn.execute(text("ALTER TABLE product_image ADD COLUMN IF NOT EXISTS url VARCHAR(255)"))
        conn.commit()
        print("Column added successfully!")
    except Exception as e:
        print(f"Error: {e}")
# ok
