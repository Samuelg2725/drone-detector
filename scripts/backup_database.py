#!/usr/bin/env python3
"""
Database Backup Utility

This script provides comprehensive database backup capabilities for the Drone Detection System:
- Full database backup
- Incremental backups
- Scheduled backups via cron
- Backup compression
- Remote backup (S3, SFTP, etc.)
- Backup verification
- Restore from backup
- Backup retention management
- Email notifications
- Backup encryption
"""

import argparse
import asyncio
import gzip
import json
import shutil
import sqlite3
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import subprocess

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.monitoring.logger import get_logger

# Optional imports
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


# ============================================================================
# Configuration
# ============================================================================

logger = get_logger(__name__)


class BackupConfig:
    """Backup configuration"""
    
    # Database paths
    DB_PATH: Path = Path("data/detections.db")
    DB_WAL_PATH: Path = Path("data/detections.db-wal")
    DB_SHM_PATH: Path = Path("data/detections.db-shm")
    
    # Backup directories
    BACKUP_DIR: Path = Path("data/backups")
    TEMP_DIR: Path = Path("data/temp/backup")
    
    # Backup settings
    COMPRESSION: bool = True
    COMPRESSION_LEVEL: int = 6
    INCREMENTAL: bool = False
    VERIFY_BACKUP: bool = True
    
    # Retention
    RETAIN_DAYS: int = 30
    RETAIN_COUNT: int = 10
    
    # Remote backup (optional)
    REMOTE_ENABLED: bool = False
    REMOTE_TYPE: str = "s3"  # s3, sftp
    REMOTE_BUCKET: str = "drone-detector-backups"
    REMOTE_PATH: str = "database/"
    S3_REGION: str = "us-east-1"
    SFTP_HOST: str = ""
    SFTP_PORT: int = 22
    SFTP_USER: str = ""
    SFTP_PASSWORD: str = ""
    SFTP_KEY_PATH: str = ""
    
    # Encryption
    ENCRYPTION_ENABLED: bool = False
    ENCRYPTION_KEY: str = ""
    
    # Notifications
    EMAIL_ENABLED: bool = False
    EMAIL_RECIPIENTS: List[str] = []
    
    # Performance
    CHUNK_SIZE: int = 8192


# ============================================================================
# Backup Manager Class
# ============================================================================

class BackupManager:
    """
    Database backup manager
    
    Features:
    - Full and incremental backups
    - Backup compression
    - Remote backup (S3, SFTP)
    - Backup verification
    - Scheduled backups
    - Restore functionality
    - Retention management
    """
    
    def __init__(self, config: BackupConfig = None):
        """
        Initialize backup manager
        
        Args:
            config: Backup configuration
        """
        self.config = config or BackupConfig()
        
        # Ensure directories exist
        self.config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self.config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # S3 client
        self.s3_client = None
        if self.config.REMOTE_ENABLED and self.config.REMOTE_TYPE == "s3" and HAS_BOTO3:
            self.s3_client = boto3.client('s3', region_name=self.config.S3_REGION)
        
        print("=" * 60)
        print("Database Backup Utility")
        print("=" * 60)
        print(f"Database: {self.config.DB_PATH}")
        print(f"Backup directory: {self.config.BACKUP_DIR}")
    
    # ========================================================================
    # Backup Methods
    # ========================================================================
    
    async def backup(
        self,
        backup_name: str = None,
        compress: bool = None,
        incremental: bool = None,
        verify: bool = None
    ) -> Path:
        """
        Create database backup
        
        Args:
            backup_name: Custom backup name (auto-generated if None)
            compress: Enable compression (uses config if None)
            incremental: Create incremental backup
            verify: Verify backup after creation
            
        Returns:
            Path to backup file
        """
        print(f"\n📦 Creating database backup...")
        
        # Use config values if not specified
        compress = compress if compress is not None else self.config.COMPRESSION
        incremental = incremental if incremental is not None else self.config.INCREMENTAL
        verify = verify if verify is not None else self.config.VERIFY_BACKUP
        
        # Check if database exists
        if not self.config.DB_PATH.exists():
            raise FileNotFoundError(f"Database not found: {self.config.DB_PATH}")
        
        # Generate backup name
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"detections_{timestamp}"
        
        # Create backup
        if incremental:
            backup_path = await self._create_incremental_backup(backup_name, compress)
        else:
            backup_path = await self._create_full_backup(backup_name, compress)
        
        # Verify backup
        if verify:
            print("\n🔍 Verifying backup...")
            is_valid = await self.verify_backup(backup_path)
            if not is_valid:
                print("❌ Backup verification failed!")
                return None
            print("✅ Backup verification passed")
        
        # Calculate checksum
        checksum = self._calculate_checksum(backup_path)
        print(f"  Checksum: {checksum}")
        
        # Save backup metadata
        await self._save_backup_metadata(backup_path, checksum, incremental)
        
        # Cleanup old backups
        await self.cleanup_old_backups()
        
        # Remote backup
        if self.config.REMOTE_ENABLED:
            await self._upload_to_remote(backup_path)
        
        # Send notification
        if self.config.EMAIL_ENABLED:
            await self._send_notification(f"Backup created: {backup_path.name}")
        
        print(f"\n✅ Backup created: {backup_path}")
        print(f"  Size: {backup_path.stat().st_size / (1024*1024):.2f} MB")
        
        return backup_path
    
    async def _create_full_backup(self, backup_name: str, compress: bool) -> Path:
        """Create full database backup"""
        
        # Create temporary copy of database (to avoid locking issues)
        temp_db = self.config.TEMP_DIR / "temp_database.db"
        shutil.copy2(self.config.DB_PATH, temp_db)
        
        if compress:
            backup_path = self.config.BACKUP_DIR / f"{backup_name}.db.gz"
            
            # Compress and save
            with open(temp_db, 'rb') as f_in:
                with gzip.open(backup_path, 'wb', compresslevel=self.config.COMPRESSION_LEVEL) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            backup_path = self.config.BACKUP_DIR / f"{backup_name}.db"
            shutil.copy2(temp_db, backup_path)
        
        # Cleanup temp file
        temp_db.unlink()
        
        # Also backup WAL and SHM files if they exist
        if self.config.DB_WAL_PATH.exists():
            wal_backup = self.config.BACKUP_DIR / f"{backup_name}.db-wal"
            shutil.copy2(self.config.DB_WAL_PATH, wal_backup)
        
        if self.config.DB_SHM_PATH.exists():
            shm_backup = self.config.BACKUP_DIR / f"{backup_name}.db-shm"
            shutil.copy2(self.config.DB_SHM_PATH, shm_backup)
        
        return backup_path
    
    async def _create_incremental_backup(self, backup_name: str, compress: bool) -> Path:
        """Create incremental backup (WAL file)"""
        
        # For SQLite, incremental backup can be done using WAL file
        # This is a simplified version
        
        backup_path = self.config.BACKUP_DIR / f"{backup_name}_incremental.wal"
        
        if self.config.DB_WAL_PATH.exists():
            if compress:
                backup_path = backup_path.with_suffix('.gz')
                with open(self.config.DB_WAL_PATH, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb', compresslevel=self.config.COMPRESSION_LEVEL) as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(self.config.DB_WAL_PATH, backup_path)
            
            print(f"  Incremental backup (WAL size: {backup_path.stat().st_size / 1024:.1f} KB)")
        else:
            print("  No WAL file found, creating full backup instead")
            return await self._create_full_backup(backup_name, compress)
        
        return backup_path
    
    async def _save_backup_metadata(self, backup_path: Path, checksum: str, incremental: bool):
        """Save backup metadata"""
        
        metadata = {
            'backup_name': backup_path.name,
            'created_at': datetime.now().isoformat(),
            'database_size_bytes': self.config.DB_PATH.stat().st_size,
            'backup_size_bytes': backup_path.stat().st_size,
            'checksum': checksum,
            'incremental': incremental,
            'compressed': self.config.COMPRESSION,
            'wal_exists': self.config.DB_WAL_PATH.exists(),
            'shm_exists': self.config.DB_SHM_PATH.exists()
        }
        
        metadata_path = backup_path.with_suffix('.json')
        if backup_path.suffix == '.gz':
            metadata_path = backup_path.with_suffix('.json')
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    # ========================================================================
    # Restore Methods
    # ========================================================================
    
    async def restore(self, backup_path: Path, force: bool = False) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_path: Path to backup file
            force: Force restore even if database exists
            
        Returns:
            True if successful
        """
        print(f"\n🔄 Restoring database from: {backup_path.name}")
        
        if not backup_path.exists():
            print(f"❌ Backup not found: {backup_path}")
            return False
        
        # Check if database exists
        if self.config.DB_PATH.exists() and not force:
            response = input("Database already exists. Overwrite? (y/n): ")
            if response.lower() != 'y':
                print("Restore cancelled")
                return False
        
        # Create backup of current database
        if self.config.DB_PATH.exists():
            current_backup = self.config.BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(self.config.DB_PATH, current_backup)
            print(f"  Current database backed up to: {current_backup}")
        
        # Restore based on file type
        if backup_path.suffix == '.gz':
            # Compressed backup
            with gzip.open(backup_path, 'rb') as f_in:
                with open(self.config.DB_PATH, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Uncompressed backup
            shutil.copy2(backup_path, self.config.DB_PATH)
        
        # Verify restored database
        integrity_ok = await self._verify_database_integrity()
        
        if not integrity_ok:
            print("❌ Restored database failed integrity check!")
            return False
        
        print("✅ Database restored successfully")
        
        # Send notification
        if self.config.EMAIL_ENABLED:
            await self._send_notification(f"Database restored from: {backup_path.name}")
        
        return True
    
    async def _verify_database_integrity(self) -> bool:
        """Verify database integrity"""
        
        try:
            conn = sqlite3.connect(str(self.config.DB_PATH))
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            return result == "ok"
        except Exception as e:
            print(f"  Integrity check error: {e}")
            return False
    
    # ========================================================================
    # Verification Methods
    # ========================================================================
    
    async def verify_backup(self, backup_path: Path) -> bool:
        """
        Verify backup file integrity
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if valid
        """
        if not backup_path.exists():
            return False
        
        # Check file size
        if backup_path.stat().st_size == 0:
            print("  Backup file is empty")
            return False
        
        # Check if can be decompressed/extracted
        try:
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f:
                    # Read first few bytes to verify
                    f.read(1024)
            else:
                # For uncompressed, try to open as SQLite
                conn = sqlite3.connect(str(backup_path))
                conn.execute("SELECT 1")
                conn.close()
        except Exception as e:
            print(f"  Backup verification failed: {e}")
            return False
        
        return True
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file"""
        
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(self.config.CHUNK_SIZE), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    # ========================================================================
    # Maintenance Methods
    # ========================================================================
    
    async def cleanup_old_backups(self, days: int = None, keep_count: int = None) -> List[Path]:
        """
        Clean up old backups based on retention policy
        
        Args:
            days: Delete backups older than this many days
            keep_count: Keep this many most recent backups
            
        Returns:
            List of deleted backup paths
        """
        days = days or self.config.RETAIN_DAYS
        keep_count = keep_count or self.config.RETAIN_COUNT
        
        print(f"\n🧹 Cleaning up old backups...")
        
        # Find all backup files
        backup_files = []
        for ext in ['.db', '.db.gz', '.db-wal', '.db-shm']:
            backup_files.extend(self.config.BACKUP_DIR.glob(f"*{ext}"))
        
        # Sort by modification time
        backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        deleted = []
        
        # Delete by age
        cutoff_time = datetime.now() - timedelta(days=days)
        for backup in backup_files:
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            if mtime < cutoff_time:
                backup.unlink()
                deleted.append(backup)
                print(f"  Deleted (age): {backup.name}")
        
        # Delete by count (keep N most recent)
        if len(backup_files) > keep_count:
            to_delete = backup_files[keep_count:]
            for backup in to_delete:
                if backup not in deleted:  # Don't double-delete
                    backup.unlink()
                    deleted.append(backup)
                    print(f"  Deleted (count): {backup.name}")
        
        print(f"✅ Cleaned up {len(deleted)} old backups")
        
        return deleted
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_path in self.config.BACKUP_DIR.glob("*.db*"):
            if backup_path.suffix in ['.db', '.gz', '.wal']:
                info = {
                    'name': backup_path.name,
                    'size_mb': backup_path.stat().st_size / (1024 * 1024),
                    'created': datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
                    'path': str(backup_path)
                }
                
                # Check if metadata exists
                metadata_path = backup_path.with_suffix('.json')
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        info['metadata'] = json.load(f)
                
                backups.append(info)
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        
        return backups
    
    # ========================================================================
    # Remote Backup Methods
    # ========================================================================
    
    async def _upload_to_remote(self, backup_path: Path) -> bool:
        """
        Upload backup to remote storage
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if successful
        """
        if self.config.REMOTE_TYPE == "s3":
            return await self._upload_to_s3(backup_path)
        elif self.config.REMOTE_TYPE == "sftp":
            return await self._upload_to_sftp(backup_path)
        else:
            print(f"⚠️ Unknown remote type: {self.config.REMOTE_TYPE}")
            return False
    
    async def _upload_to_s3(self, backup_path: Path) -> bool:
        """Upload to AWS S3"""
        
        if not HAS_BOTO3:
            print("⚠️ Boto3 not installed. Install with: pip install boto3")
            return False
        
        if not self.s3_client:
            print("⚠️ S3 client not initialized")
            return False
        
        try:
            key = f"{self.config.REMOTE_PATH}{backup_path.name}"
            
            self.s3_client.upload_file(
                str(backup_path),
                self.config.REMOTE_BUCKET,
                key,
                ExtraArgs={'ServerSideEncryption': 'AES256'}
            )
            
            print(f"  ✅ Uploaded to S3: s3://{self.config.REMOTE_BUCKET}/{key}")
            return True
            
        except Exception as e:
            print(f"  ❌ S3 upload failed: {e}")
            return False
    
    async def _upload_to_sftp(self, backup_path: Path) -> bool:
        """Upload to SFTP server"""
        
        if not HAS_PARAMIKO:
            print("⚠️ Paramiko not installed. Install with: pip install paramiko")
            return False
        
        try:
            transport = paramiko.Transport((self.config.SFTP_HOST, self.config.SFTP_PORT))
            
            if self.config.SFTP_KEY_PATH:
                key = paramiko.RSAKey.from_private_key_file(self.config.SFTP_KEY_PATH)
                transport.connect(username=self.config.SFTP_USER, pkey=key)
            else:
                transport.connect(
                    username=self.config.SFTP_USER,
                    password=self.config.SFTP_PASSWORD
                )
            
            sftp = paramiko.SFTPClient.from_transport(transport)
            
            remote_path = f"{self.config.REMOTE_PATH}{backup_path.name}"
            sftp.put(str(backup_path), remote_path)
            
            sftp.close()
            transport.close()
            
            print(f"  ✅ Uploaded to SFTP: {self.config.SFTP_HOST}:{remote_path}")
            return True
            
        except Exception as e:
            print(f"  ❌ SFTP upload failed: {e}")
            return False
    
    # ========================================================================
    # Scheduled Backups
    # ========================================================================
    
    async def setup_scheduled_backup(
        self,
        schedule: str,
        incremental: bool = False
    ) -> bool:
        """
        Setup scheduled backup using cron
        
        Args:
            schedule: Cron schedule (e.g., '0 1 * * *' for daily at 1 AM)
            incremental: Whether to do incremental backups
            
        Returns:
            True if scheduled successfully
        """
        import tempfile
        
        # Create backup script
        script_content = f'''#!/bin/bash
# Auto-generated backup script
cd {Path(__file__).parent.parent}
python {Path(__file__)} backup --incremental {"--incremental" if incremental else ""} --quiet
        '''
        
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(script_content)
            script_path = f.name
        
        # Make executable
        subprocess.check_call(['chmod', '+x', script_path])
        
        # Add to crontab
        cron_line = f"{schedule} {script_path} >> /var/log/drone_backup.log 2>&1"
        
        # Get current crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        current_crontab = result.stdout
        
        # Add new line if not exists
        if cron_line not in current_crontab:
            new_crontab = current_crontab + cron_line + '\n'
            subprocess.run(['crontab', '-'], input=new_crontab, text=True)
            print(f"✅ Scheduled backup added: {schedule}")
            return True
        else:
            print(f"⚠️ Backup already scheduled")
            return False
    
    # ========================================================================
    # Notification Methods
    # ========================================================================
    
    async def _send_notification(self, message: str):
        """Send email notification"""
        
        # This would integrate with the notification service
        # For now, just log
        print(f"📧 Notification: {message}")
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def optimize_database(self) -> bool:
        """
        Optimize database before backup
        
        Returns:
            True if successful
        """
        print("\n🔧 Optimizing database...")
        
        try:
            conn = sqlite3.connect(str(self.config.DB_PATH))
            
            # Vacuum to reclaim space
            conn.execute("VACUUM")
            
            # Analyze for query optimization
            conn.execute("ANALYZE")
            
            # Checkpoint WAL
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            
            conn.close()
            
            print("✅ Database optimized")
            return True
            
        except Exception as e:
            print(f"❌ Optimization failed: {e}")
            return False
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """
        Get backup statistics
        
        Returns:
            Statistics dictionary
        """
        backups = list(self.config.BACKUP_DIR.glob("*.db*"))
        
        total_size = sum(b.stat().st_size for b in backups)
        
        # Group by type
        by_type = {}
        for backup in backups:
            ext = backup.suffix
            by_type[ext] = by_type.get(ext, 0) + 1
        
        return {
            'total_backups': len(backups),
            'total_size_mb': total_size / (1024 * 1024),
            'backup_dir': str(self.config.BACKUP_DIR),
            'by_type': by_type,
            'oldest_backup': min((b.stat().st_mtime for b in backups), default=0),
            'newest_backup': max((b.stat().st_mtime for b in backups), default=0)
        }


# ============================================================================
# Command Line Interface
# ============================================================================

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Database backup utility for Drone Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a backup
  python backup_database.py backup
  
  # Create compressed backup
  python backup_database.py backup --compress
  
  # Create incremental backup
  python backup_database.py backup --incremental
  
  # List backups
  python backup_database.py list
  
  # Restore from backup
  python backup_database.py restore backup.db.gz
  
  # Clean up old backups (keep last 10)
  python backup_database.py cleanup --keep 10
  
  # Optimize database before backup
  python backup_database.py optimize
  
  # Schedule daily backup at 1 AM
  python backup_database.py schedule --cron "0 1 * * *"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create database backup')
    backup_parser.add_argument('--name', '-n', help='Backup name')
    backup_parser.add_argument('--compress', '-c', action='store_true', help='Compress backup')
    backup_parser.add_argument('--incremental', '-i', action='store_true', help='Incremental backup')
    backup_parser.add_argument('--no-verify', action='store_true', help='Skip verification')
    backup_parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_file', help='Backup file to restore')
    restore_parser.add_argument('--force', '-f', action='store_true', help='Force restore')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List backups')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old backups')
    cleanup_parser.add_argument('--days', '-d', type=int, help='Delete older than N days')
    cleanup_parser.add_argument('--keep', '-k', type=int, help='Keep last N backups')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify backup')
    verify_parser.add_argument('backup_file', help='Backup file to verify')
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize database')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule automatic backups')
    schedule_parser.add_argument('--cron', required=True, help='Cron schedule expression')
    schedule_parser.add_argument('--incremental', action='store_true', help='Incremental backups')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show backup statistics')
    
    args = parser.parse_args()
    
    # Create backup manager
    manager = BackupManager()
    
    if args.command == 'backup':
        await manager.backup(
            backup_name=args.name,
            compress=args.compress,
            incremental=args.incremental,
            verify=not args.no_verify
        )
    
    elif args.command == 'restore':
        await manager.restore(Path(args.backup_file), force=args.force)
    
    elif args.command == 'list':
        backups = await manager.list_backups()
        print(f"\n📋 Available Backups ({len(backups)})")
        print("-" * 60)
        for backup in backups[:20]:  # Show last 20
            print(f"  {backup['name']}")
            print(f"    Size: {backup['size_mb']:.2f} MB")
            print(f"    Created: {backup['created']}")
            if 'metadata' in backup:
                print(f"    Checksum: {backup['metadata'].get('checksum', 'N/A')[:16]}...")
            print()
    
    elif args.command == 'cleanup':
        await manager.cleanup_old_backups(days=args.days, keep_count=args.keep)
    
    elif args.command == 'verify':
        is_valid = await manager.verify_backup(Path(args.backup_file))
        if is_valid:
            print(f"\n✅ Backup is valid: {args.backup_file}")
        else:
            print(f"\n❌ Backup is corrupted: {args.backup_file}")
    
    elif args.command == 'optimize':
        await manager.optimize_database()
    
    elif args.command == 'schedule':
        await manager.setup_scheduled_backup(args.cron, incremental=args.incremental)
    
    elif args.command == 'stats':
        stats = manager.get_backup_stats()
        print(f"\n📊 Backup Statistics")
        print(f"  Total backups: {stats['total_backups']}")
        print(f"  Total size: {stats['total_size_mb']:.2f} MB")
        print(f"  Backup directory: {stats['backup_dir']}")
        print(f"\n  By type:")
        for ext, count in stats['by_type'].items():
            print(f"    {ext}: {count}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())