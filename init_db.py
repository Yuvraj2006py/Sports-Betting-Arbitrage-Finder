from db import Base, engine
import models

print("📦 Creating tables...")
Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully!")
