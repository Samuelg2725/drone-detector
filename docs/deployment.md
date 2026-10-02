# Drone Detector System - Deployment Guide

## Overview

This guide covers deployment of the Drone Detector system in various environments, from development to production. The system supports multiple deployment strategies including Docker Compose, Kubernetes, and bare-metal installations.

## Deployment Architecture Options

### 1. Single-Node Deployment (Small/Medium Scale)
- Suitable for: Testing, small facilities, up to 5 SDRs
- Components: All services on one machine
- Hardware Requirements: 8+ cores, 16GB+ RAM, 256GB+ storage

### 2. Multi-Node Deployment (Production)
- Suitable for: Large facilities, multiple locations
- Components: Distributed across multiple servers
- Hardware Requirements: 3+ nodes, 16+ cores each, 32GB+ RAM each

### 3. Edge Deployment (Remote Locations)
- Suitable for: Raspberry Pi, embedded systems
- Components: Lightweight deployment on edge devices
- Hardware Requirements: Raspberry Pi 4/5, 4GB+ RAM, 64GB+ storage

### 4. Cloud/Hybrid Deployment
- Suitable for: Multi-site monitoring, cloud analytics
- Components: Edge nodes + cloud backend
- Hardware Requirements: Cloud VMs + edge devices

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 100 GB | 500+ GB (SSD) |
| Network | 1 Gbps | 10 Gbps |
| OS | Ubuntu 22.04 | Ubuntu 24.04 LTS |

### Software Requirements

```bash
# Required software
- Docker 24.0+ / Podman 4.0+
- Docker Compose 2.20+
- Python 3.11+
- PostgreSQL 16+
- Redis 7.2+
- MinIO (optional)
- NVIDIA Drivers (for GPU support)

# Development tools (optional)
- Git 2.40+
- Make 4.0+
- curl/wget
- jq
SDR Hardware Support
SDR	Driver	USB	Bandwidth
HackRF One	hackrf	USB 3.0	20 MHz
RTL-SDR	rtl-sdr	USB 2.0	2.4 MHz
ADALM-PLUTO	libiio	USB 2.0	20 MHz
LimeSDR	limesuite	USB 3.0	30 MHz
USRP B200	UHD	USB 3.0	56 MHz
Quick Deployment
One-Command Deployment
bash
# Clone repository
git clone https://github.com/drone-detector/drone-detector.git
cd drone-detector

# Quick start with default config
make deploy-quick

# Or use docker-compose directly
docker-compose up -d
Verify Deployment
bash
# Check health
curl http://localhost:8888/health

# Should return:
# {"status": "healthy", "version": "1.0.0"}

# Access web interface
open http://localhost:8888

# View logs
docker-compose logs -f
Docker Compose Deployment
Production Deployment
bash
# 1. Clone repository
git clone https://github.com/drone-detector/drone-detector.git
cd drone-detector

# 2. Create environment file
cp .env.example .env
# Edit .env with your configuration

# 3. Create data directories
mkdir -p /mnt/drone-data/{postgres,redis,minio,app,models}
chown -R 999:999 /mnt/drone-data/postgres
chown -R 1000:1000 /mnt/drone-data/redis

# 4. Deploy with production config
docker-compose -f docker-compose.prod.yml up -d

# 5. Scale services (optional)
docker-compose -f docker-compose.prod.yml up -d --scale api=3 --scale worker=5

# 6. Check status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs --tail=50
Development Deployment
bash
# Development with hot-reload
docker-compose -f docker-compose.dev.yml up

# With data science tools
docker-compose -f docker-compose.dev.yml --profile data-science up

# With SDR simulator
docker-compose -f docker-compose.dev.yml --profile sdr-sim up
Custom Configuration
yaml
# docker-compose.override.yml
version: '3.8'
services:
  api:
    environment:
      LOG_LEVEL: DEBUG
      GUNICORN_WORKERS: 2
    volumes:
      - ./custom_config:/app/config:ro
Kubernetes Deployment
Prerequisites
bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Create namespace
kubectl create namespace drone-detector
Helm Chart Deployment
bash
# Add repository
helm repo add drone-detector https://charts.drone-detector.com
helm repo update

# Install with custom values
cat > values.yaml << EOF
replicaCount: 3

image:
  repository: drone-detector/api
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 8888

resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"

postgresql:
  enabled: true
  postgresqlPassword: "secure_password"
  persistence:
    size: 100Gi

redis:
  enabled: true
  password: "redis_password"

minio:
  enabled: true
  rootUser: "minioadmin"
  rootPassword: "minioadmin123"

ingress:
  enabled: true
  hostname: drone.detector.local
  tls: true
EOF

# Deploy
helm install drone-detector drone-detector/drone-detector -f values.yaml -n drone-detector

# Check deployment
kubectl get pods -n drone-detector
kubectl get svc -n drone-detector
Manual Kubernetes Manifest Deployment
yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drone-detector-api
  namespace: drone-detector
spec:
  replicas: 3
  selector:
    matchLabels:
      app: drone-detector
      tier: api
  template:
    metadata:
      labels:
        app: drone-detector
        tier: api
    spec:
      containers:
      - name: api
        image: drone-detector/api:latest
        ports:
        - containerPort: 8888
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8888
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8888
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: drone-detector-api
  namespace: drone-detector
spec:
  selector:
    app: drone-detector
    tier: api
  ports:
  - port: 8888
    targetPort: 8888
  type: LoadBalancer
---
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
  namespace: drone-detector
type: Opaque
stringData:
  url: postgresql://user:password@postgres:5432/drone_detector
bash
# Apply manifests
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml

# Monitor deployment
kubectl rollout status deployment/drone-detector-api
kubectl get pods -w
Bare-Metal Installation
Ubuntu/Debian Installation
bash
#!/bin/bash
# install.sh - Bare-metal installation script

set -e

# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3.11 python3-pip python3-venv \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    git \
    build-essential \
    libfftw3-dev \
    libhackrf-dev \
    librtlsdr-dev \
    libusb-1.0-0-dev

# Create application user
sudo useradd -m -s /bin/bash drone
sudo usermod -aG plugdev drone

# Setup PostgreSQL
sudo -u postgres psql << EOF
CREATE DATABASE drone_detector;
CREATE USER drone_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE drone_detector TO drone_user;
EOF

# Setup Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Clone application
sudo mkdir -p /opt/drone-detector
sudo chown drone:drone /opt/drone-detector
sudo -u drone git clone https://github.com/drone-detector/drone-detector.git /opt/drone-detector

# Setup Python virtual environment
cd /opt/drone-detector
sudo -u drone python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure application
cp .env.example .env
# Edit .env with database credentials

# Setup systemd services
sudo cp systemd/drone-api.service /etc/systemd/system/
sudo cp systemd/drone-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable drone-api drone-worker
sudo systemctl start drone-api drone-worker

# Configure Nginx
sudo cp nginx/drone-detector.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/drone-detector.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
Systemd Service Files
ini
# /etc/systemd/system/drone-api.service
[Unit]
Description=Drone Detector API Service
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=drone
Group=drone
WorkingDirectory=/opt/drone-detector
Environment="PATH=/opt/drone-detector/venv/bin"
EnvironmentFile=/opt/drone-detector/.env
ExecStart=/opt/drone-detector/venv/bin/gunicorn api.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8888
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
ini
# /etc/systemd/system/drone-worker.service
[Unit]
Description=Drone Detector Worker Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=drone
Group=drone
WorkingDirectory=/opt/drone-detector
Environment="PATH=/opt/drone-detector/venv/bin"
EnvironmentFile=/opt/drone-detector/.env
ExecStart=/opt/drone-detector/venv/bin/python app/workers/worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
Nginx Configuration
nginx
# /etc/nginx/sites-available/drone-detector.conf
upstream drone_api {
    server 127.0.0.1:8888;
}

upstream drone_websocket {
    server 127.0.0.1:8889;
}

server {
    listen 80;
    server_name drone.detector.local;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name drone.detector.local;

    ssl_certificate /etc/ssl/certs/drone-detector.crt;
    ssl_certificate_key /etc/ssl/private/drone-detector.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API
    location /api/ {
        proxy_pass http://drone_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://drone_websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Static files
    location /static/ {
        alias /opt/drone-detector/ui/;
        expires 30d;
    }

    # Health check
    location /health {
        proxy_pass http://drone_api/health;
        access_log off;
    }
}
Edge Deployment (Raspberry Pi)
Raspberry Pi 4/5 Setup
bash
#!/bin/bash
# deploy_edge.sh - Raspberry Pi deployment

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
    python3-pip \
    libhackrf-dev \
    librtlsdr-dev \
    libfftw3-dev \
    nginx

# Enable USB auto-mount for SDR
sudo apt install -y usbmount

# Setup optimized kernel
echo "dtoverlay=disable-bt" | sudo tee -a /boot/config.txt
echo "dtoverlay=pi3-miniuart-bt" | sudo tee -a /boot/config.txt

# Set CPU governor to performance
echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils

# Create swap file (for memory-constrained devices)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Setup lightweight deployment
cd /opt
sudo git clone https://github.com/drone-detector/drone-detector.git
cd drone-detector

# Use edge-optimized configuration
cp config/edge.yaml config/system.yaml

# Install Python lightweight dependencies
pip3 install --no-cache-dir -r requirements-edge.txt

# Setup auto-start on boot
cat << EOF | sudo tee /etc/rc.local
#!/bin/bash
cd /opt/drone-detector
sudo -u pi python3 run.py --mode edge &
exit 0
EOF

sudo chmod +x /etc/rc.local

# Reboot
sudo reboot
Edge Optimized Configuration
yaml
# config/edge.yaml
system:
  mode: edge
  log_level: INFO
  
hardware:
  type: auto
  sample_rate: 1000000  # Reduced for edge
  gain: 20
  
detection:
  enabled: true
  threshold: 15  # Higher threshold for edge
  update_interval: 500  # ms
  
processing:
  fft_size: 512  # Smaller FFT for edge
  peak_detection: true
  ml_inference: false  # Disable ML on edge
  feature_extraction: true
  
storage:
  local_storage: true
  upload_to_cloud: true
  cloud_endpoint: "https://api.drone-detector.com"
  retention_days: 7
  
network:
  batch_size: 100
  upload_interval: 60  # seconds
  compression: true
Cloud Deployment (AWS/GCP/Azure)
AWS Deployment with Terraform
hcl
# main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-west-2"
}

# VPC
resource "aws_vpc" "drone_detector" {
  cidr_block = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support = true
  
  tags = {
    Name = "drone-detector-vpc"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "drone_detector" {
  name = "drone-detector-cluster"
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier = "drone-detector-db"
  engine = "postgres"
  engine_version = "16.3"
  instance_class = "db.t3.large"
  allocated_storage = 100
  storage_encrypted = true
  db_name = "drone_detector"
  username = "drone_user"
  password = random_password.db_password.result
  backup_retention_period = 30
  backup_window = "03:00-04:00"
  maintenance_window = "Mon:04:00-Mon:05:00"
  skip_final_snapshot = false
  final_snapshot_identifier = "drone-detector-final-snapshot"
  
  tags = {
    Name = "drone-detector-db"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id = "drone-detector-redis"
  engine = "redis"
  node_type = "cache.t3.micro"
  num_cache_nodes = 1
  parameter_group_name = "default.redis7"
  port = 6379
  
  tags = {
    Name = "drone-detector-redis"
  }
}

# S3 Bucket for IQ Recordings
resource "aws_s3_bucket" "iq_storage" {
  bucket = "drone-detector-iq-${random_id.bucket_suffix.hex}"
  
  lifecycle_rule {
    enabled = true
    transition {
      days = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days = 90
      storage_class = "GLACIER"
    }
    expiration {
      days = 365
    }
  }
}

# ECR Repository
resource "aws_ecr_repository" "drone_detector" {
  name = "drone-detector"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "api" {
  family = "drone-detector-api"
  network_mode = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu = "1024"
  memory = "2048"
  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn = aws_iam_role.ecs_task.arn
  
  container_definitions = jsonencode([
    {
      name = "drone-detector-api"
      image = "${aws_ecr_repository.drone_detector.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8888
          protocol = "tcp"
        }
      ]
      environment = [
        {
          name = "ENVIRONMENT"
          value = "production"
        },
        {
          name = "DATABASE_URL"
          value = "postgresql://drone_user:${random_password.db_password.result}@${aws_db_instance.postgres.address}:5432/drone_detector"
        },
        {
          name = "REDIS_URL"
          value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group" = "/ecs/drone-detector"
          "awslogs-region" = "us-west-2"
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

# Auto-scaling
resource "aws_appautoscaling_target" "api" {
  max_capacity = 10
  min_capacity = 2
  resource_id = "service/${aws_ecs_cluster.drone_detector.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name = "api-cpu-autoscaling"
  policy_type = "TargetTrackingScaling"
  resource_id = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace = aws_appautoscaling_target.api.service_namespace
  
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
    scale_in_cooldown = 300
    scale_out_cooldown = 60
  }
}
bash
# Deploy to AWS
cd terraform
terraform init
terraform plan
terraform apply -auto-approve

# Build and push Docker image
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-west-2.amazonaws.com
docker build -t drone-detector:latest .
docker tag drone-detector:latest <account>.dkr.ecr.us-west-2.amazonaws.com/drone-detector:latest
docker push <account>.dkr.ecr.us-west-2.amazonaws.com/drone-detector:latest

# Update ECS service
aws ecs update-service --cluster drone-detector-cluster --service drone-detector-api --force-new-deployment
GCP Deployment
bash
# Setup Google Cloud SDK
gcloud init
gcloud config set project drone-detector-project

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com

# Create GKE cluster
gcloud container clusters create drone-detector-cluster \
    --zone us-central1-a \
    --num-nodes 3 \
    --machine-type n2-standard-4

# Create Cloud SQL PostgreSQL
gcloud sql instances create drone-detector-db \
    --database-version POSTGRES_16 \
    --tier db-custom-2-8192 \
    --region us-central1 \
    --storage-type SSD \
    --storage-size 100GB \
    --backup-start-time 03:00

# Create Memorystore Redis
gcloud redis instances create drone-detector-redis \
    --size=5 \
    --region=us-central1 \
    --zone=us-central1-a \
    --redis-version=redis_7_2

# Deploy to GKE
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Setup Cloud Run (serverless option)
gcloud run deploy drone-detector-api \
    --image gcr.io/drone-detector-project/drone-detector:latest \
    --platform managed \
    --region us-central1 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 2 \
    --max-instances 10 \
    --concurrency 80
High Availability Configuration
Load Balancing
yaml
# haproxy.cfg
global
    daemon
    maxconn 4096
    log /dev/log local0

defaults
    mode http
    timeout connect 5s
    timeout client 50s
    timeout server 50s
    log global

frontend http_front
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/drone-detector.pem
    redirect scheme https code 301 if !{ ssl_fc }
    
    acl api_path path_beg /api
    acl ws_path path_beg /ws
    
    use_backend api_backend if api_path
    use_backend ws_backend if ws_path
    
    default_backend web_backend

backend api_backend
    balance roundrobin
    option httpchk GET /health
    server api1 10.0.0.1:8888 check inter 5s rise 2 fall 3
    server api2 10.0.0.2:8888 check inter 5s rise 2 fall 3
    server api3 10.0.0.3:8888 check inter 5s rise 2 fall 3 backup

backend ws_backend
    balance leastconn
    option httpchk GET /health
    server ws1 10.0.0.1:8889 check inter 5s rise 2 fall 3
    server ws2 10.0.0.2:8889 check inter 5s rise 2 fall 3
    server ws3 10.0.0.3:8889 check inter 5s rise 2 fall 3

backend web_backend
    balance roundrobin
    server web1 10.0.0.1:80 check
    server web2 10.0.0.2:80 check
Database Replication
sql
-- Setup PostgreSQL streaming replication
-- Primary server (postgresql.conf)
wal_level = replica
max_wal_senders = 10
wal_keep_segments = 64
hot_standby = on

-- Replica server (recovery.conf)
primary_conninfo = 'host=primary host=10.0.0.1 port=5432 user=replica password=replica'
trigger_file = '/tmp/promote_to_primary'

-- Create replication user
CREATE USER replica WITH REPLICATION ENCRYPTED PASSWORD 'replica_password';
GRANT CONNECT ON DATABASE drone_detector TO replica;
Redis Sentinel for High Availability
yaml
# docker-compose.sentinel.yml
version: '3.8'
services:
  redis-master:
    image: redis:7.2-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    
  redis-replica-1:
    image: redis:7.2-alpine
    command: redis-server --slaveof redis-master 6379 --requirepass ${REDIS_PASSWORD}
    
  redis-replica-2:
    image: redis:7.2-alpine
    command: redis-server --slaveof redis-master 6379 --requirepass ${REDIS_PASSWORD}
    
  redis-sentinel-1:
    image: redis:7.2-alpine
    command: redis-sentinel /usr/local/etc/redis/sentinel.conf
    volumes:
      - ./sentinel.conf:/usr/local/etc/redis/sentinel.conf
      
  redis-sentinel-2:
    image: redis:7.2-alpine
    command: redis-sentinel /usr/local/etc/redis/sentinel.conf
    volumes:
      - ./sentinel.conf:/usr/local/etc/redis/sentinel.conf
Monitoring & Logging
Prometheus Configuration
yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'drone-detector'
    static_configs:
      - targets: ['api:8888', 'worker:8888']
    metrics_path: '/metrics'
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
      
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
      
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
Grafana Dashboards
json
{
  "dashboard": {
    "title": "Drone Detector Monitoring",
    "panels": [
      {
        "title": "Detection Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(drone_detections_total[5m])",
            "legendFormat": "detections/sec"
          }
        ]
      },
      {
        "title": "Detection Latency",
        "type": "heatmap",
        "targets": [
          {
            "expr": "drone_detection_latency_ms",
            "format": "heatmap"
          }
        ]
      },
      {
        "title": "System Resources",
        "type": "graph",
        "targets": [
          {
            "expr": "node_cpu_seconds_total{mode='user'}",
            "legendFormat": "CPU usage"
          },
          {
            "expr": "node_memory_MemTotal_bytes - node_memory_MemFree_bytes",
            "legendFormat": "Memory usage"
          }
        ]
      }
    ]
  }
}
Log Aggregation with Loki
yaml
# loki-config.yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/index_cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: true
  retention_period: 720h
Security Hardening
TLS/SSL Configuration
bash
# Generate SSL certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/drone-detector.key \
    -out /etc/ssl/certs/drone-detector.crt \
    -subj "/CN=drone.detector.local"

# Generate stronger DH parameters
openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048
Security Headers
nginx
# Security headers configuration
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
Fail2Ban Configuration
ini
# /etc/fail2ban/jail.local
[drone-detector]
enabled = true
port = http,https
filter = drone-detector
logpath = /var/log/drone-detector/api.log
maxretry = 5
bantime = 3600
findtime = 600
ini
# /etc/fail2ban/filter.d/drone-detector.conf
[Definition]
failregex = ^.*Failed login attempt from <HOST>.*$
            ^.*Invalid API key from <HOST>.*$
            ^.*Brute force detected from <HOST>.*$
ignoreregex =
Security Scanning
bash
# Run security scans
docker scan drone-detector:latest
trivy image drone-detector:latest
grype drone-detector:latest

# Check for secrets
git secrets --scan
trufflehog --regex --entropy=True .

# Compliance scanning
kube-bench run --targets master,node
Backup & Recovery
Automated Backup Script
bash
#!/bin/bash
# backup.sh - Automated backup script

BACKUP_DIR="/backups/drone-detector"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR/{database,config,recordings,models}

# Backup PostgreSQL
PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -U $DB_USER $DB_NAME \
    | gzip > $BACKUP_DIR/database/drone_db_$DATE.sql.gz

# Backup Redis
redis-cli -a $REDIS_PASSWORD --rdb $BACKUP_DIR/redis/dump_$DATE.rdb

# Backup MinIO/S3 recordings
aws s3 sync s3://drone-recordings $BACKUP_DIR/recordings/

# Backup configuration
tar czf $BACKUP_DIR/config/config_$DATE.tar.gz /opt/drone-detector/config/

# Backup ML models
tar czf $BACKUP_DIR/models/models_$DATE.tar.gz /opt/drone-detector/models/

# Clean old backups
find $BACKUP_DIR -type f -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -type f -name "*.rdb" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -type f -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Upload to cloud (optional)
aws s3 sync $BACKUP_DIR s3://drone-backups/

echo "Backup completed: $DATE"
Recovery Procedure
bash
#!/bin/bash
# restore.sh - Recovery script

# 1. Restore PostgreSQL
gunzip -c $BACKUP_DIR/database/drone_db_$DATE.sql.gz | \
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER $DB_NAME

# 2. Restore Redis
systemctl stop redis
cp $BACKUP_DIR/redis/dump_$DATE.rdb /var/lib/redis/dump.rdb
systemctl start redis

# 3. Restore configuration
tar xzf $BACKUP_DIR/config/config_$DATE.tar.gz -C /

# 4. Restart services
systemctl restart drone-api drone-worker

echo "Restore completed from: $DATE"
Troubleshooting
Common Issues
bash
# Issue: SDR not detected
lsusb | grep -i hackrf
sudo modprobe hackrf
sudo hackrf_info

# Issue: Database connection failed
sudo systemctl status postgresql
netstat -tulpn | grep 5432
tail -f /var/log/postgresql/postgresql.log

# Issue: High memory usage
free -h
top -o %MEM
docker stats

# Issue: API not responding
curl -v http://localhost:8888/health
sudo netstat -tulpn | grep 8888
tail -f /var/log/drone-detector/api.log

# Issue: WebSocket disconnects
# Increase timeout in nginx
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;

# Issue: Permission denied for SDR
sudo usermod -a -G plugdev $USER
sudo chmod 666 /dev/bus/usb/*/*
Performance Tuning
yaml
# PostgreSQL tuning (postgresql.conf)
shared_buffers = '4GB'
effective_cache_size = '12GB'
maintenance_work_mem = '1GB'
work_mem = '50MB'
max_connections = 200
random_page_cost = 1.1

# Redis tuning (redis.conf)
maxmemory 4gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000

# System tuning (sysctl.conf)
net.core.somaxconn = 65535
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
Upgrade Procedures
Rolling Upgrade
bash
# Docker Compose upgrade
docker-compose pull
docker-compose up -d --no-deps --scale api=0 api
docker-compose up -d --no-deps --scale api=3 api

# Kubernetes rolling update
kubectl set image deployment/drone-detector-api api=drone-detector:new-version
kubectl rollout status deployment/drone-detector-api

# Database migrations
python scripts/migrate.py upgrade head

# Rollback if needed
kubectl rollout undo deployment/drone-detector-api
Version Compatibility
Component	Version	Compatible With
API	1.x	All 1.x clients
Database Schema	v1.0	API 1.0+
ML Models	v2	API 1.2+
Config Files	v1	All versions
Post-Deployment Checklist
Services running and healthy

Database migrations applied

Hardware SDR detected

SSL certificates valid

Firewall rules configured

Backups scheduled

Monitoring alerts configured

Log rotation enabled

Security updates applied

Load balancing tested

Failover tested

Documentation updated

Support & Maintenance
Health Check Endpoints
bash
# Check all services
curl http://localhost:8888/health

# Check database
curl http://localhost:8888/health/database

# Check hardware
curl http://localhost:8888/health/hardware

# Check ML model
curl http://localhost:8888/health/ml
Maintenance Mode
bash
# Enable maintenance mode
curl -X POST http://localhost:8888/api/v1/system/maintenance \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"enabled": true, "message": "Scheduled maintenance"}'

# Disable maintenance mode
curl -X POST http://localhost:8888/api/v1/system/maintenance \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"enabled": false}'
