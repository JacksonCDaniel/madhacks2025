Quick start for local Redis using Docker Compose

Commands (PowerShell):

# from project root or backend/redis folder
# Start Redis in background
docker compose up -d

# Check status
docker ps --filter name=redis-demo

# View logs
docker compose logs -f

# Stop and remove resources
docker compose down

Notes:
- This composes a single Redis service on localhost:6379. Configure your app with REDIS_URL=redis://localhost:6379
- Uses a Docker named volume `redis_data` for persistence.

