# Security Guide - HomeChef Companion Backend

This document outlines the security implementation and best practices for the HomeChef Companion backend application.

## 🔐 Secret Key Management

### Overview

The SECRET_KEY is used for:

- JWT token signing and verification
- Session security
- Cryptographic operations

### Key Generation

**Recommended Method:**

```bash
python3 generate_secret_key.py
```

**Alternative Methods:**

```bash
# Method 1: Python secrets module
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Method 2: OpenSSL
openssl rand -hex 32

# Method 3: Python urandom
python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(64)).decode())"
```

### Key Requirements

- **Minimum Length**: 32 bytes (256 bits)
- **Recommended Length**: 64 bytes (512 bits)
- **Format**: URL-safe base64 or hexadecimal
- **Entropy**: High randomness using cryptographically secure generators
- **Uniqueness**: Different keys for each environment (dev/staging/prod)

### Key Validation

Your application automatically validates the secret key on startup:

- Minimum length requirements
- Detection of default/weak values
- Pattern analysis for common weak strings

## 🔑 Authentication Architecture

### Clerk Integration

- **Primary Authentication**: Clerk handles user authentication
- **JWT Tokens**: Internal tokens signed with SECRET_KEY
- **Session Management**: Stateless JWT-based sessions
- **User Sync**: Webhook integration for user lifecycle events

### Authentication Flow

1. User authenticates through Clerk frontend
2. Clerk provides authentication token
3. Backend validates token with Clerk API
4. Internal JWT issued for API access
5. All protected routes require valid JWT

### Security Headers

The application implements:

- CORS protection
- JWT token validation
- Request rate limiting (planned)
- Input sanitization

## 🛡️ Database Security

### Connection Security

- **SSL Required**: All Neon Postgres connections use SSL
- **Connection Pooling**: Configured with secure defaults
- **Credential Management**: Environment variable based

### Data Protection

- **UUID Primary Keys**: Non-sequential, harder to guess
- **Foreign Key Constraints**: Data integrity enforcement
- **Input Validation**: Pydantic schema validation
- **SQL Injection Prevention**: SQLAlchemy ORM protection

### Migration Security

- **Version Control**: All schema changes tracked
- **Rollback Capability**: Alembic migration rollbacks
- **Environment Separation**: Different databases per environment

## 🌐 API Security

### Input Validation

- **Pydantic Schemas**: Strict type validation
- **File Upload Security**: Type and size restrictions
- **SQL Injection Prevention**: ORM-based queries
- **XSS Prevention**: Content sanitization

### Output Security

- **Data Serialization**: Controlled response formats
- **Error Handling**: Secure error messages
- **Logging**: Security event logging
- **Rate Limiting**: Protection against abuse (planned)

### CORS Configuration

```python
ALLOWED_ORIGINS = [
    "http://localhost:3000",    # Development frontend
    "http://localhost:5173",    # Vite dev server
    "https://yourdomain.com"    # Production frontend
]
```

## 🔧 Environment Security

### Environment Variables

**Required:**

- `DATABASE_URL`: Postgres connection string
- `SECRET_KEY`: JWT signing key

**Optional but Recommended:**

- `CLERK_SECRET_KEY`: Clerk authentication
- `CLERK_PUBLISHABLE_KEY`: Frontend integration
- `CLERK_WEBHOOK_SECRET`: Webhook validation

### File Security

- **`.env` Protection**: Never commit to version control
- **`.gitignore`**: Comprehensive exclusion rules
- **Permission Model**: Principle of least privilege

## 🚀 Deployment Security

### Production Checklist

- [ ] Generate unique SECRET_KEY for production
- [ ] Configure Clerk production keys
- [ ] Set up SSL/TLS certificates
- [ ] Configure secure CORS origins
- [ ] Enable database SSL
- [ ] Set up monitoring and logging
- [ ] Configure backup procedures
- [ ] Implement rate limiting

### Environment-Specific Keys

```bash
# Development
SECRET_KEY=dev-specific-key-here

# Staging
SECRET_KEY=staging-specific-key-here

# Production
SECRET_KEY=production-specific-key-here
```

## 🔍 Security Monitoring

### Validation Tools

```bash
# Test security configuration
python3 test_jwt_security.py

# Validate startup configuration
python3 app/core/startup.py

# Full application validation
python3 validate_setup.py
```

### Security Logging

The application logs:

- Authentication attempts
- Token validation failures
- Startup validation results
- Database connection issues
- Configuration warnings

### Monitoring Recommendations

- **Authentication Failures**: Monitor failed login attempts
- **Token Misuse**: Watch for invalid token usage
- **Database Access**: Monitor unusual query patterns
- **API Abuse**: Track request patterns and rates

## 🔄 Key Rotation

### Rotation Schedule

- **Development**: As needed
- **Staging**: Monthly
- **Production**: Quarterly or after security incidents

### Rotation Process

1. Generate new SECRET_KEY
2. Update environment configuration
3. Test token generation/validation
4. Deploy to staging environment
5. Validate all functionality
6. Deploy to production
7. Monitor for issues

### Emergency Rotation

In case of key compromise:

1. Immediately generate new key
2. Update all environments
3. Invalidate all existing tokens
4. Force user re-authentication
5. Audit access logs
6. Document incident

## 📚 Security Resources

### Tools Used

- **FastAPI Security**: Built-in security features
- **Pydantic**: Input validation and serialization
- **SQLAlchemy**: ORM-based query protection
- **python-jose**: JWT implementation
- **passlib**: Password hashing (if needed)
- **Clerk**: Authentication service

### Best Practices

1. **Principle of Least Privilege**: Minimal required permissions
2. **Defense in Depth**: Multiple security layers
3. **Regular Updates**: Keep dependencies current
4. **Security Testing**: Regular validation and testing
5. **Incident Response**: Prepared response procedures

### Compliance Considerations

- **Data Privacy**: User data protection
- **GDPR**: European data protection compliance
- **SOC 2**: Security controls framework
- **OWASP**: Web application security standards

## 🆘 Incident Response

### Security Incident Types

1. **Key Compromise**: Unauthorized access to SECRET_KEY
2. **Data Breach**: Unauthorized database access
3. **Authentication Bypass**: Circumventing auth controls
4. **Injection Attacks**: SQL, XSS, or other injections

### Response Procedures

1. **Immediate**: Secure the system
2. **Assess**: Determine scope and impact
3. **Contain**: Prevent further damage
4. **Investigate**: Root cause analysis
5. **Recover**: Restore normal operations
6. **Document**: Record lessons learned

### Emergency Contacts

- **Technical Lead**: [Your contact info]
- **Security Team**: [Security team contact]
- **Hosting Provider**: Neon support
- **Authentication Provider**: Clerk support

---

## 📞 Support

For security questions or concerns:

1. Review this documentation
2. Run validation tools
3. Check application logs
4. Contact the development team

**Remember**: When in doubt about security, err on the side of caution.
