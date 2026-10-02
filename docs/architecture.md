# Drone Detector System Architecture

## Overview

The Drone Detector is a comprehensive, production-grade system for detecting, identifying, and tracking drones using Software Defined Radio (SDR) technology. The system employs a modular, clean architecture with clear separation of concerns, domain-driven design, and support for multiple deployment scenarios.

## Architecture Principles

- **Clean Architecture**: Dependency inversion with business logic at the core
- **Domain-Driven Design**: Rich domain models encapsulating business rules
- **Hexagonal Architecture**: Ports and adapters for infrastructure isolation
- **Event-Driven**: Loose coupling through event propagation
- **Observability First**: Metrics, logs, and traces throughout
- **Security by Design**: Defense in depth, least privilege
- **Scalability**: Horizontal scaling for high-throughput scenarios

## High-Level Architecture
┌─────────────────────────────────────────────────────────────────────────────┐
│ External World │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ Web │ │ Mobile │ │ API │ │ MQTT │ │ Kafka │ │
│ │ Client │ │ Client │ │ Client │ │ Broker │ │ Stream │ │
│ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│ │ │ │ │ │ │
└───────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────┘
│ │ │ │ │
▼ ▼ ▼ ▼ ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Interface Layer (API) │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ FastAPI Application │ │
│ │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │ │
│ │ │ REST │ │WebSocket│ │ GraphQL │ │ gRPC │ │ Metrics │ │ │
│ │ │Endpoints│ │ Server │ │ Schema │ │ Server │ │Endpoint │ │ │
│ │ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ │ │
│ │ │ │ │ │ │ │ │
│ │ ┌────┴───────────┴───────────┴───────────┴───────────┴────┐ │ │
│ │ │ Middleware (Auth, CORS, Logging) │ │ │
│ │ └─────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Application Layer (Use Cases) │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ Pipeline │ │ Service │ │ Worker │ │ Scheduler│ │ Event │ │ │
│ │ │ Chain │ │ Layer │ │ Pool │ │ Tasks │ │ Handler │ │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│ │ │ │
│ │ Use Cases: │ │
│ │ • DetectDrone • TrackDrone • IdentifyDrone │ │
│ │ • ClassifySignal • GenerateAlert • RecordIQ │ │
│ │ • TrainModel • ExportData • ManageSystem │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Domain Layer (Core) │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Entities (Aggregates) │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ IQSignal │ │Detection │ │ Drone │ │ Spectrum │ │ Alert │ │ │
│ │ │ │ │ Event │ │Signature │ │ Profile │ │ │ │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│ │ │ │
│ │ Value Objects │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │Frequency │ │Position │ │ThreatLevel│ │Confidence│ │TimeWindow│ │ │
│ │ │ Band │ │ │ │ │ │ Score │ │ │ │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│ │ │ │
│ │ Domain Services │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ Signal │ │ Threat │ │ Pattern │ │ Remote │ │ TDOA │ │ │
│ │ │Processor │ │Assessment│ │ Matching │ │ID Decoder│ │Engine │ │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│ │ │ │
│ │ Policies │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ Alert │ │Frequency │ │ Retention│ │ Privacy │ │ Rate │ │ │
│ │ │ Policies │ │Allocation│ │ Policies │ │ Policies │ │Limiting │ │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Infrastructure Layer (Adapters) │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Hardware │ │ Storage │ │ Messaging │ │ External │ │
│ │ Adapters │ │ Adapters │ │ Adapters │ │ Services │ │
│ │ │ │ │ │ │ │ │ │
│ │ • HackRF │ │ • PostgreSQL│ │ • Redis │ │ • ADS-B │ │
│ │ • RTL-SDR │ │ • Timescale │ │ • RabbitMQ │ │ • FlightRadar│ │
│ │ • Pluto │ │ • MinIO │ │ • Kafka │ │ • Notify │ │
│ │ • Mock │ │ • SQLite │ │ • WebSocket │ │ • Geocoding │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Monitoring │ │ Cache │ │ Queue │ │ Search │ │
│ │ │ │ │ │ │ │ │ │
│ │ • Prometheus│ │ • Redis │ │ • Celery │ │ • Elastic │ │
│ │ • Grafana │ │ • Memcached │ │ • RQ │ │ • Meilisearch│ │
│ │ • Loki │ │ │ │ │ │ │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

text

## Component Architecture

### 1. Domain Layer (Core Business Logic)

The domain layer is the heart of the system, containing all business rules and logic.

#### Entities

```python
# Core entities that have identity and lifecycles
class IQSignal:
    - data: complex64[]
    - sample_rate: float
    - center_frequency: float
    - timestamp: datetime
    - metadata: dict

class DetectionEvent:
    - id: UUID
    - drone_id: str
    - frequency: float
    - confidence: float
    - threat_level: ThreatLevel
    - position: Optional[Position]
    - timestamp: datetime

class DroneSignature:
    - drone_type: str
    - frequency_bands: List[FrequencyBand]
    - modulation_type: Modulation
    - signature_features: FeatureVector
    - confidence_threshold: float
Value Objects
python
# Immutable objects with no identity
class FrequencyBand:
    - start: float
    - end: float
    - center: float
    - bandwidth: float

class Position:
    - latitude: float
    - longitude: float
    - altitude: float
    - accuracy: float

class ThreatLevel(Enum):
    - NONE = 0
    - LOW = 1
    - MEDIUM = 2
    - HIGH = 3
    - CRITICAL = 4
Domain Services
python
# Stateless operations that don't belong to entities
class SignalProcessor:
    def calculate_psd(signal: IQSignal) -> PowerSpectrum
    def extract_features(signal: IQSignal) -> FeatureVector
    def detect_peaks(spectrum: PowerSpectrum) -> List[Peak]

class ThreatAssessment:
    def assess_threat(detection: DetectionEvent) -> ThreatLevel
    def calculate_risk_score(context: DetectionContext) -> float
2. Application Layer (Use Cases)
Orchestrates domain objects to accomplish user goals.

python
class DetectDroneUseCase:
    def execute(self, signal: IQSignal) -> DetectionEvent:
        1. Convert IQ to spectrum
        2. Extract signal features
        3. Match against drone signatures
        4. Assess threat level
        5. Store detection
        6. Publish events
        7. Return result

class TrackDroneUseCase:
    def execute(self, drone_id: str) -> Trajectory:
        1. Fetch historical detections
        2. Apply tracking algorithm (Kalman filter)
        3. Predict future position
        4. Return trajectory

class GenerateAlertUseCase:
    def execute(self, detection: DetectionEvent) -> Alert:
        1. Evaluate alert policies
        2. Determine severity
        3. Format notification
        4. Route to channels
        5. Log alert
3. Infrastructure Layer (Technical Details)
Adapters for external systems.

Hardware Adapters
python
class SDRAdapter(ABC):
    @abstractmethod
    def start_stream(self, config: HardwareConfig) -> AsyncIterator[IQSignal]
    
    @abstractmethod
    def stop_stream(self) -> None
    
    @abstractmethod
    def configure(self, config: HardwareConfig) -> None

class HackRFAdapter(SDRAdapter):
    # Implementation specific to HackRF One

class RTL_SDRAdapter(SDRAdapter):
    # Implementation for RTL-SDR dongles
Repository Pattern
python
class DetectionRepository(ABC):
    @abstractmethod
    async def save(self, detection: DetectionEvent) -> None
    
    @abstractmethod
    async def find_by_id(self, id: UUID) -> Optional[DetectionEvent]
    
    @abstractmethod
    async def find_by_time_range(
        self, start: datetime, end: datetime
    ) -> List[DetectionEvent]

class PostgresDetectionRepository(DetectionRepository):
    # PostgreSQL specific implementation
Data Flow Architecture
Real-Time Detection Pipeline
text
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  SDR    │────▶│  IQ     │────▶│  FFT    │────▶│  Peak   │────▶│ Pattern │
│Capture  │     │ Stream  │     │Compute  │     │Detect   │     │ Matching│
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └────┬────┘
                                                                      │
                                                                      ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Alert  │◀────│ Threat  │◀────│  ML     │◀────│ Classify│◀────│ Feature │
│ Generate│     │ Assess  │     │ Predict │     │  Drone  │     │ Extract │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
     │
     ▼
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Notify  │────▶│ Store   │────▶│  Push   │
│ Clients │     │   DB    │     │WebSocket│
└─────────┘     └─────────┘     └─────────┘
Batch Processing Pipeline
text
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Record  │────▶│  Upload  │────▶│ Process  │────▶│ Extract  │
│   IQ     │     │  to S3   │     │  Batch   │     │Features  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                         │
                                                         ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Update  │◀────│  Train   │◀────│  Label   │◀────│  Store   │
│  Model   │     │  Model   │     │  Data    │     │Features  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
Deployment Architecture
Single-Node Deployment
text
┌─────────────────────────────────────────────────────────────┐
│                         Single Host                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Docker/Podman                      │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │    │
│  │  │   API    │  │  Worker  │  │ Postgres │          │    │
│  │  │ Container│  │Container │  │ Container│          │    │
│  │  └──────────┘  └──────────┘  └──────────┘          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │    │
│  │  │  Redis   │  │  MinIO   │  │  Nginx   │          │    │
│  │  │ Container│  │Container │  │ Container│          │    │
│  │  └──────────┘  └──────────┘  └──────────┘          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    USB/SDR Hardware                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
Multi-Node (Kubernetes) Deployment
text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                               │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────┐   │
│  │      Node 1         │  │      Node 2         │  │    Node 3     │   │
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │  │ ┌───────────┐ │   │
│  │  │ API (x2)      │  │  │  │ API (x2)      │  │  │ │ Worker    │ │   │
│  │  ├───────────────┤  │  │  ├───────────────┤  │  │ │ (x4)      │ │   │
│  │  │ WebSocket     │  │  │  │ WebSocket     │  │  ├───────────┤ │   │
│  │  ├───────────────┤  │  │  ├───────────────┤  │  │ │ Beat      │ │   │
│  │  │ SDR Daemon    │  │  │  │ Prometheus    │  │  └───────────┘ │   │
│  │  └───────────────┘  │  │  ├───────────────┤  │                 │   │
│  │      USB/SDR        │  │  │ Grafana       │  │                 │   │
│  └─────────────────────┘  │  └───────────────┘  │                 │   │
│                           └─────────────────────┘                 │   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Shared Services                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │   │
│  │  │PostgreSQL│  │  Redis   │  │  MinIO   │  │   Kafka  │       │   │
│  │  │(Primary) │  │(Cluster) │  │ (HA)     │  │ (Stream) │       │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
Signal Processing Chain
IQ to Detection Flow
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Signal Processing Pipeline                        │
│                                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐          │
│  │   Raw    │     │   IQ     │     │   FFT    │     │   PSD    │          │
│  │ Samples  │────▶│  Data    │────▶│ Compute  │────▶│Compute   │          │
│  │ (I/Q)    │     │(Complex) │     │          │     │          │          │
│  └──────────┘     └──────────┘     └──────────┘     └────┬─────┘          │
│                                                            │                │
│                                                            ▼                │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐          │
│  │  Threat  │     │  Match   │     │ Feature  │     │  Peak    │          │
│  │  Level   │◀────│Database  │◀────│ Extract  │◀────│ Detect   │          │
│  └──────────┘     └──────────┘     └────┬─────┘     └──────────┘          │
│                                          │                                  │
│                                          ▼                                  │
│                                ┌──────────────────┐                        │
│                                │   ML Inference   │                        │
│                                │    Classifier    │                        │
│                                └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
Feature Extraction
text
Input: IQ Signal (complex samples)
    │
    ├──► Time Domain Features
    │    ├── RMS Power
    │    ├── Peak-to-Average Ratio
    │    ├── Kurtosis
    │    ├── Skewness
    │    └── Zero-Crossing Rate
    │
    ├──► Frequency Domain Features
    │    ├── Center Frequency
    │    ├── Bandwidth (99%)
    │    ├── Spectral Flatness
    │    ├── Spectral Centroid
    │    ├── Spectral Rolloff
    │    └── Peak Frequencies
    │
    ├──► Cyclostationary Features
    │    ├── Cyclic Autocorrelation
    │    ├── Spectral Coherence
    │    └── Cycle Frequencies
    │
    └──► Statistical Features
         ├── Mean, Variance
         ├── Higher-order moments
         ├── Entropy
         └── Correlation coefficients

Output: Feature Vector (128 dimensions)
Security Architecture
Defense in Depth
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Security Layers                                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                        External Perimeter                          │    │
│  │  • API Gateway / Load Balancer                                     │    │
│  │  • WAF (Web Application Firewall)                                  │    │
│  │  • DDoS Protection                                                 │    │
│  │  • Rate Limiting                                                   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                         Network Layer                              │    │
│  │  • TLS 1.3 for all communications                                  │    │
│  │  • Certificate validation                                          │    │
│  │  • Private network isolation                                       │    │
│  │  • Network policies (Kubernetes)                                   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                        Application Layer                           │    │
│  │  • JWT/OAuth2 authentication                                       │    │
│  │  • RBAC authorization                                              │    │
│  │  • Input validation                                                │    │
│  │  • SQL injection prevention                                        │    │
│  │  • XSS protection                                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                           Data Layer                               │    │
│  │  • Encryption at rest (AES-256)                                    │    │
│  │  • Encryption in transit (TLS)                                     │    │
│  │  • Database encryption (TDE)                                       │    │
│  │  • Key rotation                                                    │    │
│  │  • Audit logging                                                   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                       Identity & Access                            │    │
│  │  • Multi-factor authentication                                     │    │
│  │  • SSO integration (SAML/OIDC)                                     │    │
│  │  • Service accounts                                                │    │
│  │  • Secrets management (Vault)                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
Technology Stack
Core Technologies
Layer	Technology	Purpose
Language	Python 3.11+	Primary development language
Web Framework	FastAPI	REST API with OpenAPI docs
Async	asyncio, AnyIO	Concurrent operations
Signal Processing	NumPy, SciPy, FFTW	DSP operations
ML/DL	TensorFlow, PyTorch, scikit-learn	Classification
Type Safety	Pydantic, mypy	Data validation
Infrastructure
Component	Technology	Purpose
Database	PostgreSQL	Primary storage
Time-Series	TimescaleDB	Spectrum analytics
Cache	Redis	Session, rate limiting
Queue	Celery/RQ	Background tasks
Object Storage	MinIO/S3	IQ recordings
Logging	Loki + Vector	Log aggregation
Metrics	Prometheus + Grafana	Monitoring
Tracing	Jaeger	Distributed tracing
Deployment
Component	Technology	Purpose
Container	Docker	Application packaging
Orchestration	Kubernetes	Production deployment
CI/CD	GitHub Actions	Automation
IaC	Terraform	Infrastructure provisioning
Service Mesh	Istio (optional)	Advanced networking
Scalability Patterns
Horizontal Scaling
yaml
# API Servers - Stateless, can scale horizontally
api:
  replicas: 3-10 (HPA based on CPU/Memory)

# Workers - Process background tasks
worker:
  replicas: 5-20 (based on queue length)

# WebSocket - Stateful, need session affinity
websocket:
  replicas: 2-5 (with sticky sessions)

# Database - Read replicas for queries
postgres:
  primary: 1
  read_replicas: 2-3
Database Scaling
text
┌─────────────────────────────────────────────────────────────┐
│                    Database Architecture                     │
│                                                              │
│  ┌──────────────┐                                          │
│  │   Primary    │                                          │
│  │ (Write/Read) │                                          │
│  └──────┬───────┘                                          │
│         │                                                   │
│         │ Replication                                       │
│         ▼                                                   │
│  ┌──────────────┐     ┌──────────────┐                    │
│  │   Replica 1  │     │   Replica 2  │                    │
│  │   (Read)     │     │   (Read)     │                    │
│  └──────────────┘     └──────────────┘                    │
│                                                              │
│  Partitioning:                                              │
│  • detections_2024_01, detections_2024_02, ...            │
│  • Time-based partitioning for spectrum data               │
│                                                              │
│  Sharding:                                                  │
│  • By drone_id hash (future)                               │
│  • Geographic sharding (multi-region)                      │
└─────────────────────────────────────────────────────────────┘
Observability
Three Pillars
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Observability                                     │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │     Metrics      │  │      Logs        │  │     Traces       │         │
│  │                  │  │                  │  │                  │         │
│  │ • Request rate   │  │ • Application    │  │ • Request flow   │         │
│  │ • Error rate     │  │ • Access logs    │  │ • Service calls  │         │
│  │ • Latency        │  │ • Error logs     │  │ • DB queries     │         │
│  │ • Resource usage │  │ • Audit logs     │  │ • External APIs  │         │
│  │ • Queue depth    │  │ • Security logs  │  │ • Async tasks    │         │
│  │ • Hardware stats │  │ • System logs    │  │ • Hardware ops   │         │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘         │
│           │                     │                     │                    │
│           ▼                     ▼                     ▼                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   Prometheus     │  │      Loki        │  │     Jaeger       │         │
│  │   + Alertmanager │  │   + Vector       │  │                  │         │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘         │
│           │                     │                     │                    │
│           └─────────────────────┼─────────────────────┘                    │
│                                 ▼                                           │
│                    ┌────────────────────────┐                              │
│                    │        Grafana         │                              │
│                    │   (Unified Dashboard)  │                              │
│                    └────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
Error Handling & Resilience
Circuit Breaker Pattern
python
# Circuit breaker for external services
@circuit_breaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=ConnectionError
)
async def call_external_api():
    # API call that might fail
    pass
Retry with Backoff
python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(NetworkError)
)
async def resilient_operation():
    # Operation that may fail transiently
    pass
Bulkhead Pattern
python
# Limit concurrent operations
bulkhead = Bulkhead(max_concurrent_calls=10, max_wait_time=5.0)

@bulkhead
async def limited_operation():
    # Resource-intensive operation
    pass
Data Retention & Lifecycle
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Data Lifecycle Policy                               │
│                                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐          │
│  │  Real-   │────▶│  Active  │────▶│   Warm   │────▶│   Cold   │          │
│  │  time    │     │ Storage  │     │ Storage  │     │ Storage  │          │
│  │  (Live)  │     │ (Hot)    │     │ (Warm)   │     │ (Archive)│          │
│  └──────────┘     └──────────┘     └──────────┘     └──────────┘          │
│       │                │                │                │                 │
│       ▼                ▼                ▼                ▼                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐          │
│  │ Memory/  │     │  Redis/  │     │PostgreSQL│     │   S3/    │          │
│  │ Stream   │     │  MinIO   │     │(primary) │     │ Glacier │          │
│  └──────────┘     └──────────┘     └──────────┘     └──────────┘          │
│                                                                              │
│  Retention:                                                                  │
│  • Live: 1 minute                                                           │
│  • Hot: 24 hours                                                            │
│  • Warm: 90 days                                                            │
│  • Cold: 7 years                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
Performance Targets
Metric	Target	P99 Target
Detection Latency	< 100ms	< 500ms
API Response Time	< 50ms	< 200ms
WebSocket Message Latency	< 10ms	< 50ms
Database Query (simple)	< 10ms	< 50ms
Database Query (complex)	< 200ms	< 1000ms
IQ Processing Rate	10 MSPS	20 MSPS
Concurrent API Clients	1000	5000
Concurrent WebSocket	500	2000
Detection Accuracy	> 95%	N/A
False Positive Rate	< 1%	< 5%
Failure Modes & Mitigations
Failure	Mitigation	Recovery
SDR Hardware Failure	Fallback to mock hardware, alert operator	Auto-restart, hardware failover
Database Connection Loss	Connection pooling, retry logic	Automatic reconnect
Redis Failure	Local cache fallback	Replication, persistence
Network Partition	Circuit breakers, graceful degradation	Automatic failover
Disk Full	Monitoring, auto-cleanup, alerting	Manual intervention
High CPU/Load	Autoscaling, rate limiting	Scale out
Memory Leak	Restart policy, monitoring	Container restart
Future Architecture Extensions
Edge Computing
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Edge Deployment                                     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                      Edge Node (Raspberry Pi)                     │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                │      │
│  │  │   SDR      │─▶│  Local     │─▶│  Detection │                │      │
│  │  │ Capture    │  │ Processor  │  │  (Light)   │                │      │
│  │  └────────────┘  └────────────┘  └─────┬──────┘                │      │
│  │                                         │                         │      │
│  │                                         ▼                         │      │
│  │                              ┌────────────────────┐              │      │
│  │                              │   MQTT/WebSocket   │──────────┐   │      │
│  │                              │    (Compressed)    │          │   │      │
│  │                              └────────────────────┘          │   │      │
│  └──────────────────────────────────────────────────────────────┼───┘      │
│                                                                  │          │
│                                                                  ▼          │
│                                                          Cloud / Data Center│
└─────────────────────────────────────────────────────────────────────────────┘
Multi-Region Deployment
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Multi-Region Architecture                           │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   US-East         │  │    EU-West       │  │    AP-Southeast  │         │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │         │
│  │  │ API x4     │  │  │  │ API x4     │  │  │  │ API x4     │  │         │
│  │  │ Workers x8 │  │  │  │ Workers x8 │  │  │  │ Workers x8 │  │         │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │         │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │         │
│  │  │ PostgreSQL │  │  │  │ PostgreSQL │  │  │  │ PostgreSQL │  │         │
│  │  │  (Primary) │  │  │  │ (Replica)  │  │  │  │ (Replica)  │  │         │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │         │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘         │
│           │                     │                     │                    │
│           └─────────────────────┼─────────────────────┘                    │
│                                 │                                           │
│                    ┌────────────▼────────────┐                             │
│                    │    Global Load Balancer │                             │
│                    │    (GeoDNS/Route53)      │                             │
│                    └─────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
This architecture document serves as the authoritative reference for the Drone Detector system's design, guiding implementation decisions and ensuring consistency across the codebase.
