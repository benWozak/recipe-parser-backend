# Docker Security Guide

## Security Overview

This document provides comprehensive security guidance for deploying the HomeChef Companion backend using Docker.

## Base Image Security

### Current Configuration
- **Base Image**: `python:3.12-slim-bookworm`
- **Rationale**: More stable than 3.13, fewer known vulnerabilities than older versions
- **Multi-stage build**: Separates build dependencies from runtime

### Why Python 3.12-slim-bookworm?
1. **Stability**: More mature ecosystem than 3.13
2. **Security**: Debian Bookworm has regular security updates
3. **Size**: Slim variant reduces attack surface (~150 packages vs 570+)
4. **Support**: Extended security support timeline

## Security Scanning

### Before Deployment
Always scan your images for vulnerabilities before deployment:

```bash
# Using Docker Scout (built-in)
docker scout cves recipecatalogue-backend

# Using Trivy
trivy image recipecatalogue-backend

# Using Snyk (requires account)
snyk container test recipecatalogue-backend
```

### CI/CD Integration
Add security scanning to your GitHub Actions:

```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'recipecatalogue-backend:latest'
    format: 'sarif'
    output: 'trivy-results.sarif'

- name: Upload Trivy scan results to GitHub Security tab
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: 'trivy-results.sarif'
```

## Security Best Practices

### 1. Non-Root User
The Dockerfile creates and uses a non-root user (`appuser`) to minimize privilege escalation risks.

### 2. Minimal Dependencies
- Uses slim base image
- Only installs necessary runtime dependencies
- Cleans package cache after installation

### 3. File System Security
- Read-only filesystem where possible
- Secure media directory permissions
- Quarantine directory for uploaded files

### 4. Network Security
- Only exposes necessary port (8000)
- CORS configuration via environment variables
- Rate limiting enabled by default

## Production Security Checklist

### Environment Variables
- [ ] `SECRET_KEY` generated using `python generate_secret_key.py`
- [ ] `DATABASE_URL` uses SSL (`?sslmode=require` for external DBs)
- [ ] Clerk keys are production keys (not test keys)
- [ ] `ALLOWED_ORIGINS` set to actual frontend domains

### Image Security
- [ ] Base image vulnerability scan passed
- [ ] No secrets in image layers
- [ ] Multi-stage build removes build tools
- [ ] Non-root user configured

### Runtime Security
- [ ] Container runs as non-root
- [ ] File uploads go to quarantine first
- [ ] Rate limiting enabled
- [ ] Security headers middleware active
- [ ] Request size limits configured

## Monitoring and Logging

### Security Events
The application logs security events to `/app/logs/security_events.log`:
- Authentication failures
- Rate limit violations
- File upload security violations
- Suspicious request patterns

### File Upload Security
All uploads are scanned and logged:
- File type validation
- Security score calculation
- Quarantine process for suspicious files
- Detailed logging in `/app/logs/file_uploads.log`

## Vulnerability Response

### When Vulnerabilities Are Found

1. **Assess Severity**: Use CVSS scores and impact analysis
2. **Check Availability**: Look for updated base images
3. **Test Updates**: Verify application compatibility
4. **Deploy Patches**: Use rolling updates for zero downtime
5. **Verify Fix**: Re-scan after updates

### Update Process
```bash
# Update base image
docker build --pull --no-cache -t recipecatalogue-backend:latest .

# Scan updated image
trivy image recipecatalogue-backend:latest

# Deploy if scan passes
docker-compose up -d --no-deps backend
```

## Alternative Secure Configurations

### Distroless Option (Advanced)
For maximum security, consider a distroless runtime:

```dockerfile
# Use Google's distroless Python image for runtime
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
# Note: No shell access, harder debugging
```

### Security-Hardened Alpine
If you prefer Alpine Linux:

```dockerfile
FROM python:3.12-alpine3.19
# Add security updates
RUN apk update && apk upgrade
# Install only necessary packages
```

## Resources

- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [OWASP Container Security](https://owasp.org/www-project-container-security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Snyk Container Security](https://snyk.io/learn/container-security/)

## Support

For security questions or to report vulnerabilities:
- Create an issue with the `security` label
- Include scan results and affected versions
- Follow responsible disclosure practices