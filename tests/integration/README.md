drone-detector/tests/integration/README.md - Integration Tests Documentation

markdown
# Integration Tests Directory

This directory contains integration tests for the Drone Detection System. Integration tests verify that different components work together correctly, testing real interactions between modules, databases, APIs, messaging systems, and external services.

## Directory Structure
tests/integration/
├── README.md # This file
├── init.py # Package initialization and test utilities
├── conftest.py # pytest configuration
├── pipeline/ # End-to-end pipeline tests
│ ├── test_replay_pipeline.py # IQ replay pipeline tests
│ ├── test_detection_pipeline.py # Detection pipeline tests
│ └── test_remote_id_pipeline.py # Remote ID pipeline tests
├── api/ # API endpoint tests
│ ├── test_system_api.py # System API tests
│ ├── test_detection_api.py # Detection API tests
│ ├── test_map_api.py # Map API tests
│ └── test_websocket_api.py # WebSocket API tests
├── storage/ # Database integration tests
│ ├── test_sqlite_storage.py # SQLite storage tests
│ └── test_postgres_storage.py # PostgreSQL storage tests
├── messaging/ # Message queue tests
│ ├── test_event_flow.py # Event bus flow tests
│ └── test_websocket_broadcast.py # WebSocket broadcast tests
└── data/ # Test data files
├── iq_samples/ # IQ test files
├── config/ # Test configuration
└── expected/ # Expected results

text

## Test Categories

### Pipeline Tests (`pipeline/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_replay_pipeline.py` | Tests IQ replay pipeline | File loading, playback, real-time processing |
| `test_detection_pipeline.py` | Tests detection pipeline | Signal processing, classification, alerting |
| `test_remote_id_pipeline.py` | Tests Remote ID pipeline | BLE/WiFi decoding, tracking, geofencing |

### API Tests (`api/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_system_api.py` | Tests system endpoints | Health, metrics, configuration |
| `test_detection_api.py` | Tests detection endpoints | CRUD operations, filtering, export |
| `test_map_api.py` | Tests map endpoints | GeoJSON, geofencing, heatmaps |
| `test_websocket_api.py` | Tests WebSocket endpoints | Connections, broadcasting, commands |

### Storage Tests (`storage/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_sqlite_storage.py` | Tests SQLite storage | CRUD, transactions, concurrency |
| `test_postgres_storage.py` | Tests PostgreSQL storage | Connection pooling, performance, integrity |

### Messaging Tests (`messaging/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_event_flow.py` | Tests event bus | Publishing, subscription, event routing |
| `test_websocket_broadcast.py` | Tests WebSocket broadcast | Real-time distribution, channels, performance |

## Prerequisites

### System Requirements

```bash
# Required system packages
sudo apt-get install -y python3-dev postgresql postgresql-contrib

# For macOS
brew install postgresql

# For Windows (using WSL2 recommended)
Python Dependencies
bash
# Install test dependencies
pip install -r requirements-dev.txt

# Additional integration test dependencies
pip install pytest-asyncio pytest-timeout pytest-xdist websockets
Database Setup
SQLite (Default)
bash
# SQLite is included with Python, no additional setup required
# Test database will be created automatically in /tmp
PostgreSQL (Optional)
bash
# Start PostgreSQL service
sudo systemctl start postgresql

# Create test database
sudo -u postgres createdb drone_test_integration
sudo -u postgres psql -c "CREATE USER test_user WITH PASSWORD 'test_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE drone_test_integration TO test_user;"

# Set environment variables
export POSTGRES_TEST=true
export TEST_POSTGRES_HOST=localhost
export TEST_POSTGRES_PORT=5432
export TEST_POSTGRES_DB=drone_test_integration
export TEST_POSTGRES_USER=test_user
export TEST_POSTGRES_PASSWORD=test_password
Running Integration Tests
Basic Test Execution
bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run specific test category
python -m pytest tests/integration/pipeline/ -v
python -m pytest tests/integration/api/ -v
python -m pytest tests/integration/storage/ -v
python -m pytest tests/integration/messaging/ -v

# Run specific test file
python -m pytest tests/integration/pipeline/test_detection_pipeline.py -v

# Run specific test class
python -m pytest tests/integration/pipeline/test_detection_pipeline.py::TestDetectionPipeline -v

# Run specific test method
python -m pytest tests/integration/pipeline/test_detection_pipeline.py::TestDetectionPipeline::test_full_detection_cycle -v
With Coverage
bash
# Run with coverage report
python -m pytest tests/integration/ --cov=. --cov-report=html

# Run specific module with coverage
python -m pytest tests/integration/pipeline/test_remote_id_pipeline.py \
    --cov=app.pipelines \
    --cov-report=term

# Generate XML coverage report for CI
python -m pytest tests/integration/ --cov=. --cov-report=xml
Parallel Execution
bash
# Run tests in parallel (requires pytest-xdist)
python -m pytest tests/integration/ -n auto

# Run with specific number of workers
python -m pytest tests/integration/ -n 4

# Distribute by test file
python -m pytest tests/integration/ -n 4 --dist=loadfile
Environment-Specific Testing
bash
# Run with SQLite (default)
python -m pytest tests/integration/storage/ -v

# Run with PostgreSQL
export POSTGRES_TEST=true
python -m pytest tests/integration/storage/test_postgres_storage.py -v

# Run with mock services
export MOCK_EXTERNAL_SERVICES=true
python -m pytest tests/integration/api/test_websocket_api.py -v
Docker-Based Testing
bash
# Using docker-compose for test environment
docker-compose -f docker-compose.test.yml up -d

# Run tests against containerized services
python -m pytest tests/integration/ -v --docker

# Stop test containers
docker-compose -f docker-compose.test.yml down
Test Configuration
Environment Variables
Variable	Description	Default
TESTING	Enable test mode	true
POSTGRES_TEST	Enable PostgreSQL tests	false
TEST_POSTGRES_HOST	PostgreSQL host	localhost
TEST_POSTGRES_PORT	PostgreSQL port	5432
TEST_POSTGRES_DB	Test database name	drone_test
TEST_POSTGRES_USER	Database user	test_user
TEST_POSTGRES_PASSWORD	Database password	test_password
MOCK_EXTERNAL_SERVICES	Mock external APIs	false
TEST_API_PORT	API server port	8888
TEST_WS_PORT	WebSocket port	8889
pytest Configuration (conftest.py)
python
# tests/integration/conftest.py
import pytest
import asyncio
from pathlib import Path

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def api_client():
    """Create API client for testing"""
    from tests.integration import APIFixture
    fixture = APIFixture()
    await fixture.start()
    yield fixture
    await fixture.stop()

@pytest.fixture(scope="session")
async def websocket_client():
    """Create WebSocket client for testing"""
    from tests.integration import WebSocketFixture
    fixture = WebSocketFixture()
    await fixture.start()
    yield fixture
    await fixture.stop()

@pytest.fixture(scope="function")
async def db_cleanup():
    """Clean database between tests"""
    from tests.integration import DatabaseFixture
    fixture = DatabaseFixture()
    await fixture.start()
    yield fixture
    await fixture.clear()
    await fixture.stop()

# Markers for test categorization
pytest.mark.pipeline = pytest.mark.pipeline
pytest.mark.api = pytest.mark.api
pytest.mark.storage = pytest.mark.storage
pytest.mark.messaging = pytest.mark.messaging
pytest.mark.slow = pytest.mark.slow
pytest.mark.postgres = pytest.mark.postgres
Writing Integration Tests
Test Structure Template
python
import pytest
import asyncio
from tests.integration import IntegrationTestCase, setup_integration_services

class TestMyIntegration(IntegrationTestCase):
    """Integration tests for my component"""
    
    @classmethod
    async def asyncSetUpClass(cls):
        """Set up test class - called once"""
        cls.services = await setup_integration_services()
    
    @classmethod
    async def asyncTearDownClass(cls):
        """Clean up test class"""
        await cls.services.stop_all()
    
    async def asyncSetUp(self):
        """Set up test method - called before each test"""
        await self.services.get('database').clear()
    
    async def test_full_workflow(self):
        """Test complete workflow"""
        # Arrange
        test_data = self.test_data.create_test_detection_batch(5)
        
        # Act
        for detection in test_data:
            await self.services.get('api').post("/detections", json=detection)
        
        # Assert
        response = await self.services.get('api').get("/detections")
        data = response.json()
        assert len(data['items']) >= 5
Test Patterns
API Test Pattern
python
async def test_create_and_retrieve_detection():
    """Test detection creation and retrieval"""
    # Create
    detection = test_data.create_test_detection()
    post_response = await api_client.post("/detections", json=detection)
    assert post_response.status_code == 201
    
    # Retrieve
    detection_id = post_response.json()['id']
    get_response = await api_client.get(f"/detections/{detection_id}")
    assert get_response.status_code == 200
    assert get_response.json()['id'] == detection_id
Database Test Pattern
python
async def test_database_transaction():
    """Test database transaction rollback"""
    async with db.transaction():
        await db.execute("INSERT INTO detections VALUES ($1, $2)", "det_001", "DJI Mavic 3")
        raise Exception("Trigger rollback")
    
    # Verify rollback
    result = await db.fetch_one("SELECT * FROM detections WHERE id = 'det_001'")
    assert result is None
WebSocket Test Pattern
python
async def test_websocket_broadcast():
    """Test WebSocket message broadcast"""
    client = await websocket_client.connect()
    
    # Subscribe to channel
    await client.send({"type": "subscribe", "channels": ["detections"]})
    
    # Broadcast message
    await websocket_client.broadcast_detection(test_detection)
    
    # Verify receipt
    message = await client.receive(timeout=5.0)
    assert message['type'] == 'detection'
Test Data Management
Test Data Directory Structure
text
tests/integration/data/
├── iq_samples/
│   ├── dji_mavic_sample.iq        # DJI Mavic IQ sample
│   ├── fpv_analog_sample.iq       # FPV analog sample
│   └── noise_sample.iq            # Background noise sample
├── config/
│   ├── test_config.yaml           # Test configuration
│   └── test_signatures.json       # Test drone signatures
├── expected/
│   ├── detection_expected.json    # Expected detection output
│   └── spectrum_expected.npy      # Expected spectrum data
└── fixtures/
    ├── database_fixture.sql       # Database test data
    └── redis_fixture.rdb          # Redis test data
Generating Test Data
python
from tests.integration import IntegrationTestDataGenerator

# Generate test detections
detections = IntegrationTestDataGenerator.create_test_detection_batch(100)

# Generate test alerts
alerts = IntegrationTestDataGenerator.create_test_alert_batch(50)

# Generate test Remote ID messages
remote_id_msgs = IntegrationTestDataGenerator.create_test_remote_id_batch(200)
Continuous Integration
GitHub Actions Workflow
yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * *'  # Daily run

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
        database: [sqlite, postgres]
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: drone_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    - name: Run integration tests
      env:
        POSTGRES_TEST: ${{ matrix.database == 'postgres' }}
        TEST_POSTGRES_HOST: localhost
        TEST_POSTGRES_USER: test_user
        TEST_POSTGRES_PASSWORD: test_password
      run: |
        python -m pytest tests/integration/ -v --cov=. --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: integration-tests
Troubleshooting
Common Issues
Issue	Cause	Solution
Connection refused	Services not started	Run setup_integration_services() first
Database locked	Concurrent access	Use connection pooling or sequential tests
Port already in use	Previous test left server running	Kill process or use different port
Timeout	Slow operation	Increase timeout or optimize test
Foreign key violation	Referenced data missing	Ensure proper test data order
Debugging Integration Tests
bash
# Run with debug output
python -m pytest tests/integration/ -v --capture=no

# Drop into debugger on failure
python -m pytest tests/integration/ --pdb

# Run single test with verbose logging
python -m pytest tests/integration/api/test_detection_api.py::test_create_detection -v -s --log-cli-level=DEBUG

# Use pytest-timeout to debug hanging tests
python -m pytest tests/integration/ --timeout=30 --timeout-method=thread
Test Isolation
python
# Use unique test identifiers to avoid conflicts
import uuid
import time

def generate_unique_id():
    return f"test_{uuid.uuid4().hex[:8]}_{int(time.time())}"

# Use temporary directories for file-based tests
import tempfile
from pathlib import Path

def get_temp_db_path():
    return Path(tempfile.mkdtemp()) / "test.db"
Performance Guidelines
Test Type	Expected Duration	Timeout
Pipeline tests	1-5 seconds	30 seconds
API tests	0.1-1 second	10 seconds
Storage tests	0.1-2 seconds	20 seconds
Messaging tests	0.5-3 seconds	30 seconds
Stress tests	5-30 seconds	120 seconds
Best Practices
Test Isolation: Each test should be independent and not rely on other tests

Clean State: Reset database and services between tests

Realistic Data: Use data that mimics production scenarios

Timeout Management: Set appropriate timeouts for async operations

Resource Cleanup: Always close connections and remove temporary files

Meaningful Assertions: Verify both success and failure cases

Logging: Use debug logging for troubleshooting failed tests

Parallel Safety: Ensure tests can run in parallel without conflicts
