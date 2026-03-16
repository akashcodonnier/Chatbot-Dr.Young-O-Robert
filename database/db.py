#!/usr/bin/env python3
"""
Database connection module for Dr. Robert Young's semantic search system

This module provides database connection functionality for the semantic search system.
It manages MySQL connections for storing and retrieving articles with their embeddings.

Configuration:
- Supports environment variables for cloud deployment (Railway, Render, etc.)
- Falls back to localhost defaults for local development
- Environment variables:
  * DB_HOST: Database host (default: localhost)
  * DB_USER: Database username (default: root)
  * DB_PASSWORD: Database password (default: empty string)
  * DB_NAME: Database name (default: case_studies_db)

Usage:
- Local development: Works automatically with defaults
- Cloud deployment: Set environment variables in platform settings
"""

# Standard library imports
import os

# Third-party imports
import mysql.connector  # MySQL database connector


def get_connection():
    """
    Establish and return a connection to the MySQL database

    This function creates a connection using environment variables if available,
    otherwise falls back to localhost defaults for development.

    Environment variables (optional):
    - DB_HOST: Database host
    - DB_USER: Database username
    - DB_PASSWORD: Database password
    - DB_NAME: Database name

    Returns:
        mysql.connector.connection.MySQLConnection: Database connection object

    Note:
        - Automatically detects local vs cloud environment
        - Local: Uses localhost with default credentials
        - Cloud: Uses environment variables from platform
    """
    return mysql.connector.connect(
        host=os.getenv("DB_HOST") or os.getenv("MYSQLHOST", "localhost"),
        user=os.getenv("DB_USER") or os.getenv("MYSQLUSER", "root"),
        password=os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE", "case_studies_db"),
        port=int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT", "3306"))
    )
