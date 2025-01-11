"""
Database migration runner.

Version: 1.0
"""

import os
import importlib
import logging
from typing import List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def run_migrations(db: AsyncIOMotorDatabase, direction: str = "up") -> bool:
    """
    Run all database migrations in sequence.
    
    Args:
        db: AsyncIOMotorDatabase instance
        direction: Migration direction ("up" or "down")
        
    Returns:
        bool: True if all migrations successful, False otherwise
    """
    try:
        # Get list of migration files
        migration_files = sorted([
            f for f in os.listdir(os.path.dirname(__file__))
            if f.endswith('.py') and f != '__init__.py'
        ])
        
        if direction == "down":
            migration_files.reverse()
        
        # Run each migration
        for migration_file in migration_files:
            module_name = f"app.db.migrations.{migration_file[:-3]}"
            migration_module = importlib.import_module(module_name)
            
            func = getattr(migration_module, "upgrade" if direction == "up" else "downgrade")
            
            logger.info(f"Running migration {migration_file}")
            success = await func(db)
            
            if not success:
                logger.error(f"Migration {migration_file} failed")
                return False
                
            logger.info(f"Successfully completed migration {migration_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        return False 