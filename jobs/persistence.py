"""Database persistence functionality for scraped data."""

from typing import Dict, Any, Optional

from db.database import SessionLocal
from db.models import RawData


class DatabasePersistence:
    """Handles persistence of scraped data to PostgreSQL database."""

    def __init__(self):
        """Initialize database persistence."""
        self.session = None

    def connect(self):
        """Establish database connection."""
        try:
            self.session = SessionLocal()
            print("✅ Connected to database")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self.session:
            self.session.close()
            self.session = None
            print("🔌 Disconnected from database")
    
    def save_condition_data(self, slug: str, data: Dict[str, Any]) -> Optional[str]:
        """
        Save scraped condition data to the database.
        
        Args:
            slug: The condition slug (e.g., 'acne', 'diabetes')
            data: The scraped condition data
            
        Returns:
            The UUID of the saved record, or None if failed
        """
        if not self.session:
            print("❌ No database connection")
            return None
        
        try:
            # Create RawData record
            raw_data = RawData(
                content=data,
                source=f"medical_conditions:{slug}"
            )
            
            self.session.add(raw_data)
            self.session.commit()
            
            print(f"✅ Saved condition '{slug}' to database (ID: {raw_data.id})")
            return str(raw_data.id)
            
        except Exception as e:
            print(f"❌ Failed to save condition '{slug}' to database: {e}")
            self.session.rollback()
            return None
    
    def check_existing_condition(self, slug: str) -> bool:
        """
        Check if a condition already exists in the database.
        
        Args:
            slug: The condition slug to check
            
        Returns:
            True if the condition exists, False otherwise
        """
        if not self.session:
            return False
        
        try:
            existing = self.session.query(RawData).filter(
                RawData.source == f"medical_conditions:{slug}"
            ).first()
            
            return existing is not None
            
        except Exception as e:
            print(f"⚠️ Error checking existing condition '{slug}': {e}")
            return False
    
    def get_condition_count(self) -> int:
        """
        Get the total number of conditions stored in the database.
        
        Returns:
            Number of stored conditions
        """
        if not self.session:
            return 0
        
        try:
            count = self.session.query(RawData).filter(
                RawData.source.like("medical_conditions:%")
            ).count()
            
            return count
            
        except Exception as e:
            print(f"⚠️ Error getting condition count: {e}")
            return 0