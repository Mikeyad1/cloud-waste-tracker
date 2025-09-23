from src.db import engine
from src.models import Base

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("✅ tables created")

