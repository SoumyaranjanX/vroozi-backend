import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_connection():
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["vroozi"]
        
        # Test the connection
        print("Testing MongoDB connection...")
        await db.command("ping")
        print("Successfully connected to MongoDB!")
        
        # List all collections
        collections = await db.list_collection_names()
        print(f"Available collections: {collections}")
        
    except Exception as e:
        print(f"Failed to connect to MongoDB: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_connection()) 