# ManicTime Python Client Tests

This directory contains tests for the ManicTime Python client.

## Test Types

1. **Unit Tests** - Test individual components without external dependencies
2. **Integration Tests** - Test the client against a real ManicTime server running in Docker

## Running Tests

### Unit Tests

Run the unit tests (which don't require a server):

```bash
pytest tests/test_client.py -v
```

### Integration Tests with Docker

The integration tests require a running ManicTime server. We've provided a Docker-based setup to make this easy:

1. Make sure Docker and Docker Compose are installed
2. Run the integration tests script:

```bash
# From the project root
./run_docker_tests.sh
```

This script will:
- Start the ManicTime server in Docker
- Run the unit tests
- Run the integration tests
- Stop the Docker container when complete

### Manual Integration Testing

If you want to run the tests manually:

1. Start the Docker container:
```bash
docker-compose up -d
```

2. Wait for the server to initialize (~30 seconds)

3. Run the integration tests:
```bash
cd manictime
pytest -m docker tests/test_integration.py -v
```

4. Stop the container when done:
```bash
docker-compose down
```

## Test Configuration

The Docker-based ManicTime server is configured with:
- URL: http://localhost:8080
- Admin username: admin
- Admin password: admin123

You can modify these settings in the `docker-compose.yml` file and `tests/conftest.py`.