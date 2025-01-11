# Contract Processing System - Backend

## Overview

The Contract Processing System backend is a high-performance, scalable microservices architecture built with FastAPI and Python 3.9+. It provides automated contract processing, data extraction using Google Vision OCR, and purchase order generation capabilities.

## 🚀 Features

- **Contract Processing**: Automated data extraction from contracts using Google Vision OCR
- **Purchase Order Generation**: Template-based PO creation with customizable workflows
- **Microservices Architecture**: Scalable and maintainable service-oriented design
- **Security**: JWT-based authentication, role-based access control, and encryption
- **High Performance**: Asynchronous processing with FastAPI and Celery
- **Monitoring**: Comprehensive metrics collection and health monitoring
- **Containerization**: Docker-based deployment with orchestration support

## 🛠 Technology Stack

- **Python**: 3.9+
- **Web Framework**: FastAPI 0.95.0
- **Database**: MongoDB 6.0
- **Cache**: Redis 7.0
- **Task Queue**: Celery 5.2.0
- **OCR**: Google Cloud Vision API 3.4.0
- **Storage**: AWS S3 via Boto3 1.26.0
- **Documentation**: OpenAPI (Swagger) / ReDoc

## 📋 Prerequisites

- Python 3.9+
- Docker 24.0+
- Docker Compose v2.20+
- Poetry 1.4+
- MongoDB 6.0+
- Redis 7.0+
- Google Cloud Vision API credentials
- AWS S3 credentials

## 🔧 Development Setup

1. Clone the repository:
```bash
git clone <repository_url>
cd src/backend
```

2. Install dependencies using Poetry:
```bash
poetry install
poetry run pre-commit install
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Start development environment:
```bash
docker-compose up -d
```

5. Run development server:
```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🔒 Security Configuration

1. Authentication Setup:
   - Configure JWT secret key in `.env`
   - Set token expiration times
   - Enable MFA if required

2. Authorization:
   - Configure RBAC roles
   - Set up API rate limiting
   - Define access policies

3. API Security:
   - Configure CORS settings
   - Set up API key management
   - Enable request validation

## 🧪 Testing

Run the test suite:
```bash
# Run tests with coverage
poetry run pytest --cov=app tests/ --cov-report=xml

# Run specific test file
poetry run pytest tests/test_contracts.py -v
```

## 📦 Docker Development Environment

Start the development environment:
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Run tests in container
docker-compose exec api poetry run pytest
```

## 🔍 Environment Variables

Key environment variables (see `.env.example` for complete list):

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| MONGODB_URL | MongoDB connection string | mongodb://localhost:27017 | Yes |
| REDIS_HOST | Redis cache host | localhost | Yes |
| GOOGLE_VISION_CREDENTIALS | Google Vision API credentials path | None | Yes |
| AWS_S3_BUCKET_NAME | S3 bucket for document storage | None | Yes |
| MAX_FILE_SIZE_MB | Maximum file upload size | 25 | Yes |
| RATE_LIMIT_PER_MINUTE | API rate limit per user | 100 | Yes |

## 🛠 Development Tools

- **Code Formatting**: Black (line length: 100)
- **Import Sorting**: isort
- **Type Checking**: mypy
- **Linting**: flake8
- **Security Analysis**: bandit
- **Git Hooks**: pre-commit

## 🔍 Troubleshooting

### Common Issues

1. Database Connection Issues:
   ```bash
   # Check MongoDB container
   docker-compose logs mongodb
   # Verify connection string in .env
   ```

2. Cache Performance:
   ```bash
   # Check Redis container
   docker-compose logs redis
   # Monitor Redis metrics
   docker-compose exec redis redis-cli info
   ```

3. OCR Processing:
   ```bash
   # Verify Google credentials
   export GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
   # Check Vision API quota
   ```

## 📚 API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 🚀 Deployment

1. Build production image:
```bash
docker build -t cps-backend:latest .
```

2. Configure production environment:
   - Set `ENVIRONMENT=production`
   - Configure production databases
   - Set up monitoring

3. Deploy using orchestration:
```bash
# Kubernetes
kubectl apply -f k8s/

# Docker Swarm
docker stack deploy -c docker-compose.prod.yml cps
```

## 📈 Monitoring

- **Metrics**: Prometheus endpoint at `/metrics`
- **Health Check**: Status endpoint at `/health`
- **Logging**: JSON format logs to stdout
- **Tracing**: Distributed tracing with Jaeger

## 📝 License

Proprietary - All rights reserved

## 🤝 Contributing

1. Follow code style guidelines
2. Write tests for new features
3. Update documentation
4. Submit pull requests for review

## 📞 Support

- Create GitHub issues for bugs
- Contact development team for urgent issues
- Refer to troubleshooting guide