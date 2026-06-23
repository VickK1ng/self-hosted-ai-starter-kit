# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly by
opening a private issue or contacting the maintainer directly. Do **not** open
a public issue for security vulnerabilities.

## Security Considerations

### Secrets Management

- **Never commit `.env` to version control.** The `.gitignore` is configured to
  exclude it.
- Copy `.env.example` to `.env` and replace all placeholder values with strong,
  unique secrets before starting the stack.
- Generate secrets with: `openssl rand -hex 32`

### Network Exposure

All service ports are bound to `127.0.0.1` (localhost) by default. This means
they are **only** reachable from the host machine. If you need remote access,
place a reverse proxy (e.g. Caddy, Traefik, nginx) in front of the services
with TLS and authentication enabled rather than binding to `0.0.0.0`.

### Docker Image Pinning

Docker images are pinned to specific versions to prevent supply-chain attacks
from compromised `latest` tags. When upgrading, review changelogs before bumping
versions.

### Service Authentication

- **n8n**: Requires user account creation on first access.
- **Ollama** (port 11434): No built-in authentication. Keep localhost-only or
  place behind an authenticated proxy.
- **Qdrant** (port 6333): Supports API key authentication. For production, enable
  it via Qdrant's configuration and update the n8n credential accordingly.
- **PostgreSQL**: Internal to the Docker network and not exposed to the host.

### Additional Hardening (Production)

1. Use Docker secrets or a vault (e.g., HashiCorp Vault) instead of `.env` files.
2. Enable TLS for PostgreSQL connections.
3. Run containers as non-root users where supported.
4. Set `read_only: true` on containers that don't need write access.
5. Regularly update pinned image versions to include security patches.
