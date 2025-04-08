from database import engine, Base
from models import VideoSummary

def recreate_database():
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("Banco de dados recriado com sucesso!")

if __name__ == "__main__":
    recreate_database() 