#!/usr/bin/env python3
"""
Example Python Code for Tree-sitter Analysis
This module demonstrates various Python constructs that the Tree-sitter analyzer can detect.
"""

import os
import sys
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


# Module-level constants
MAX_CONNECTIONS = 100
DEFAULT_TIMEOUT = 30.0
API_VERSION = "v1.2.3"

# Module-level variables
connection_pool = []
_private_cache = {}


@dataclass
class UserProfile:
    """Represents a user profile with basic information"""

    username: str
    email: str
    age: Optional[int] = None
    preferences: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True

    def __post_init__(self):
        """Validate user data after initialization"""
        if not self.username or len(self.username) < 3:
            raise ValueError("Username must be at least 3 characters long")

    @property
    def display_name(self) -> str:
        """Get the display name for the user"""
        return self.username.title()

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int, bool]]) -> "UserProfile":
        """Create UserProfile from dictionary"""
        return cls(
            username=data["username"],
            email=data["email"],
            age=data.get("age"),
            is_active=data.get("is_active", True),
        )

    def to_dict(self) -> Dict[str, Union[str, int, bool]]:
        """Convert UserProfile to dictionary"""
        return {
            "username": self.username,
            "email": self.email,
            "age": self.age,
            "is_active": self.is_active,
            "preferences": self.preferences,
        }


class DatabaseConnection(ABC):
    """Abstract base class for database connections"""

    def __init__(self, connection_string: str, timeout: float = DEFAULT_TIMEOUT):
        self.connection_string = connection_string
        self.timeout = timeout
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the database"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the database"""
        pass

    @abstractmethod
    async def execute_query(
        self, query: str, params: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute a query and return results"""
        pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._connected:
            asyncio.run(self.disconnect())


class PostgreSQLConnection(DatabaseConnection):
    """PostgreSQL database connection implementation"""

    def __init__(
        self, host: str, port: int, database: str, username: str, password: str
    ):
        connection_string = (
            f"postgresql://{username}:{password}@{host}:{port}/{database}"
        )
        super().__init__(connection_string)
        self.host = host
        self.port = port
        self.database = database

    async def connect(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            # Simulate connection logic
            if self._is_valid_connection():
                self._connected = True
                print(f"Connected to PostgreSQL at {self.host}:{self.port}")
                return True
        except Exception as e:
            print(f"Failed to connect: {e}")
        return False

    async def disconnect(self) -> None:
        """Disconnect from PostgreSQL database"""
        if self._connected:
            self._connected = False
            print("Disconnected from PostgreSQL")

    async def execute_query(
        self, query: str, params: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute PostgreSQL query"""
        if not self._connected:
            raise ConnectionError("Not connected to database")

        # Simulate query execution
        results = []
        complexity_score = self._calculate_query_complexity(query)

        if complexity_score > 10:
            print(f"Warning: Complex query detected (score: {complexity_score})")

        return results

    def _is_valid_connection(self) -> bool:
        """Check if connection parameters are valid"""
        return all([self.host, self.port, self.database])

    def _calculate_query_complexity(self, query: str) -> int:
        """Calculate query complexity score"""
        complexity = 1

        # Check for various SQL constructs
        keywords = ["JOIN", "UNION", "SUBQUERY", "WHERE", "GROUP BY", "ORDER BY"]
        for keyword in keywords:
            if keyword.lower() in query.lower():
                complexity += 1

        # Check for nested conditions
        if "AND" in query.upper() or "OR" in query.upper():
            complexity += 2

        return complexity


class UserService:
    """Service class for managing users"""

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection
        self._user_cache: Dict[str, UserProfile] = {}

    async def create_user(self, username: str, email: str, **kwargs) -> UserProfile:
        """Create a new user"""
        # Validate input
        if not username or not email:
            raise ValueError("Username and email are required")

        if await self._user_exists(username):
            raise ValueError(f"User {username} already exists")

        # Create user profile
        user = UserProfile(
            username=username,
            email=email,
            age=kwargs.get("age"),
            preferences=kwargs.get("preferences", {}),
            is_active=kwargs.get("is_active", True),
        )

        # Save to database
        query = """
            INSERT INTO users (username, email, age, preferences, is_active)
            VALUES (%(username)s, %(email)s, %(age)s, %(preferences)s, %(is_active)s)
        """

        try:
            await self.db_connection.execute_query(query, user.to_dict())
            self._user_cache[username] = user
            print(f"Created user: {user.display_name}")
            return user
        except Exception as e:
            print(f"Failed to create user {username}: {e}")
            raise

    async def get_user(self, username: str) -> Optional[UserProfile]:
        """Get user by username"""
        # Check cache first
        if username in self._user_cache:
            return self._user_cache[username]

        # Query database
        query = "SELECT * FROM users WHERE username = %(username)s"
        results = await self.db_connection.execute_query(query, {"username": username})

        if results:
            user = UserProfile.from_dict(results[0])
            self._user_cache[username] = user
            return user

        return None

    async def update_user(self, username: str, **updates) -> bool:
        """Update user information"""
        user = await self.get_user(username)
        if not user:
            return False

        # Update user object
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)

        # Save to database
        query = """
            UPDATE users SET email=%(email)s, age=%(age)s,
                           preferences=%(preferences)s, is_active=%(is_active)s
            WHERE username=%(username)s
        """

        try:
            await self.db_connection.execute_query(query, user.to_dict())
            self._user_cache[username] = user
            return True
        except Exception as e:
            print(f"Failed to update user {username}: {e}")
            return False

    async def delete_user(self, username: str) -> bool:
        """Delete user"""
        if not await self._user_exists(username):
            return False

        query = "DELETE FROM users WHERE username = %(username)s"

        try:
            await self.db_connection.execute_query(query, {"username": username})
            if username in self._user_cache:
                del self._user_cache[username]
            print(f"Deleted user: {username}")
            return True
        except Exception as e:
            print(f"Failed to delete user {username}: {e}")
            return False

    async def list_users(self, active_only: bool = True) -> List[UserProfile]:
        """List all users"""
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE is_active = true"

        results = await self.db_connection.execute_query(query)
        users = []

        for result in results:
            try:
                user = UserProfile.from_dict(result)
                users.append(user)
            except Exception as e:
                print(f"Error parsing user data: {e}")
                continue

        return users

    async def _user_exists(self, username: str) -> bool:
        """Check if user exists"""
        user = await self.get_user(username)
        return user is not None

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None


# Utility functions
def get_environment_config() -> Dict[str, str]:
    """Get configuration from environment variables"""
    config = {
        "database_host": os.getenv("DB_HOST", "localhost"),
        "database_port": int(os.getenv("DB_PORT", "5432")),
        "database_name": os.getenv("DB_NAME", "myapp"),
        "database_user": os.getenv("DB_USER", "postgres"),
        "database_password": os.getenv("DB_PASSWORD", "password"),
    }

    # Validate required config
    required_keys = ["database_host", "database_name", "database_user"]
    missing_keys = [key for key in required_keys if not config.get(key)]

    if missing_keys:
        raise ValueError(f"Missing required configuration: {missing_keys}")

    return config


async def initialize_database() -> PostgreSQLConnection:
    """Initialize database connection"""
    config = get_environment_config()

    db = PostgreSQLConnection(
        host=config["database_host"],
        port=config["database_port"],
        database=config["database_name"],
        username=config["database_user"],
        password=config["database_password"],
    )

    if await db.connect():
        return db
    else:
        raise ConnectionError("Failed to connect to database")


def _private_helper_function(data: List[str]) -> List[str]:
    """Private helper function for data processing"""
    return [item.strip().lower() for item in data if item.strip()]


class __PrivateClass:
    """Private class for internal use only"""

    def __init__(self):
        self.__secret_data = "classified"

    def __private_method(self):
        """Private method"""
        return self.__secret_data


async def main():
    """Main application entry point"""
    try:
        # Initialize database
        db = await initialize_database()

        # Create user service
        user_service = UserService(db)

        # Create some example users
        users_data = [
            {"username": "alice", "email": "alice@example.com", "age": 25},
            {"username": "bob", "email": "bob@example.com", "age": 30},
            {"username": "charlie", "email": "charlie@example.com", "age": 22},
        ]

        for user_data in users_data:
            try:
                user = await user_service.create_user(**user_data)
                print(f"Created: {user.display_name}")
            except ValueError as e:
                print(f"Error creating user: {e}")

        # List all users
        users = await user_service.list_users()
        print(f"Total users: {len(users)}")

        # Update a user
        await user_service.update_user("alice", age=26, preferences={"theme": "dark"})

        # Get specific user
        alice = await user_service.get_user("alice")
        if alice:
            print(f"Alice's preferences: {alice.preferences}")

    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)
    finally:
        if "db" in locals():
            await db.disconnect()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
