#!/usr/bin/env python3
"""
Data Export Utility

This script exports data from the Drone Detection System database to various formats:
- CSV (Comma Separated Values)
- JSON (JavaScript Object Notation)
- Excel (XLSX)
- Parquet (columnar storage)
- SQL dump
- HTML report
- GeoJSON (for map visualization)

Features:
- Filter by date range, drone type, threat level
- Select specific fields to export
- Batch export with pagination
- Compressed output
- Progress tracking
- Email notification on completion
- Scheduled exports via cron
"""

import argparse
import asyncio
import csv
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.storage.database import DatabaseManager
from infrastructure.storage.repositories import DetectionRepository, AlertRepository
from infrastructure.monitoring.logger import get_logger

# Optional imports
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils.dataframe import dataframe_to_rows
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import geopandas as gpd
    from shapely.geometry import Point
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


# ============================================================================
# Configuration
# ============================================================================

logger = get_logger(__name__)


class ExportConfig:
    """Export configuration"""
    
    # Default export settings
    DEFAULT_FORMAT: str = "csv"
    DEFAULT_LIMIT: int = 10000
    BATCH_SIZE: int = 5000
    
    # Output directory
    OUTPUT_DIR: Path = Path("data/exports")
    
    # Date formats
    DATE_FORMAT: str = "%Y-%m-%d"
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    
    # CSV settings
    CSV_DELIMITER: str = ","
    CSV_ENCODING: str = "utf-8"
    
    # JSON settings
    JSON_INDENT: int = 2
    JSON_ENSURE_ASCII: bool = False
    
    # Excel settings
    EXCEL_SHEET_NAME: str = "Data"
    
    # Compression
    COMPRESSION: bool = False
    COMPRESSION_LEVEL: int = 6
    
    # Email notification
    EMAIL_ENABLED: bool = False
    EMAIL_RECIPIENTS: List[str] = []
    EMAIL_SMTP_SERVER: str = "smtp.gmail.com"
    EMAIL_SMTP_PORT: int = 587


# ============================================================================
# Data Exporter Class
# ============================================================================

class DataExporter:
    """
    Comprehensive data export utility
    
    Supports exporting:
    - Detections
    - Alerts
    - Remote ID messages
    - System metrics
    - Geofence violations
    """
    
    def __init__(self, config: ExportConfig = None):
        """
        Initialize data exporter
        
        Args:
            config: Export configuration
        """
        self.config = config or ExportConfig()
        self.db = DatabaseManager()
        self.detection_repo = DetectionRepository(self.db)
        self.alert_repo = AlertRepository(self.db)
        
        # Create output directory
        self.config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        print("=" * 60)
        print("Data Export Utility")
        print("=" * 60)
    
    # ========================================================================
    # Export Methods
    # ========================================================================
    
    async def export_detections(
        self,
        output_file: str = None,
        format: str = "csv",
        start_date: datetime = None,
        end_date: datetime = None,
        drone_type: str = None,
        threat_level: str = None,
        min_confidence: float = None,
        fields: List[str] = None,
        limit: int = None,
        compression: bool = None
    ) -> Path:
        """
        Export detection data
        
        Args:
            output_file: Output file path (auto-generated if None)
            format: Export format (csv, json, excel, parquet)
            start_date: Start date filter
            end_date: End date filter
            drone_type: Filter by drone type
            threat_level: Filter by threat level
            min_confidence: Minimum confidence
            fields: List of fields to export
            limit: Maximum number of records
            compression: Enable compression
            
        Returns:
            Path to exported file
        """
        print(f"\n📊 Exporting detections...")
        
        # Build query
        query = "SELECT * FROM detections WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        if drone_type:
            query += " AND drone_type = ?"
            params.append(drone_type)
        
        if threat_level:
            query += " AND threat_level = ?"
            params.append(threat_level)
        
        if min_confidence:
            query += " AND confidence >= ?"
            params.append(min_confidence)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        # Execute query
        async with self.db._adapter._get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        
        # Convert to list of dicts
        data = [dict(zip(columns, row)) for row in rows]
        
        # Filter fields
        if fields:
            data = [{k: v for k, v in row.items() if k in fields} for row in data]
        
        print(f"  Exporting {len(data)} records")
        
        # Generate filename
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"detections_{timestamp}.{format}"
            if compression:
                output_file += ".gz"
        
        output_path = self.config.OUTPUT_DIR / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export based on format
        if format == "csv":
            await self._export_to_csv(data, output_path, compression)
        elif format == "json":
            await self._export_to_json(data, output_path, compression)
        elif format == "excel":
            await self._export_to_excel(data, output_path)
        elif format == "parquet":
            await self._export_to_parquet(data, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"  ✅ Exported to: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return output_path
    
    async def export_alerts(
        self,
        output_file: str = None,
        format: str = "csv",
        start_date: datetime = None,
        end_date: datetime = None,
        severity: str = None,
        resolved: bool = None,
        limit: int = None
    ) -> Path:
        """
        Export alert data
        
        Args:
            output_file: Output file path
            format: Export format
            start_date: Start date filter
            end_date: End date filter
            severity: Filter by severity
            resolved: Filter by resolved status
            limit: Maximum records
            
        Returns:
            Path to exported file
        """
        print(f"\n🔔 Exporting alerts...")
        
        # Build query
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        if resolved is not None:
            query += " AND resolved = ?"
            params.append(1 if resolved else 0)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        # Execute query
        async with self.db._adapter._get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        
        # Convert to list of dicts
        data = [dict(zip(columns, row)) for row in rows]
        
        print(f"  Exporting {len(data)} records")
        
        # Generate filename
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"alerts_{timestamp}.{format}"
        
        output_path = self.config.OUTPUT_DIR / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export based on format
        if format == "csv":
            await self._export_to_csv(data, output_path)
        elif format == "json":
            await self._export_to_json(data, output_path)
        elif format == "excel":
            await self._export_to_excel(data, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"  ✅ Exported to: {output_path}")
        
        return output_path
    
    async def export_remote_id(
        self,
        output_file: str = None,
        format: str = "csv",
        start_date: datetime = None,
        end_date: datetime = None,
        uas_id: str = None,
        limit: int = None
    ) -> Path:
        """
        Export Remote ID messages
        
        Args:
            output_file: Output file path
            format: Export format
            start_date: Start date filter
            end_date: End date filter
            uas_id: Filter by UAS ID
            limit: Maximum records
            
        Returns:
            Path to exported file
        """
        print(f"\n🆔 Exporting Remote ID messages...")
        
        # Build query
        query = "SELECT * FROM remote_id_messages WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        if uas_id:
            query += " AND uas_id = ?"
            params.append(uas_id)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        # Execute query
        async with self.db._adapter._get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        
        # Convert to list of dicts
        data = [dict(zip(columns, row)) for row in rows]
        
        print(f"  Exporting {len(data)} records")
        
        # Generate filename
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"remote_id_{timestamp}.{format}"
        
        output_path = self.config.OUTPUT_DIR / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export based on format
        if format == "csv":
            await self._export_to_csv(data, output_path)
        elif format == "json":
            await self._export_to_json(data, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"  ✅ Exported to: {output_path}")
        
        return output_path
    
    async def export_geojson(
        self,
        output_file: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        threat_level: str = None
    ) -> Path:
        """
        Export detections as GeoJSON for mapping
        
        Args:
            output_file: Output file path
            start_date: Start date filter
            end_date: End date filter
            threat_level: Filter by threat level
            
        Returns:
            Path to exported file
        """
        print(f"\n🗺️ Exporting GeoJSON...")
        
        if not HAS_GEOPANDAS:
            print("  ⚠️ GeoPandas not installed. Install with: pip install geopandas")
            return None
        
        # Query detections with coordinates
        query = """
            SELECT id, timestamp, drone_type, confidence, threat_level, 
                   latitude, longitude, altitude
            FROM detections 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        if threat_level:
            query += " AND threat_level = ?"
            params.append(threat_level)
        
        query += " ORDER BY timestamp DESC"
        
        # Execute query
        async with self.db._adapter._get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        
        # Convert to GeoDataFrame
        data = [dict(zip(columns, row)) for row in rows]
        
        if not data:
            print("  No location data found")
            return None
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            data,
            geometry=[Point(row['longitude'], row['latitude']) for row in data],
            crs="EPSG:4326"
        )
        
        # Generate filename
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"detections_{timestamp}.geojson"
        
        output_path = self.config.OUTPUT_DIR / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export
        gdf.to_file(output_path, driver="GeoJSON")
        
        print(f"  ✅ Exported to: {output_path}")
        
        return output_path
    
    # ========================================================================
    # Format Export Methods
    # ========================================================================
    
    async def _export_to_csv(self, data: List[Dict], output_path: Path, compression: bool = False):
        """Export data to CSV format"""
        
        if not data:
            # Create empty file with headers
            output_path.touch()
            return
        
        mode = 'wt'
        encoding = self.config.CSV_ENCODING
        
        if compression:
            import gzip
            f = gzip.open(output_path, mode='wt', encoding=encoding)
        else:
            f = open(output_path, mode, encoding=encoding)
        
        try:
            writer = csv.DictWriter(f, fieldnames=data[0].keys(), delimiter=self.config.CSV_DELIMITER)
            writer.writeheader()
            writer.writerows(data)
        finally:
            f.close()
    
    async def _export_to_json(self, data: List[Dict], output_path: Path, compression: bool = False):
        """Export data to JSON format"""
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'record_count': len(data),
            'data': data
        }
        
        mode = 'wt'
        encoding = self.config.JSON_ENSURE_ASCII
        
        if compression:
            import gzip
            f = gzip.open(output_path, mode='wt', encoding=encoding)
        else:
            f = open(output_path, mode, encoding=encoding)
        
        try:
            json.dump(
                export_data, f,
                indent=self.config.JSON_INDENT,
                ensure_ascii=self.config.JSON_ENSURE_ASCII,
                default=str
            )
        finally:
            f.close()
    
    async def _export_to_excel(self, data: List[Dict], output_path: Path):
        """Export data to Excel format"""
        
        if not HAS_OPENPYXL:
            print("  ⚠️ OpenPyXL not installed. Installing...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            global HAS_OPENPYXL
            HAS_OPENPYXL = True
        
        df = pd.DataFrame(data)
        
        # Create Excel writer
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=self.config.EXCEL_SHEET_NAME, index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets[self.config.EXCEL_SHEET_NAME]
            for column in df:
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                column_idx = df.columns.get_loc(column)
                worksheet.column_dimensions[chr(65 + column_idx)].width = min(column_width + 2, 50)
    
    async def _export_to_parquet(self, data: List[Dict], output_path: Path):
        """Export data to Parquet format"""
        
        if not HAS_PYARROW:
            print("  ⚠️ PyArrow not installed. Install with: pip install pyarrow")
            return
        
        df = pd.DataFrame(data)
        df.to_parquet(output_path, index=False, compression='snappy')
    
    # ========================================================================
    # Scheduled Export
    # ========================================================================
    
    async def setup_scheduled_export(
        self,
        export_type: str,
        schedule: str,
        output_dir: str = None,
        **kwargs
    ) -> bool:
        """
        Setup scheduled export using cron
        
        Args:
            export_type: Type of export ('detections', 'alerts', 'remote_id')
            schedule: Cron schedule (e.g., '0 1 * * *' for daily at 1 AM)
            output_dir: Output directory for exports
            **kwargs: Additional export parameters
            
        Returns:
            True if scheduled successfully
        """
        import subprocess
        import tempfile
        
        # Create export script
        script_content = f'''#!/bin/bash
# Auto-generated export script
cd {Path(__file__).parent.parent}
python {Path(__file__)} {export_type} --output-dir {output_dir or self.config.OUTPUT_DIR} '''
        
        # Add kwargs to command
        for key, value in kwargs.items():
            if value:
                script_content += f"--{key} {value} "
        
        # Add timestamp
        script_content += f"--suffix $(date +\\%Y\\%m\\%d_\\%H\\%M\\%S)"
        
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(script_content)
            script_path = f.name
        
        # Make executable
        subprocess.check_call(['chmod', '+x', script_path])
        
        # Add to crontab
        cron_line = f"{schedule} {script_path} >> /var/log/drone_export.log 2>&1"
        
        # Get current crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        current_crontab = result.stdout
        
        # Add new line if not exists
        if cron_line not in current_crontab:
            new_crontab = current_crontab + cron_line + '\n'
            subprocess.run(['crontab', '-'], input=new_crontab, text=True)
            print(f"✅ Scheduled export added: {schedule}")
            return True
        else:
            print(f"⚠️ Export already scheduled")
            return False
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_export_stats(self) -> Dict[str, Any]:
        """Get export statistics"""
        
        stats = {
            'exports_dir': str(self.config.OUTPUT_DIR),
            'total_files': 0,
            'total_size_mb': 0,
            'files_by_type': {}
        }
        
        for file_path in self.config.OUTPUT_DIR.rglob("*"):
            if file_path.is_file():
                stats['total_files'] += 1
                stats['total_size_mb'] += file_path.stat().st_size / (1024 * 1024)
                
                ext = file_path.suffix.lower()
                stats['files_by_type'][ext] = stats['files_by_type'].get(ext, 0) + 1
        
        return stats


# ============================================================================
# Command Line Interface
# ============================================================================

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Export data from Drone Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export detections to CSV
  python export_data.py detections --format csv --limit 1000
  
  # Export alerts to JSON with date filter
  python export_data.py alerts --format json --start-date 2024-01-01 --end-date 2024-01-31
  
  # Export Remote ID data to Excel
  python export_data.py remote-id --format excel --uas-id ABC123
  
  # Export as GeoJSON for mapping
  python export_data.py geojson --threat-level HIGH
  
  # Schedule daily export at 1 AM
  python export_data.py detections --schedule "0 1 * * *" --output-dir /backups/daily
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Export type')
    
    # Detections export
    detections_parser = subparsers.add_parser('detections', help='Export detections')
    detections_parser.add_argument('--format', '-f', default='csv', choices=['csv', 'json', 'excel', 'parquet'])
    detections_parser.add_argument('--output', '-o', help='Output file name')
    detections_parser.add_argument('--output-dir', help='Output directory')
    detections_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    detections_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    detections_parser.add_argument('--drone-type', help='Filter by drone type')
    detections_parser.add_argument('--threat-level', help='Filter by threat level')
    detections_parser.add_argument('--min-confidence', type=float, help='Minimum confidence')
    detections_parser.add_argument('--fields', help='Comma-separated list of fields')
    detections_parser.add_argument('--limit', type=int, help='Maximum records')
    detections_parser.add_argument('--compress', action='store_true', help='Compress output')
    detections_parser.add_argument('--schedule', help='Cron schedule for automated export')
    
    # Alerts export
    alerts_parser = subparsers.add_parser('alerts', help='Export alerts')
    alerts_parser.add_argument('--format', '-f', default='csv', choices=['csv', 'json', 'excel'])
    alerts_parser.add_argument('--output', '-o', help='Output file name')
    alerts_parser.add_argument('--output-dir', help='Output directory')
    alerts_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    alerts_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    alerts_parser.add_argument('--severity', help='Filter by severity')
    alerts_parser.add_argument('--resolved', action='store_true', help='Export resolved alerts')
    alerts_parser.add_argument('--unresolved', action='store_true', help='Export unresolved alerts')
    alerts_parser.add_argument('--limit', type=int, help='Maximum records')
    
    # Remote ID export
    remote_parser = subparsers.add_parser('remote-id', help='Export Remote ID messages')
    remote_parser.add_argument('--format', '-f', default='csv', choices=['csv', 'json'])
    remote_parser.add_argument('--output', '-o', help='Output file name')
    remote_parser.add_argument('--output-dir', help='Output directory')
    remote_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    remote_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    remote_parser.add_argument('--uas-id', help='Filter by UAS ID')
    remote_parser.add_argument('--limit', type=int, help='Maximum records')
    
    # GeoJSON export
    geojson_parser = subparsers.add_parser('geojson', help='Export as GeoJSON')
    geojson_parser.add_argument('--output', '-o', help='Output file name')
    geojson_parser.add_argument('--output-dir', help='Output directory')
    geojson_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    geojson_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    geojson_parser.add_argument('--threat-level', help='Filter by threat level')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show export statistics')
    
    args = parser.parse_args()
    
    # Configure exporter
    config = ExportConfig()
    if hasattr(args, 'output_dir') and args.output_dir:
        config.OUTPUT_DIR = Path(args.output_dir)
    
    exporter = DataExporter(config)
    
    try:
        if args.command == 'detections':
            # Parse date filters
            start_date = None
            if args.start_date:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_date = None
            if args.end_date:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d") + timedelta(days=1)
            
            # Parse fields
            fields = None
            if args.fields:
                fields = [f.strip() for f in args.fields.split(',')]
            
            # Parse resolved status
            resolved = None
            if args.resolved and args.unresolved:
                resolved = None
            elif args.resolved:
                resolved = True
            elif args.unresolved:
                resolved = False
            
            # Handle scheduled export
            if args.schedule:
                await exporter.setup_scheduled_export(
                    'detections',
                    args.schedule,
                    args.output_dir,
                    format=args.format,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    drone_type=args.drone_type,
                    threat_level=args.threat_level,
                    min_confidence=args.min_confidence,
                    limit=args.limit,
                    compress=args.compress
                )
            else:
                # Perform immediate export
                await exporter.export_detections(
                    output_file=args.output,
                    format=args.format,
                    start_date=start_date,
                    end_date=end_date,
                    drone_type=args.drone_type,
                    threat_level=args.threat_level,
                    min_confidence=args.min_confidence,
                    fields=fields,
                    limit=args.limit,
                    compression=args.compress
                )
        
        elif args.command == 'alerts':
            # Parse date filters
            start_date = None
            if args.start_date:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_date = None
            if args.end_date:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d") + timedelta(days=1)
            
            # Parse resolved status
            resolved = None
            if args.resolved and args.unresolved:
                resolved = None
            elif args.resolved:
                resolved = True
            elif args.unresolved:
                resolved = False
            
            await exporter.export_alerts(
                output_file=args.output,
                format=args.format,
                start_date=start_date,
                end_date=end_date,
                severity=args.severity,
                resolved=resolved,
                limit=args.limit
            )
        
        elif args.command == 'remote-id':
            # Parse date filters
            start_date = None
            if args.start_date:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_date = None
            if args.end_date:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d") + timedelta(days=1)
            
            await exporter.export_remote_id(
                output_file=args.output,
                format=args.format,
                start_date=start_date,
                end_date=end_date,
                uas_id=args.uas_id,
                limit=args.limit
            )
        
        elif args.command == 'geojson':
            # Parse date filters
            start_date = None
            if args.start_date:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_date = None
            if args.end_date:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d") + timedelta(days=1)
            
            await exporter.export_geojson(
                output_file=args.output,
                start_date=start_date,
                end_date=end_date,
                threat_level=args.threat_level
            )
        
        elif args.command == 'stats':
            stats = exporter.get_export_stats()
            print(f"\n📊 Export Statistics")
            print(f"  Directory: {stats['exports_dir']}")
            print(f"  Total files: {stats['total_files']}")
            print(f"  Total size: {stats['total_size_mb']:.2f} MB")
            print(f"  Files by type:")
            for ext, count in stats['files_by_type'].items():
                print(f"    {ext}: {count}")
        
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Export failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())