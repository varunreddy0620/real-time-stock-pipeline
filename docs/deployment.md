# Deployment

## Local (canonical)

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f consumer
```

## CI

`.github/workflows/ci.yml` runs flake8, pytest with a 70% coverage gate, builds the image, and executes a deterministic Compose integration test including Redis, PostgreSQL, MinIO, Streamlit, and dbt.

Pushing an image to Docker Hub is left as Task 16’s stretch goal (`docker/login-action` + `docker/build-push-action`).

## Cloud sketch

| Piece | Simple hosting |
| --- | --- |
| App containers | Fly.io / Railway |
| Postgres | Supabase or managed Postgres |
| Object storage | Real S3 (change endpoint + credentials) |
| Dashboard | Same Streamlit container, bind a public port |

Terraform under `infra/terraform/` is reserved for a later module; Compose is the course default so every student can finish on a laptop.

## Production checklist

- Rotate MinIO/Postgres passwords
- Enable SendGrid from a verified domain
- Add volume backups for Postgres
- Restrict Streamlit if the dashboard is public
- Keep Redis, PostgreSQL, and MinIO bound to private interfaces
- Pin container image digests and review them during upgrades
