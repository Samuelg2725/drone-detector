#!/usr/bin/env python3
# drone-detector/infrastructure/storage/migrations/versions/__init__.py
"""
Database Migration Versions Module

This module contains all database migration version scripts for the Drone Detection System.
Each migration file represents a specific version of the database schema.

Migration files follow the naming pattern:
    XXX_{description}.py

Where:
    XXX - Sequential number (001, 002, etc.) or timestamp-based
    description - Human-readable description of the migration

Available migrations:
    001_initial_schema.py      - Initial database schema
    002_add_drone_signatures.py - Drone signatures table
    003_add_remote_id_tables.py - Remote ID tables
    004_add_alert_escalation.py - Alert escalation tables
    005_add_spectrum_analysis.py - Spectrum analysis tables
    006_add_recording_management.py - Recording management tables
    007_add_performance_indexes.py - Performance indexes
    008_add_geospatial_support.py - Geospatial support
    009_add_audit_logging.py - Audit logging tables
    010_add_ml_training_data.py - ML training data tables
"""

from typing import Dict, Any, List, Optional

__version__ = "1.0.0"

# Export information about available migrations
MIGRATIONS_INFO: Dict[str, Dict[str, Any]] = {
    "001_initial_schema": {
        "revision": "001_initial_schema",
        "description": "Initial database schema with detections, alerts, and metrics tables",
        "dependencies": None,
        "created_at": "2024-01-01",
        "author": "Drone Detection Team"
    },
    "002_add_drone_signatures": {
        "revision": "002_add_drone_signatures",
        "description": "Add drone signatures and spectrum signatures tables",
        "dependencies": ["001_initial_schema"],
        "created_at": "2024-01-02",
        "author": "Drone Detection Team"
    },
    "003_add_remote_id_tables": {
        "revision": "003_add_remote_id_tables",
        "description": "Add Remote ID message tracking and session tables",
        "dependencies": ["002_add_drone_signatures"],
        "created_at": "2024-01-03",
        "author": "Drone Detection Team"
    },
    "004_add_alert_escalation": {
        "revision": "004_add_alert_escalation",
        "description": "Add alert escalation, notifications, and rules tables",
        "dependencies": ["003_add_remote_id_tables"],
        "created_at": "2024-01-04",
        "author": "Drone Detection Team"
    },
    "005_add_spectrum_analysis": {
        "revision": "005_add_spectrum_analysis",
        "description": "Add spectrum measurements, interference, and modulation analysis tables",
        "dependencies": ["004_add_alert_escalation"],
        "created_at": "2024-01-05",
        "author": "Drone Detection Team"
    },
    "006_add_recording_management": {
        "revision": "006_add_recording_management",
        "description": "Add recording management tables for IQ data storage",
        "dependencies": ["005_add_spectrum_analysis"],
        "created_at": "2024-01-06",
        "author": "Drone Detection Team"
    },
    "007_add_performance_indexes": {
        "revision": "007_add_performance_indexes",
        "description": "Add performance indexes and FTS for text search",
        "dependencies": ["006_add_recording_management"],
        "created_at": "2024-01-07",
        "author": "Drone Detection Team"
    },
    "008_add_geospatial_support": {
        "revision": "008_add_geospatial_support",
        "description": "Add geofence zones, violations, and geolocation history tables",
        "dependencies": ["007_add_performance_indexes"],
        "created_at": "2024-01-08",
        "author": "Drone Detection Team"
    },
    "009_add_audit_logging": {
        "revision": "009_add_audit_logging",
        "description": "Add audit logging, system events, and configuration history tables",
        "dependencies": ["008_add_geospatial_support"],
        "created_at": "2024-01-09",
        "author": "Drone Detection Team"
    },
    "010_add_ml_training_data": {
        "revision": "010_add_ml_training_data",
        "description": "Add ML training samples, models, predictions, and training jobs tables",
        "dependencies": ["009_add_audit_logging"],
        "created_at": "2024-01-10",
        "author": "Drone Detection Team"
    }
}


def get_migration_list() -> List[str]:
    """
    Get list of all available migration files in order
    
    Returns:
        List of migration revision names in dependency order
    """
    return list(MIGRATIONS_INFO.keys())


def get_migration_info(revision: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific migration
    
    Args:
        revision: Migration revision name
        
    Returns:
        Migration information dictionary or None if not found
    """
    return MIGRATIONS_INFO.get(revision)


def get_latest_migration() -> Optional[str]:
    """
    Get the latest migration revision
    
    Returns:
        Latest migration revision name
    """
    revisions = get_migration_list()
    return revisions[-1] if revisions else None


def get_dependency_chain(revision: str) -> List[str]:
    """
    Get the dependency chain for a migration
    
    Args:
        revision: Migration revision name
        
    Returns:
        List of revisions in dependency order up to the specified revision
    """
    if revision not in MIGRATIONS_INFO:
        return []
    
    chain = []
    current = revision
    
    while current:
        chain.insert(0, current)
        info = MIGRATIONS_INFO.get(current)
        if info and info.get('dependencies'):
            current = info['dependencies'][0] if info['dependencies'] else None
        else:
            current = None
    
    return chain


def get_migrations_summary() -> Dict[str, Any]:
    """
    Get a summary of all migrations
    
    Returns:
        Dictionary with migration summary information
    """
    return {
        "total_migrations": len(MIGRATIONS_INFO),
        "latest_migration": get_latest_migration(),
        "migrations": [
            {
                "revision": rev,
                "description": info["description"],
                "created_at": info["created_at"]
            }
            for rev, info in MIGRATIONS_INFO.items()
        ]
    }


# Version tracking
__all__ = [
    "MIGRATIONS_INFO",
    "get_migration_list",
    "get_migration_info",
    "get_latest_migration",
    "get_dependency_chain",
    "get_migrations_summary"
]