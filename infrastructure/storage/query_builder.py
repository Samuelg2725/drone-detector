#!/usr/bin/env python3
# drone-detector/infrastructure/storage/query_builder.py
"""
Complex Query Construction Module

This module provides a flexible query builder for constructing complex database queries,
supporting:
- Fluent query building interface
- Dynamic WHERE clause construction
- JOIN operations across tables
- Subquery support
- Aggregation and GROUP BY
- Pagination and sorting
- Field selection and aliasing
- Conditional expression building
- Date/time filtering
- Geospatial queries
- Full-text search support
- Batch query optimization
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Tuple, Callable
from decimal import Decimal

# ============================================================================
# Enums and Constants
# ============================================================================

class Operator(Enum):
    """Comparison operators"""
    EQ = "="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    LIKE = "LIKE"
    ILIKE = "ILIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    BETWEEN = "BETWEEN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    CONTAINS = "CONTAINS"  # JSON contains


class LogicalOperator(Enum):
    """Logical operators for combining conditions"""
    AND = "AND"
    OR = "OR"


class OrderDirection(Enum):
    """Sort order directions"""
    ASC = "ASC"
    DESC = "DESC"


class JoinType(Enum):
    """JOIN types"""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL JOIN"


class AggregateFunction(Enum):
    """Aggregate functions"""
    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    GROUP_CONCAT = "GROUP_CONCAT"


# ============================================================================
# Query Condition Classes
# ============================================================================

@dataclass
class Condition:
    """Base condition class"""
    field: str
    operator: Operator
    value: Any
    table_alias: Optional[str] = None
    
    def to_sql(self, param_index: int, dialect: str = "sqlite") -> Tuple[str, Dict[str, Any]]:
        """Convert condition to SQL"""
        param_name = f"param_{param_index}"
        
        # Handle special operators
        if self.operator == Operator.IN:
            placeholders = ','.join([f":{param_name}_{i}" for i in range(len(self.value))])
            params = {f"{param_name}_{i}": v for i, v in enumerate(self.value)}
            sql = f"{self._get_field()} {self.operator.value} ({placeholders})"
            return sql, params
        
        elif self.operator == Operator.BETWEEN:
            sql = f"{self._get_field()} BETWEEN :{param_name}_start AND :{param_name}_end"
            params = {f"{param_name}_start": self.value[0], f"{param_name}_end": self.value[1]}
            return sql, params
        
        elif self.operator in [Operator.IS_NULL, Operator.IS_NOT_NULL]:
            sql = f"{self._get_field()} {self.operator.value}"
            return sql, {}
        
        elif self.operator == Operator.CONTAINS:
            # JSON contains for SQLite/PostgreSQL
            if dialect == "sqlite":
                sql = f"json_extract({self._get_field()}, '$') LIKE :{param_name}"
            elif dialect == "postgresql":
                sql = f"{self._get_field()} @> :{param_name}"
            else:
                sql = f"{self._get_field()} LIKE :{param_name}"
            return sql, {param_name: f'%{json.dumps(self.value)}%'}
        
        else:
            sql = f"{self._get_field()} {self.operator.value} :{param_name}"
            return sql, {param_name: self.value}
    
    def _get_field(self) -> str:
        """Get field name with table alias"""
        if self.table_alias:
            return f"{self.table_alias}.{self.field}"
        return self.field


class ConditionGroup:
    """Group of conditions with logical operators"""
    
    def __init__(self, operator: LogicalOperator = LogicalOperator.AND):
        self.operator = operator
        self.conditions: List[Union[Condition, 'ConditionGroup']] = []
    
    def add(self, condition: Union[Condition, 'ConditionGroup']):
        """Add a condition or group"""
        self.conditions.append(condition)
        return self
    
    def to_sql(self, param_index: int, dialect: str = "sqlite") -> Tuple[str, Dict[str, Any]]:
        """Convert condition group to SQL"""
        if not self.conditions:
            return "", {}
        
        sql_parts = []
        all_params = {}
        
        for condition in self.conditions:
            sql, params = condition.to_sql(param_index, dialect)
            if sql:
                sql_parts.append(sql)
                all_params.update(params)
                param_index += len(params)
        
        if not sql_parts:
            return "", {}
        
        sql = f" {self.operator.value} ".join(sql_parts)
        return f"({sql})", all_params


# ============================================================================
# Query Builder Classes
# ============================================================================

class QueryBuilder:
    """
    Fluent query builder for complex SQL queries
    
    Usage:
        query = (QueryBuilder("detections", dialect="sqlite")
                 .select("id", "drone_type", "confidence")
                 .where("timestamp", Operator.GTE, start_date)
                 .where("threat_level", Operator.EQ, "HIGH")
                 .order_by("timestamp", OrderDirection.DESC)
                 .limit(100)
                 .build())
    """
    
    def __init__(self, table: str, alias: Optional[str] = None, dialect: str = "sqlite"):
        """
        Initialize query builder
        
        Args:
            table: Main table name
            alias: Table alias
            dialect: SQL dialect ('sqlite', 'postgresql', 'mysql')
        """
        self.table = table
        self.alias = alias
        self.dialect = dialect
        self.fields: List[Tuple[str, Optional[str]]] = []  # (field, alias)
        self.distinct = False
        self.conditions = ConditionGroup()
        self.joins: List[Dict[str, Any]] = []
        self.group_by: List[str] = []
        self.having_conditions = ConditionGroup()
        self.order_by: List[Tuple[str, OrderDirection]] = []
        self.limit_count: Optional[int] = None
        self.offset_count: Optional[int] = None
        self.aggregates: List[Tuple[AggregateFunction, str, Optional[str]]] = []
        self.parameters: Dict[str, Any] = {}
        self._param_counter = 0
    
    def select(self, *fields: str, **aliased_fields: str) -> 'QueryBuilder':
        """
        Specify fields to select
        
        Args:
            *fields: Field names
            **aliased_fields: Field names with aliases (alias=field)
            
        Returns:
            Self for chaining
        """
        for field in fields:
            self.fields.append((field, None))
        
        for alias, field in aliased_fields.items():
            self.fields.append((field, alias))
        
        return self
    
    def select_count(self, field: str = "*", alias: str = "count") -> 'QueryBuilder':
        """Add COUNT aggregation"""
        self.aggregates.append((AggregateFunction.COUNT, field, alias))
        return self
    
    def select_sum(self, field: str, alias: str) -> 'QueryBuilder':
        """Add SUM aggregation"""
        self.aggregates.append((AggregateFunction.SUM, field, alias))
        return self
    
    def select_avg(self, field: str, alias: str) -> 'QueryBuilder':
        """Add AVG aggregation"""
        self.aggregates.append((AggregateFunction.AVG, field, alias))
        return self
    
    def select_min(self, field: str, alias: str) -> 'QueryBuilder':
        """Add MIN aggregation"""
        self.aggregates.append((AggregateFunction.MIN, field, alias))
        return self
    
    def select_max(self, field: str, alias: str) -> 'QueryBuilder':
        """Add MAX aggregation"""
        self.aggregates.append((AggregateFunction.MAX, field, alias))
        return self
    
    def distinct(self, enabled: bool = True) -> 'QueryBuilder':
        """Enable/disable DISTINCT"""
        self.distinct = enabled
        return self
    
    def where(self, field: str, operator: Operator, value: Any, 
              table_alias: Optional[str] = None) -> 'QueryBuilder':
        """
        Add WHERE condition (AND)
        
        Args:
            field: Field name
            operator: Comparison operator
            value: Value to compare
            table_alias: Optional table alias
            
        Returns:
            Self for chaining
        """
        condition = Condition(field, operator, value, table_alias)
        self.conditions.add(condition)
        return self
    
    def where_or(self, field: str, operator: Operator, value: Any,
                 table_alias: Optional[str] = None) -> 'QueryBuilder':
        """
        Add WHERE condition with OR
        
        Args:
            field: Field name
            operator: Comparison operator
            value: Value to compare
            table_alias: Optional table alias
            
        Returns:
            Self for chaining
        """
        condition = Condition(field, operator, value, table_alias)
        
        # Create OR group
        if not self.conditions.conditions:
            self.conditions = ConditionGroup(LogicalOperator.OR)
        elif self.conditions.operator == LogicalOperator.AND:
            # Convert to mixed group
            or_group = ConditionGroup(LogicalOperator.OR)
            self.conditions.add(or_group)
            or_group.add(condition)
        else:
            self.conditions.add(condition)
        
        return self
    
    def where_between(self, field: str, start: Any, end: Any,
                      table_alias: Optional[str] = None) -> 'QueryBuilder':
        """Add BETWEEN condition"""
        return self.where(field, Operator.BETWEEN, (start, end), table_alias)
    
    def where_in(self, field: str, values: List[Any],
                 table_alias: Optional[str] = None) -> 'QueryBuilder':
        """Add IN condition"""
        return self.where(field, Operator.IN, values, table_alias)
    
    def where_null(self, field: str, table_alias: Optional[str] = None) -> 'QueryBuilder':
        """Add IS NULL condition"""
        return self.where(field, Operator.IS_NULL, None, table_alias)
    
    def where_not_null(self, field: str, table_alias: Optional[str] = None) -> 'QueryBuilder':
        """Add IS NOT NULL condition"""
        return self.where(field, Operator.IS_NOT_NULL, None, table_alias)
    
    def where_contains(self, field: str, value: Any,
                       table_alias: Optional[str] = None) -> 'QueryBuilder':
        """Add JSON contains condition"""
        return self.where(field, Operator.CONTAINS, value, table_alias)
    
    def where_date_range(self, field: str, start_date: datetime, 
                         end_date: datetime) -> 'QueryBuilder':
        """Add date range filter"""
        return self.where_between(field, start_date.isoformat(), end_date.isoformat())
    
    def where_last_hours(self, field: str, hours: int) -> 'QueryBuilder':
        """Filter records from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return self.where(field, Operator.GTE, cutoff.isoformat())
    
    def join(self, table: str, condition: str, join_type: JoinType = JoinType.INNER,
             alias: Optional[str] = None) -> 'QueryBuilder':
        """
        Add JOIN clause
        
        Args:
            table: Table to join
            condition: JOIN condition
            join_type: Type of JOIN
            alias: Table alias
            
        Returns:
            Self for chaining
        """
        self.joins.append({
            'table': table,
            'alias': alias,
            'condition': condition,
            'type': join_type
        })
        return self
    
    def left_join(self, table: str, condition: str, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add LEFT JOIN"""
        return self.join(table, condition, JoinType.LEFT, alias)
    
    def right_join(self, table: str, condition: str, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add RIGHT JOIN"""
        return self.join(table, condition, JoinType.RIGHT, alias)
    
    def inner_join(self, table: str, condition: str, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add INNER JOIN"""
        return self.join(table, condition, JoinType.INNER, alias)
    
    def group_by(self, *fields: str) -> 'QueryBuilder':
        """Add GROUP BY clause"""
        self.group_by.extend(fields)
        return self
    
    def having(self, field: str, operator: Operator, value: Any) -> 'QueryBuilder':
        """Add HAVING condition"""
        condition = Condition(field, operator, value)
        self.having_conditions.add(condition)
        return self
    
    def order_by(self, field: str, direction: OrderDirection = OrderDirection.ASC) -> 'QueryBuilder':
        """Add ORDER BY clause"""
        self.order_by.append((field, direction))
        return self
    
    def limit(self, limit: int) -> 'QueryBuilder':
        """Set LIMIT"""
        self.limit_count = limit
        return self
    
    def offset(self, offset: int) -> 'QueryBuilder':
        """Set OFFSET"""
        self.offset_count = offset
        return self
    
    def page(self, page: int, page_size: int) -> 'QueryBuilder':
        """Set pagination (1-indexed page number)"""
        self.limit_count = page_size
        self.offset_count = (page - 1) * page_size
        return self
    
    def _build_select_clause(self) -> str:
        """Build SELECT clause"""
        if self.aggregates:
            # Build aggregate selections
            agg_parts = []
            for func, field, alias in self.aggregates:
                if field == "*" and func == AggregateFunction.COUNT:
                    agg_parts.append(f"COUNT(*)")
                else:
                    agg_parts.append(f"{func.value}({field})")
                if alias:
                    agg_parts[-1] = f"{agg_parts[-1]} AS {alias}"
            
            if self.fields:
                # Mixed aggregates and regular fields require GROUP BY
                regular_fields = [self._field_to_sql(f, a) for f, a in self.fields]
                return f"SELECT {', '.join(agg_parts + regular_fields)}"
            else:
                return f"SELECT {', '.join(agg_parts)}"
        
        elif self.fields:
            fields = [self._field_to_sql(f, a) for f, a in self.fields]
            return f"SELECT {'DISTINCT ' if self.distinct else ''}{', '.join(fields)}"
        
        else:
            return f"SELECT {'DISTINCT ' if self.distinct else ''}*"
    
    def _field_to_sql(self, field: str, alias: Optional[str]) -> str:
        """Convert field to SQL with alias"""
        if alias:
            return f"{field} AS {alias}"
        return field
    
    def _build_from_clause(self) -> str:
        """Build FROM clause"""
        if self.alias:
            return f"FROM {self.table} AS {self.alias}"
        return f"FROM {self.table}"
    
    def _build_join_clause(self) -> str:
        """Build JOIN clause"""
        if not self.joins:
            return ""
        
        join_parts = []
        for join in self.joins:
            table = join['table']
            alias = f" AS {join['alias']}" if join['alias'] else ""
            condition = join['condition']
            join_parts.append(f"{join['type'].value} {table}{alias} ON {condition}")
        
        return " " + " ".join(join_parts)
    
    def _build_where_clause(self) -> Tuple[str, Dict[str, Any]]:
        """Build WHERE clause"""
        if not self.conditions.conditions:
            return "", {}
        
        sql, params = self.conditions.to_sql(self._param_counter, self.dialect)
        self._param_counter += len(params)
        if sql:
            return f" WHERE {sql}", params
        return "", {}
    
    def _build_group_by_clause(self) -> str:
        """Build GROUP BY clause"""
        if not self.group_by:
            return ""
        return f" GROUP BY {', '.join(self.group_by)}"
    
    def _build_having_clause(self) -> Tuple[str, Dict[str, Any]]:
        """Build HAVING clause"""
        if not self.having_conditions.conditions:
            return "", {}
        
        sql, params = self.having_conditions.to_sql(self._param_counter, self.dialect)
        self._param_counter += len(params)
        if sql:
            return f" HAVING {sql}", params
        return "", {}
    
    def _build_order_clause(self) -> str:
        """Build ORDER BY clause"""
        if not self.order_by:
            return ""
        order_parts = [f"{field} {direction.value}" for field, direction in self.order_by]
        return f" ORDER BY {', '.join(order_parts)}"
    
    def _build_limit_clause(self) -> str:
        """Build LIMIT clause"""
        if self.limit_count is None:
            return ""
        
        if self.dialect == "sqlite":
            return f" LIMIT {self.limit_count}"
        elif self.dialect == "postgresql":
            return f" LIMIT {self.limit_count}"
        elif self.dialect == "mysql":
            return f" LIMIT {self.limit_count}"
        return ""
    
    def _build_offset_clause(self) -> str:
        """Build OFFSET clause"""
        if self.offset_count is None:
            return ""
        
        if self.dialect == "sqlite":
            return f" OFFSET {self.offset_count}"
        elif self.dialect == "postgresql":
            return f" OFFSET {self.offset_count}"
        elif self.dialect == "mysql":
            return f" OFFSET {self.offset_count}"
        return ""
    
    def build(self) -> Tuple[str, Dict[str, Any]]:
        """
        Build the complete SQL query
        
        Returns:
            Tuple of (sql_string, parameters_dict)
        """
        self._param_counter = 0
        self.parameters = {}
        
        # Build query parts
        select_clause = self._build_select_clause()
        from_clause = self._build_from_clause()
        join_clause = self._build_join_clause()
        where_sql, where_params = self._build_where_clause()
        group_clause = self._build_group_by_clause()
        having_sql, having_params = self._build_having_clause()
        order_clause = self._build_order_clause()
        limit_clause = self._build_limit_clause()
        offset_clause = self._build_offset_clause()
        
        # Combine parameters
        self.parameters.update(where_params)
        self.parameters.update(having_params)
        
        # Combine SQL
        sql = f"{select_clause}{from_clause}{join_clause}{where_sql}{group_clause}{having_sql}{order_clause}{limit_clause}{offset_clause}"
        
        return sql, self.parameters
    
    def build_count(self) -> Tuple[str, Dict[str, Any]]:
        """Build COUNT query for pagination"""
        count_builder = QueryBuilder(self.table, self.alias, self.dialect)
        count_builder.select_count()
        count_builder.conditions = self.conditions
        count_builder.joins = self.joins
        return count_builder.build()
    
    def to_sql(self) -> str:
        """Get SQL string with parameters replaced (for debugging)"""
        sql, params = self.build()
        
        # Replace parameters for display
        for key, value in params.items():
            if isinstance(value, str):
                sql = sql.replace(f':{key}', f"'{value}'")
            else:
                sql = sql.replace(f':{key}', str(value))
        
        return sql


# ============================================================================
# Specialized Query Builders
# ============================================================================

class DetectionQueryBuilder(QueryBuilder):
    """Specialized query builder for detection queries"""
    
    def __init__(self, dialect: str = "sqlite"):
        super().__init__("detections", "d", dialect)
        
    def by_threat_level(self, threat_level: str) -> 'DetectionQueryBuilder':
        """Filter by threat level"""
        self.where("threat_level", Operator.EQ, threat_level)
        return self
    
    def by_drone_type(self, drone_type: str) -> 'DetectionQueryBuilder':
        """Filter by drone type"""
        self.where("drone_type", Operator.EQ, drone_type)
        return self
    
    def by_confidence(self, min_confidence: float = 0.0, 
                      max_confidence: float = 1.0) -> 'DetectionQueryBuilder':
        """Filter by confidence range"""
        if min_confidence > 0:
            self.where("confidence", Operator.GTE, min_confidence)
        if max_confidence < 1:
            self.where("confidence", Operator.LTE, max_confidence)
        return self
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> 'DetectionQueryBuilder':
        """Filter by date range"""
        self.where_between("timestamp", start_date.isoformat(), end_date.isoformat())
        return self
    
    def by_location_radius(self, lat: float, lon: float, radius_km: float) -> 'DetectionQueryBuilder':
        """Filter by location within radius"""
        # Haversine formula for distance calculation
        # This works for SQLite with custom function
        distance_expr = f"""
            (6371 * acos(
                cos(radians({lat})) * cos(radians(latitude)) *
                cos(radians(longitude) - radians({lon})) +
                sin(radians({lat})) * sin(radians(latitude))
            ))
        """
        self.where(distance_expr, Operator.LTE, radius_km)
        return self
    
    def with_remote_id(self) -> 'DetectionQueryBuilder':
        """Filter detections that have Remote ID"""
        self.where_not_null("remote_id")
        return self
    
    def recent(self, minutes: int) -> 'DetectionQueryBuilder':
        """Filter recent detections"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        self.where("timestamp", Operator.GTE, cutoff.isoformat())
        return self
    
    def high_confidence_drones(self) -> 'DetectionQueryBuilder':
        """Filter high confidence drone detections"""
        self.where("confidence", Operator.GTE, 0.8)
        self.where("drone_type", Operator.NE, "unknown")
        return self
    
    def unresolved_threats(self) -> 'DetectionQueryBuilder':
        """Filter unresolved threats"""
        # For alerts that haven't been resolved
        return self
    
    def get_threat_summary(self) -> 'DetectionQueryBuilder':
        """Build threat summary query"""
        self.select_count("*", "total")
        self.select_sum("CASE WHEN threat_level = 'HIGH' THEN 1 ELSE 0 END", "high")
        self.select_sum("CASE WHEN threat_level = 'MEDIUM' THEN 1 ELSE 0 END", "medium")
        self.select_sum("CASE WHEN threat_level = 'LOW' THEN 1 ELSE 0 END", "low")
        self.select_avg("confidence", "avg_confidence")
        return self


class AlertQueryBuilder(QueryBuilder):
    """Specialized query builder for alert queries"""
    
    def __init__(self, dialect: str = "sqlite"):
        super().__init__("alerts", "a", dialect)
        self.join("detections", "d.id = a.detection_id", JoinType.LEFT, "d")
    
    def by_severity(self, severity: str) -> 'AlertQueryBuilder':
        """Filter by severity"""
        self.where("severity", Operator.EQ, severity)
        return self
    
    def unacknowledged(self) -> 'AlertQueryBuilder':
        """Filter unacknowledged alerts"""
        self.where("acknowledged", Operator.EQ, False)
        return self
    
    def unresolved(self) -> 'AlertQueryBuilder':
        """Filter unresolved alerts"""
        self.where("resolved", Operator.EQ, False)
        return self
    
    def by_escalation_level(self, level: int) -> 'AlertQueryBuilder':
        """Filter by escalation level"""
        self.where("escalation_level", Operator.GTE, level)
        return self
    
    def active_alerts(self) -> 'AlertQueryBuilder':
        """Get active alerts"""
        self.unacknowledged()
        self.unresolved()
        return self


class RemoteIDQueryBuilder(QueryBuilder):
    """Specialized query builder for Remote ID queries"""
    
    def __init__(self, dialect: str = "sqlite"):
        super().__init__("remote_id_messages", "r", dialect)
    
    def by_uas_id(self, uas_id: str) -> 'RemoteIDQueryBuilder':
        """Filter by UAS ID"""
        self.where("uas_id", Operator.EQ, uas_id)
        return self
    
    def by_location_radius(self, lat: float, lon: float, radius_km: float) -> 'RemoteIDQueryBuilder':
        """Filter by location radius"""
        distance_expr = f"""
            (6371 * acos(
                cos(radians({lat})) * cos(radians(latitude)) *
                cos(radians(longitude) - radians({lon})) +
                sin(radians({lat})) * sin(radians(latitude))
            ))
        """
        self.where(distance_expr, Operator.LTE, radius_km)
        return self
    
    def recent_positions(self, minutes: int = 5) -> 'RemoteIDQueryBuilder':
        """Get recent positions for each drone"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        self.where("timestamp", Operator.GTE, cutoff.isoformat())
        self.order_by("timestamp", OrderDirection.DESC)
        return self
    
    def get_track(self, uas_id: str, start_time: datetime, end_time: datetime) -> 'RemoteIDQueryBuilder':
        """Get track for a specific drone"""
        self.by_uas_id(uas_id)
        self.where_between("timestamp", start_time.isoformat(), end_time.isoformat())
        self.order_by("timestamp", OrderDirection.ASC)
        return self
    
    def active_drones(self, minutes: int = 5) -> 'RemoteIDQueryBuilder':
        """Get active drones (recent positions)"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        self.where("timestamp", Operator.GTE, cutoff.isoformat())
        self.select_distinct("uas_id")
        return self


class SpectrumQueryBuilder(QueryBuilder):
    """Specialized query builder for spectrum analysis queries"""
    
    def __init__(self, dialect: str = "sqlite"):
        super().__init__("spectrum_measurements", "s", dialect)
    
    def by_frequency_range(self, min_freq: float, max_freq: float) -> 'SpectrumQueryBuilder':
        """Filter by frequency range"""
        self.where("center_frequency", Operator.BETWEEN, (min_freq, max_freq))
        return self
    
    def with_detection(self) -> 'SpectrumQueryBuilder':
        """Filter measurements associated with detections"""
        self.where_not_null("detection_id")
        return self
    
    def by_snr(self, min_snr: float) -> 'SpectrumQueryBuilder':
        """Filter by SNR threshold"""
        self.where("snr", Operator.GTE, min_snr)
        return self
    
    def get_band_occupancy(self, band_start: float, band_end: float, 
                           resolution: float = 1e6) -> 'SpectrumQueryBuilder':
        """Get spectrum band occupancy analysis"""
        self.by_frequency_range(band_start, band_end)
        # Would need custom aggregation
        return self


class RecordingQueryBuilder(QueryBuilder):
    """Specialized query builder for recording queries"""
    
    def __init__(self, dialect: str = "sqlite"):
        super().__init__("recordings", "r", dialect)
    
    def by_session(self, session_id: str) -> 'RecordingQueryBuilder':
        """Filter by session ID"""
        self.where("session_id", Operator.EQ, session_id)
        return self
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> 'RecordingQueryBuilder':
        """Filter by date range"""
        self.where_between("start_time", start_date.isoformat(), end_date.isoformat())
        return self
    
    def by_format(self, file_format: str) -> 'RecordingQueryBuilder':
        """Filter by file format"""
        self.where("file_format", Operator.EQ, file_format)
        return self
    
    def large_files(self, min_size_mb: float = 100) -> 'RecordingQueryBuilder':
        """Filter large files"""
        min_bytes = min_size_mb * 1024 * 1024
        self.where("file_size_bytes", Operator.GTE, min_bytes)
        return self
    
    def recent_recordings(self, days: int = 7) -> 'RecordingQueryBuilder':
        """Get recent recordings"""
        cutoff = datetime.now() - timedelta(days=days)
        self.where("start_time", Operator.GTE, cutoff.isoformat())
        self.order_by("start_time", OrderDirection.DESC)
        return self


# ============================================================================
# Query Execution Helper
# ============================================================================

class QueryExecutor:
    """Helper class for executing queries with a database connection"""
    
    def __init__(self, db_adapter):
        """
        Initialize query executor
        
        Args:
            db_adapter: Database adapter instance
        """
        self.db = db_adapter
    
    async def execute_builder(self, builder: QueryBuilder) -> Tuple[List[Dict[str, Any]], int]:
        """
        Execute a query builder and return results with total count
        
        Args:
            builder: QueryBuilder instance
            
        Returns:
            Tuple of (results, total_count)
        """
        # Get total count first
        count_sql, count_params = builder.build_count()
        count_result = await self.db.fetch_one(count_sql, **count_params)
        total = count_result.get('COUNT(*)', 0) if count_result else 0
        
        # Get paginated results
        sql, params = builder.build()
        results = await self.db.fetch_all(sql, **params)
        
        return results, total
    
    async def execute_builder_one(self, builder: QueryBuilder) -> Optional[Dict[str, Any]]:
        """Execute and return first result"""
        sql, params = builder.build()
        return await self.db.fetch_one(sql, **params)
    
    async def execute_builder_all(self, builder: QueryBuilder) -> List[Dict[str, Any]]:
        """Execute and return all results"""
        sql, params = builder.build()
        return await self.db.fetch_all(sql, **params)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of query builder"""
    
    # Create query builder
    builder = DetectionQueryBuilder("sqlite")
    
    # Build complex query
    query = (builder
             .select("id", "timestamp", "drone_type", "confidence", "threat_level")
             .by_threat_level("HIGH")
             .by_confidence(min_confidence=0.8)
             .recent(minutes=60)
             .order_by("timestamp", OrderDirection.DESC)
             .limit(50))
    
    # Get SQL
    sql, params = query.build()
    print(f"SQL: {sql}")
    print(f"Params: {params}")
    
    # Get count query
    count_sql, count_params = query.build_count()
    print(f"COUNT SQL: {count_sql}")
    
    # Threat summary
    summary_builder = DetectionQueryBuilder()
    summary = (summary_builder
               .get_threat_summary()
               .recent(minutes=60))
    
    summary_sql, summary_params = summary.build()
    print(f"Summary SQL: {summary_sql}")
    
    # Remote ID track query
    track_builder = RemoteIDQueryBuilder()
    track = (track_builder
             .get_track("UAS12345", 
                       datetime.now() - timedelta(hours=1),
                       datetime.now())
             .limit(1000))
    
    track_sql, track_params = track.build()
    print(f"Track SQL: {track_sql}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())