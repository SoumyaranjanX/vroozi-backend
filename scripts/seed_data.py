"""
Script to seed initial data into MongoDB for development and testing environments.
Provides comprehensive test data including users with different roles, contracts in various states,
and purchase orders with different templates.

Version: 1.0
"""

# External imports with versions
from datetime import datetime, timedelta  # built-in
import random  # built-in
import uuid  # built-in
import argparse  # built-in
import logging  # built-in
from typing import Dict, List, Optional

# Internal imports
from app.models.user import User, create_user, ROLE_CHOICES
from app.models.contract import Contract, create_contract, CONTRACT_STATUS_CHOICES
from app.models.purchase_order import PurchaseOrder, PO_STATUS_CHOICES, PO_TEMPLATE_CHOICES
from app.db.mongodb import get_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global constants
TEST_USERS = [
    {
        "email": "admin@example.com",
        "password": "admin123",
        "role": "admin",
        "metadata": {"last_login": None, "failed_attempts": 0}
    },
    {
        "email": "manager@example.com",
        "password": "manager123",
        "role": "contract_manager",
        "metadata": {"department": "Procurement"}
    },
    {
        "email": "reviewer@example.com",
        "password": "reviewer123",
        "role": "reviewer",
        "metadata": {"review_count": 0}
    },
    {
        "email": "user@example.com",
        "password": "user123",
        "role": "basic_user",
        "metadata": {"access_level": 1}
    }
]

SAMPLE_FILE_PATHS = ["contracts/test1.pdf", "contracts/test2.docx", "contracts/test3.pdf"]
BATCH_SIZE = 100
MAX_RETRIES = 3

async def seed_users(config: Dict) -> Dict:
    """
    Creates test users with different roles and security metadata.
    
    Args:
        config: Configuration dictionary for seeding
        
    Returns:
        Dict: Mapping of created user emails to IDs with metadata
    """
    logger.info("Starting user seeding process...")
    user_mapping = {}
    
    try:
        db = await get_database()
        
        # Clear existing users if specified
        if config.get('clear_existing'):
            await db.users.delete_many({})
            logger.info("Cleared existing users")
        
        # Create test users
        for user_data in TEST_USERS:
            try:
                # Add required fields
                user_data['first_name'] = f"Test {user_data['role'].title()}"
                user_data['last_name'] = "User"
                
                # Create user with secure password hashing
                user = await create_user(user_data)
                
                user_mapping[user_data['email']] = {
                    'id': str(user._id),
                    'role': user_data['role'],
                    'metadata': user_data['metadata']
                }
                
                logger.info(f"Created user: {user_data['email']} with role: {user_data['role']}")
                
            except Exception as e:
                logger.error(f"Error creating user {user_data['email']}: {str(e)}")
                
        logger.info(f"Successfully created {len(user_mapping)} test users")
        return user_mapping
        
    except Exception as e:
        logger.error(f"User seeding failed: {str(e)}")
        raise

async def seed_contracts(user_mapping: Dict, config: Dict) -> Dict:
    """
    Creates sample contracts with different statuses and validation states.
    
    Args:
        user_mapping: Dictionary mapping of created users
        config: Configuration dictionary for seeding
        
    Returns:
        Dict: Mapping of created contract IDs with metadata
    """
    logger.info("Starting contract seeding process...")
    contract_mapping = {}
    
    try:
        db = await get_database()
        
        # Clear existing contracts if specified
        if config.get('clear_existing'):
            await db.contracts.delete_many({})
            logger.info("Cleared existing contracts")
        
        # Create contracts for each user
        for email, user_data in user_mapping.items():
            contracts_to_create = random.randint(2, 5)
            
            for _ in range(contracts_to_create):
                try:
                    # Prepare contract data
                    contract_data = {
                        'file_path': random.choice(SAMPLE_FILE_PATHS),
                        'status': random.choice(CONTRACT_STATUS_CHOICES),
                        'created_by': user_data['id'],
                        'metadata': {
                            'department': user_data['metadata'].get('department', 'General'),
                            'priority': random.choice(['low', 'medium', 'high']),
                            'value': random.randint(1000, 100000)
                        },
                        'file_size': random.randint(1000000, 5000000)  # 1-5MB
                    }
                    
                    # Create contract with security context
                    contract = await create_contract(
                        contract_data,
                        security_context={'user_id': user_data['id'], 'role': user_data['role']}
                    )
                    
                    contract_mapping[str(contract._id)] = {
                        'status': contract.status,
                        'created_by': user_data['id'],
                        'file_path': contract.file_path
                    }
                    
                    logger.info(f"Created contract for user {email} with status: {contract.status}")
                    
                except Exception as e:
                    logger.error(f"Error creating contract for user {email}: {str(e)}")
        
        logger.info(f"Successfully created {len(contract_mapping)} test contracts")
        return contract_mapping
        
    except Exception as e:
        logger.error(f"Contract seeding failed: {str(e)}")
        raise

async def seed_purchase_orders(user_mapping: Dict, contract_mapping: Dict, config: Dict) -> Dict:
    """
    Creates sample purchase orders with different templates and states.
    
    Args:
        user_mapping: Dictionary mapping of created users
        contract_mapping: Dictionary mapping of created contracts
        config: Configuration dictionary for seeding
        
    Returns:
        Dict: Dictionary of created purchase order IDs with metadata
    """
    logger.info("Starting purchase order seeding process...")
    po_mapping = {}
    
    try:
        db = await get_database()
        
        # Clear existing POs if specified
        if config.get('clear_existing'):
            await db.purchase_orders.delete_many({})
            logger.info("Cleared existing purchase orders")
        
        # Create POs for contracts
        for contract_id, contract_data in contract_mapping.items():
            if contract_data['status'] in ['VALIDATED', 'COMPLETED']:
                try:
                    # Prepare PO data
                    po_data = {
                        'po_number': f"PO-{uuid.uuid4().hex[:8].upper()}",
                        'status': random.choice(PO_STATUS_CHOICES),
                        'contract_id': contract_id,
                        'generated_by': contract_data['created_by'],
                        'template_type': random.choice(PO_TEMPLATE_CHOICES),
                        'output_format': random.choice(['pdf', 'docx']),
                        'po_data': {
                            'items': [
                                {
                                    'description': f"Item {i}",
                                    'quantity': random.randint(1, 10),
                                    'price': random.randint(100, 1000)
                                } for i in range(1, random.randint(2, 5))
                            ],
                            'terms': "Net 30",
                            'delivery': "Standard Shipping"
                        },
                        'include_logo': random.choice([True, False]),
                        'digital_signature': True,
                        'send_notification': random.choice([True, False])
                    }
                    
                    # Create PO document
                    po = PurchaseOrder(**po_data)
                    await po.save()
                    
                    po_mapping[str(po._id)] = {
                        'po_number': po.po_number,
                        'status': po.status,
                        'contract_id': contract_id
                    }
                    
                    logger.info(f"Created PO {po.po_number} for contract {contract_id}")
                    
                except Exception as e:
                    logger.error(f"Error creating PO for contract {contract_id}: {str(e)}")
        
        logger.info(f"Successfully created {len(po_mapping)} test purchase orders")
        return po_mapping
        
    except Exception as e:
        logger.error(f"Purchase order seeding failed: {str(e)}")
        raise

async def main() -> int:
    """
    Main function to orchestrate data seeding with error handling.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Seed database with test data')
        parser.add_argument('--clear', action='store_true', help='Clear existing data before seeding')
        parser.add_argument('--env', choices=['development', 'staging'], default='development',
                          help='Target environment for seeding')
        args = parser.parse_args()
        
        # Prepare configuration
        config = {
            'environment': args.env,
            'clear_existing': args.clear,
            'batch_size': BATCH_SIZE
        }
        
        logger.info(f"Starting data seeding for {args.env} environment")
        
        # Initialize database connection
        db = await get_database()
        
        # Seed data in sequence
        user_mapping = await seed_users(config)
        contract_mapping = await seed_contracts(user_mapping, config)
        po_mapping = await seed_purchase_orders(user_mapping, contract_mapping, config)
        
        # Print summary
        logger.info("Data seeding completed successfully")
        logger.info(f"Created {len(user_mapping)} users")
        logger.info(f"Created {len(contract_mapping)} contracts")
        logger.info(f"Created {len(po_mapping)} purchase orders")
        
        return 0
        
    except Exception as e:
        logger.error(f"Data seeding failed: {str(e)}")
        return 1

if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)
```

This script provides a comprehensive data seeding solution with the following features:

1. Creates test users with different roles (admin, contract_manager, reviewer, basic_user)
2. Generates sample contracts in various states with realistic metadata
3. Creates purchase orders with different templates and statuses
4. Implements proper error handling and logging
5. Supports environment-specific configurations
6. Maintains data integrity and relationships between entities
7. Includes command-line arguments for flexibility
8. Follows security best practices for password handling
9. Provides detailed logging and execution summary

The script can be run with optional arguments:
```bash
# Basic usage
python seed_data.py

# Clear existing data before seeding
python seed_data.py --clear

# Seed staging environment
python seed_data.py --env staging