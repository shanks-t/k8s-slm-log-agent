# OIDC Authentication Implementation Plan

## Table of Contents
1. [Overview](#overview)
2. [OIDC Fundamentals](#oidc-fundamentals)
3. [Architecture Design](#architecture-design)
4. [Keycloak Setup](#keycloak-setup)
5. [Log Analyzer Integration](#log-analyzer-integration)
6. [Development Workflow](#development-workflow)
7. [Implementation Phases](#implementation-phases)
8. [Testing Strategy](#testing-strategy)
9. [Learning Objectives](#learning-objectives)
10. [References](#references)

---

## Overview

### Goals
Implement industry-standard OpenID Connect (OIDC) authentication for the log-analyzer API using Keycloak as the identity provider (IdP), enabling:

- **Hands-on OIDC learning**: Understand OAuth 2.0/OIDC flows, JWT structure, and claims-based authorization
- **Kubernetes-native patterns**: Service-to-service authentication, RBAC integration, sidecar patterns
- **Self-hosted security**: Run Keycloak in-cluster for full control and learning
- **Fast feedback loops**: Maintain local development velocity with mocked/bypassed auth
- **Production patterns**: Implement patterns used by professional teams (JWT validation, token introspection, RBAC)

### Why Keycloak?
- **Open source**: Self-hostable, no vendor lock-in
- **Feature-complete**: OIDC/OAuth 2.0, SAML, user federation, SSO
- **Kubernetes-friendly**: Official Docker images, Helm charts, operator patterns
- **Learning-oriented**: Admin UI for exploring OIDC concepts visually
- **Production-grade**: Used by Netflix, Red Hat, and other enterprises

### Current State
- **Authentication**: None (all endpoints publicly accessible within cluster)
- **Authorization**: None (no RBAC, roles, or permissions)
- **Network security**: ClusterIP isolation only
- **API structure**: FastAPI with health, prompts, and analysis endpoints

---

## OIDC Fundamentals

### What is OIDC?
OpenID Connect (OIDC) is an identity layer on top of OAuth 2.0 that provides:
- **Authentication**: "Who is the user?" (via ID tokens)
- **Authorization**: "What can they access?" (via access tokens)
- **User info**: Standardized claims about the user (email, roles, groups)

### Key Concepts

#### 1. **Tokens**
| Token Type | Purpose | Format | Validation |
|------------|---------|--------|------------|
| **ID Token** | Proves user identity | JWT | Signature + claims |
| **Access Token** | Grants API access | JWT (opaque optional) | Signature + expiry |
| **Refresh Token** | Obtains new access tokens | Opaque string | Server-side only |

#### 2. **JWT Structure**
```
HEADER.PAYLOAD.SIGNATURE

Header:
{
  "alg": "RS256",        # RSA SHA-256 signing
  "typ": "JWT",
  "kid": "key-id"        # Key ID for rotation
}

Payload (Claims):
{
  "iss": "https://keycloak/realms/homelab",  # Issuer
  "sub": "user-uuid",                         # Subject (user ID)
  "aud": "log-analyzer",                      # Audience (API)
  "exp": 1735689600,                          # Expiration (Unix timestamp)
  "iat": 1735686000,                          # Issued at
  "auth_time": 1735686000,                    # Authentication time
  "azp": "log-analyzer-client",               # Authorized party
  "scope": "openid profile email",            # OAuth scopes
  "email": "user@example.com",
  "preferred_username": "user",
  "realm_access": {
    "roles": ["log-viewer", "sre-admin"]
  }
}

Signature:
RS256(base64(header) + "." + base64(payload), private_key)
```

#### 3. **OIDC Flows**

**Authorization Code Flow** (recommended for web apps):
```
1. User → API → Redirect to Keycloak login
2. User authenticates at Keycloak
3. Keycloak → Redirect back with authorization code
4. API → Exchange code for tokens (server-side)
5. API → Validate and use access token
```

**Client Credentials Flow** (for service-to-service):
```
1. Service → POST client_id + client_secret to Keycloak
2. Keycloak → Returns access token
3. Service → Use token in API requests (Bearer header)
```

**Resource Owner Password Flow** (for CLI tools):
```
1. User provides username + password to CLI
2. CLI → POST credentials to Keycloak
3. Keycloak → Returns tokens
4. CLI → Use tokens in API requests
```

#### 4. **Standard Claims**
- **iss**: Issuer (Keycloak URL)
- **sub**: Subject (unique user ID)
- **aud**: Audience (your API identifier)
- **exp**: Expiration time (Unix timestamp)
- **iat**: Issued at time
- **auth_time**: When user authenticated
- **nonce**: Replay attack prevention
- **scope**: Requested permissions
- **email**, **name**, **preferred_username**: User attributes

#### 5. **Custom Claims**
Keycloak allows adding custom claims for application-specific data:
- **Roles**: `realm_access.roles`, `resource_access.log-analyzer.roles`
- **Groups**: `groups: ["sre-team", "devops"]`
- **Attributes**: `department`, `cost_center`, `access_level`

---

## Architecture Design

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         User / CLI Client                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 1. Request with JWT Bearer token
                         │    Authorization: Bearer eyJhbGc...
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Envoy Gateway (Node 1)                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Optional: JWT validation at gateway (future enhancement)  │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │ 2. Forward request
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Log Analyzer Service (log-analyzer NS)              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ FastAPI Middleware: JWT Validation                        │  │
│  │  • Extract Bearer token from Authorization header         │  │
│  │  • Verify signature using Keycloak's public key (JWKS)    │  │
│  │  • Validate claims (iss, aud, exp, nbf)                   │  │
│  │  • Extract roles/permissions from token                   │  │
│  │  • Inject user context into request state                 │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       │ 3. Authenticated request                │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Authorization Layer (Endpoint Dependencies)               │  │
│  │  • Check roles: require_role("log-viewer")                │  │
│  │  • Check scopes: require_scope("logs:read")               │  │
│  │  • Policy enforcement: RBAC or ABAC                       │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│                       │ 4. Authorized request                   │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Business Logic (Pipeline)                                 │  │
│  │  • Loki query → normalize → LLM → response                │  │
│  │  • Audit logging with user context                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         │ 5. Query for token validation
                         │    (JWKS endpoint / token introspection)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Keycloak (keycloak NS, Node 2)                  │
│                                                                   │
│  • Realms: "homelab" (production), "dev" (local testing)         │
│  • Clients: "log-analyzer" (API), "cli-tool" (user client)      │
│  • Roles: "sre-admin", "log-viewer", "readonly"                 │
│  • Users: Admin users, service accounts                          │
│  • JWKS endpoint: /.well-known/openid-configuration             │
│  • Token introspection: /protocol/openid-connect/token/introspect│
└─────────────────────────────────────────────────────────────────┘
```

### Token Flow (Client Credentials - Service-to-Service)

```
┌─────────────┐                                   ┌──────────────┐
│   Service   │                                   │  Keycloak    │
│  (CLI/App)  │                                   │              │
└──────┬──────┘                                   └──────┬───────┘
       │                                                  │
       │ 1. POST /token                                  │
       │    client_id=log-analyzer-client                │
       │    client_secret=xxx                            │
       │    grant_type=client_credentials                │
       ├────────────────────────────────────────────────►│
       │                                                  │
       │                            2. Validate client   │
       │                               Generate JWT      │
       │                                                  │
       │ 3. Response: access_token (JWT)                 │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │                                                  │
       │ 4. GET /v1/analyze                              │
┌──────┴──────┐    Authorization: Bearer <JWT>   ┌──────┴───────┐
│ Log Analyzer│◄─────────────────────────────────┤   Service    │
│     API     │                                   │              │
└──────┬──────┘                                   └──────────────┘
       │
       │ 5. Extract JWT, fetch JWKS from Keycloak
       │
       ├────────────────────────────────────────────────►┐
       │ GET /.well-known/jwks.json              Keycloak│
       │◄────────────────────────────────────────────────┤
       │ Response: {keys: [{kid, kty, n, e, ...}]}       │
       │                                                  │
       │ 6. Verify JWT signature with public key         │
       │    Validate claims (iss, aud, exp)              │
       │    Extract roles/scopes                         │
       │                                                  │
       │ 7. Execute business logic                       │
       │    Return response                              │
       │                                                  │
```

### Deployment Architecture

**Node Placement:**
- **Keycloak**: Node 2 (heavy) - Database-backed, stateful
- **Log Analyzer**: Node 1 (light) - Stateless API, JWT validation
- **Postgres** (Keycloak DB): Node 2 (heavy) - Persistent storage

**Namespace Organization:**
```
keycloak/
├── deployment.yaml       # Keycloak server
├── service.yaml          # ClusterIP on port 8080
├── postgres.yaml         # PostgreSQL for Keycloak
├── configmap.yaml        # Realm configuration
└── kustomization.yaml

log-analyzer/             # Existing namespace
├── deployment.yaml       # Updated with OIDC config
├── service.yaml          # No changes
└── configmap.yaml        # Add KEYCLOAK_URL env var
```

---

## Keycloak Setup

### Phase 1: Basic Keycloak Deployment

#### 1. PostgreSQL Database
```yaml
# infrastructure/keycloak/postgres.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: keycloak-postgres-pvc
  namespace: keycloak
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: local-path
  volumeBindingMode: WaitForFirstConsumer
  resources:
    requests:
      storage: 5Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keycloak-postgres
  namespace: keycloak
spec:
  replicas: 1
  selector:
    matchLabels:
      app: keycloak-postgres
  template:
    metadata:
      labels:
        app: keycloak-postgres
    spec:
      nodeSelector:
        hardware: heavy  # Node 2
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: keycloak
        - name: POSTGRES_USER
          value: keycloak
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-postgres
              key: password
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: keycloak-postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: keycloak-postgres
  namespace: keycloak
spec:
  selector:
    app: keycloak-postgres
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None  # Headless service
```

#### 2. Keycloak Deployment
```yaml
# infrastructure/keycloak/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keycloak
  namespace: keycloak
spec:
  replicas: 1
  selector:
    matchLabels:
      app: keycloak
  template:
    metadata:
      labels:
        app: keycloak
    spec:
      nodeSelector:
        hardware: heavy  # Node 2
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        effect: NoSchedule
      containers:
      - name: keycloak
        image: quay.io/keycloak/keycloak:23.0  # Latest stable
        args:
        - start
        - --db=postgres
        - --hostname-strict=false
        - --hostname-strict-https=false
        - --http-enabled=true
        - --health-enabled=true
        - --metrics-enabled=true
        ports:
        - name: http
          containerPort: 8080
        - name: https
          containerPort: 8443
        env:
        - name: KC_DB
          value: postgres
        - name: KC_DB_URL
          value: jdbc:postgresql://keycloak-postgres:5432/keycloak
        - name: KC_DB_USERNAME
          value: keycloak
        - name: KC_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-postgres
              key: password
        - name: KEYCLOAK_ADMIN
          value: admin
        - name: KEYCLOAK_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-admin
              key: password
        - name: KC_PROXY
          value: edge  # Behind Envoy Gateway
        - name: KC_HOSTNAME_URL
          value: http://node1.local/auth  # External URL
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: keycloak
  namespace: keycloak
spec:
  selector:
    app: keycloak
  ports:
  - name: http
    port: 8080
    targetPort: 8080
  - name: https
    port: 8443
    targetPort: 8443
  type: ClusterIP
```

#### 3. Secrets (Create Manually)
```bash
# Create namespace
kubectl create namespace keycloak

# Create Postgres password
kubectl create secret generic keycloak-postgres \
  --from-literal=password='CHANGEME_PG_PASSWORD' \
  -n keycloak

# Create Keycloak admin password
kubectl create secret generic keycloak-admin \
  --from-literal=password='CHANGEME_ADMIN_PASSWORD' \
  -n keycloak
```

#### 4. Ingress Configuration
```yaml
# infrastructure/gateway/keycloak-httproute.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: keycloak
  namespace: keycloak
spec:
  parentRefs:
  - name: homelab-gateway
    namespace: envoy-gateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /auth
    backendRefs:
    - name: keycloak
      port: 8080
```

### Phase 2: Realm Configuration

#### Realm Setup (Manual via Admin UI)
1. **Access Keycloak**: `http://node1.local/auth`
2. **Login**: admin / <admin-password>
3. **Create Realm**: "homelab"
4. **Configure Realm Settings**:
   - Display name: "Homelab Services"
   - Enabled: Yes
   - User registration: Disabled (admin-managed)
   - Email as username: Yes
   - Login with email: Yes

#### Client Configuration: log-analyzer
```json
{
  "clientId": "log-analyzer",
  "name": "Log Analyzer API",
  "enabled": true,
  "clientAuthenticatorType": "client-secret",
  "secret": "GENERATE_AND_STORE_IN_SECRET",
  "redirectUris": [],
  "webOrigins": ["*"],
  "protocol": "openid-connect",
  "publicClient": false,
  "bearerOnly": true,
  "standardFlowEnabled": false,
  "implicitFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": true,
  "attributes": {
    "access.token.lifespan": "3600",
    "use.refresh.tokens": "false"
  }
}
```

#### Client Configuration: log-analyzer-cli
```json
{
  "clientId": "log-analyzer-cli",
  "name": "Log Analyzer CLI Client",
  "enabled": true,
  "publicClient": true,
  "redirectUris": ["http://localhost:*"],
  "webOrigins": ["http://localhost:*"],
  "protocol": "openid-connect",
  "standardFlowEnabled": false,
  "implicitFlowEnabled": false,
  "directAccessGrantsEnabled": true,
  "attributes": {
    "pkce.code.challenge.method": "S256"
  }
}
```

#### Roles Configuration
```
Realm Roles:
- sre-admin: Full access to all log analysis endpoints
- log-viewer: Read-only access to logs
- developer: Limited access with rate limiting

Client Roles (log-analyzer):
- logs:read: Read log data
- logs:analyze: Trigger LLM analysis
- prompts:manage: Create/update prompt templates
```

#### User Setup
```
Users:
1. admin@homelab.local
   - Roles: sre-admin
   - Purpose: Full administrative access

2. viewer@homelab.local
   - Roles: log-viewer
   - Purpose: Read-only testing

3. Service Account: log-analyzer-service
   - Roles: logs:read, logs:analyze
   - Purpose: Service-to-service communication
```

### Phase 3: Realm Export (GitOps)

Export realm configuration for version control:
```bash
# Export realm to JSON (via Keycloak Admin API)
kubectl exec -n keycloak deployment/keycloak -- \
  /opt/keycloak/bin/kc.sh export \
  --dir /tmp/export \
  --realm homelab \
  --users realm_file

# Copy export to local machine
kubectl cp keycloak/<pod-name>:/tmp/export/homelab-realm.json \
  infrastructure/keycloak/homelab-realm.json
```

Store in Git:
```
infrastructure/keycloak/
├── homelab-realm.json    # Full realm export
├── README.md             # Import instructions
└── import-job.yaml       # Kubernetes Job to import on deploy
```

---

## Log Analyzer Integration

### Phase 1: JWT Validation Middleware

#### 1. Dependencies
```toml
# workloads/log-analyzer/pyproject.toml
[project]
dependencies = [
    # ... existing dependencies
    "python-jose[cryptography]>=3.3.0",  # JWT validation
    "requests>=2.31.0",                   # Fetch JWKS
]
```

#### 2. Configuration
```python
# workloads/log-analyzer/src/log_analyzer/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings

    # OIDC Configuration
    oidc_enabled: bool = True
    keycloak_url: str = "http://keycloak.keycloak.svc.cluster.local:8080"
    keycloak_realm: str = "homelab"
    oidc_client_id: str = "log-analyzer"
    oidc_jwks_cache_ttl: int = 3600  # 1 hour

    # Development bypass
    dev_mode: bool = False  # Disable auth for local testing

    @property
    def keycloak_realm_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.keycloak_realm_url}/protocol/openid-connect/certs"

    @property
    def issuer_url(self) -> str:
        return self.keycloak_realm_url

    class Config:
        env_prefix = "LOG_ANALYZER_"
```

#### 3. JWKS Client (Public Key Caching)
```python
# workloads/log-analyzer/src/log_analyzer/auth/jwks.py
import time
import requests
from typing import Dict, Optional
from jose import jwk
from log_analyzer.config import settings

class JWKSClient:
    """Fetches and caches Keycloak's public keys for JWT validation."""

    def __init__(self):
        self._keys: Dict[str, jwk.Key] = {}
        self._last_fetch: float = 0
        self._ttl: int = settings.oidc_jwks_cache_ttl

    def get_signing_key(self, kid: str) -> Optional[jwk.Key]:
        """Get signing key by Key ID (kid), fetching from JWKS if needed."""
        if self._should_refresh():
            self._fetch_keys()

        return self._keys.get(kid)

    def _should_refresh(self) -> bool:
        """Check if cache has expired."""
        return time.time() - self._last_fetch > self._ttl

    def _fetch_keys(self):
        """Fetch JWKS from Keycloak and parse into Key objects."""
        try:
            response = requests.get(
                settings.jwks_url,
                timeout=5
            )
            response.raise_for_status()

            jwks = response.json()
            self._keys = {
                key["kid"]: jwk.construct(key)
                for key in jwks.get("keys", [])
                if key.get("use") == "sig"  # Signing keys only
            }
            self._last_fetch = time.time()

        except Exception as e:
            # Log error but don't crash - use cached keys if available
            print(f"Failed to fetch JWKS: {e}")

# Global singleton
jwks_client = JWKSClient()
```

#### 4. JWT Validation
```python
# workloads/log-analyzer/src/log_analyzer/auth/jwt.py
from typing import Dict, Optional
from jose import jwt, JWTError
from fastapi import HTTPException, status
from log_analyzer.config import settings
from log_analyzer.auth.jwks import jwks_client

class JWTValidator:
    """Validates and decodes JWT tokens from Keycloak."""

    @staticmethod
    def validate_token(token: str) -> Dict:
        """
        Validate JWT token and return decoded claims.

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Decode header to get Key ID (kid)
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing Key ID (kid)"
                )

            # Fetch public key from JWKS
            signing_key = jwks_client.get_signing_key(kid)
            if not signing_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Unknown signing key: {kid}"
                )

            # Validate and decode token
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=settings.oidc_client_id,
                issuer=settings.issuer_url,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )

            return claims

        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )

jwt_validator = JWTValidator()
```

#### 5. Authentication Middleware
```python
# workloads/log-analyzer/src/log_analyzer/auth/middleware.py
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from log_analyzer.config import settings
from log_analyzer.auth.jwt import jwt_validator

security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None
) -> dict:
    """
    Extract and validate JWT from Authorization header.

    Returns:
        User claims from validated token

    Raises:
        HTTPException: If token is missing or invalid
    """
    # Development bypass
    if settings.dev_mode:
        return {
            "sub": "dev-user",
            "preferred_username": "developer",
            "email": "dev@localhost",
            "realm_access": {"roles": ["sre-admin"]},
        }

    # Skip auth for health endpoints
    if request.url.path in ["/", "/health"]:
        return {"sub": "anonymous"}

    # Extract Bearer token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Validate and return claims
    claims = jwt_validator.validate_token(token)
    return claims
```

#### 6. Role-Based Authorization
```python
# workloads/log-analyzer/src/log_analyzer/auth/permissions.py
from typing import List
from fastapi import HTTPException, status, Depends
from log_analyzer.auth.middleware import get_current_user

def require_roles(required_roles: List[str]):
    """
    Dependency to enforce role-based access control.

    Usage:
        @app.get("/admin", dependencies=[Depends(require_roles(["sre-admin"]))])
    """
    async def check_roles(user: dict = Depends(get_current_user)):
        user_roles = user.get("realm_access", {}).get("roles", [])

        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {required_roles}"
            )

        return user

    return check_roles

# Convenience functions
def require_sre_admin():
    return require_roles(["sre-admin"])

def require_log_viewer():
    return require_roles(["log-viewer", "sre-admin"])
```

#### 7. Update Main Application
```python
# workloads/log-analyzer/src/log_analyzer/main.py
from fastapi import FastAPI, Depends
from log_analyzer.auth.middleware import get_current_user
from log_analyzer.auth.permissions import require_log_viewer

app = FastAPI(
    title="Log Analyzer API",
    description="Kubernetes log analysis with OIDC authentication",
    version="0.2.0"
)

# Public endpoints (no auth)
@app.get("/")
async def root():
    return {"status": "healthy", "service": "log-analyzer"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "log-analyzer", "version": "0.2.0"}

# Protected endpoints (require authentication)
@app.get("/prompts", dependencies=[Depends(get_current_user)])
async def list_prompts(user: dict = Depends(get_current_user)):
    # User context available for audit logging
    return await _list_prompts()

@app.post("/v1/analyze", dependencies=[Depends(require_log_viewer())])
async def analyze_logs(
    request: AnalyzeRequest,
    user: dict = Depends(get_current_user)
):
    # Log user action for audit trail
    logger.info(
        "Log analysis requested",
        extra={
            "user_id": user.get("sub"),
            "username": user.get("preferred_username"),
            "namespace": request.filters.namespace,
        }
    )
    return await _analyze_logs(request)
```

### Phase 2: Testing Infrastructure

#### 1. Mock Token Generator (for tests)
```python
# workloads/log-analyzer/tests/conftest.py
import jwt
from datetime import datetime, timedelta
from typing import Dict

def generate_test_token(
    claims: Dict = None,
    expired: bool = False
) -> str:
    """Generate a test JWT token for unit tests."""
    default_claims = {
        "iss": "http://keycloak.test/realms/homelab",
        "sub": "test-user-id",
        "aud": "log-analyzer",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "preferred_username": "testuser",
        "email": "test@example.com",
        "realm_access": {"roles": ["log-viewer"]},
    }

    if claims:
        default_claims.update(claims)

    if expired:
        default_claims["exp"] = datetime.utcnow() - timedelta(hours=1)

    # Sign with test secret (not used in production)
    return jwt.encode(default_claims, "test-secret", algorithm="HS256")

@pytest.fixture
def auth_headers():
    """Fixture providing valid auth headers for tests."""
    token = generate_test_token()
    return {"Authorization": f"Bearer {token}"}
```

#### 2. Integration Tests
```python
# workloads/log-analyzer/tests/test_auth.py
import pytest
from fastapi.testclient import TestClient

def test_health_endpoint_no_auth(client: TestClient):
    """Health endpoint should be publicly accessible."""
    response = client.get("/health")
    assert response.status_code == 200

def test_prompts_requires_auth(client: TestClient):
    """Prompts endpoint should require authentication."""
    response = client.get("/prompts")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]

def test_prompts_with_valid_token(client: TestClient, auth_headers):
    """Valid token should grant access to prompts."""
    response = client.get("/prompts", headers=auth_headers)
    assert response.status_code == 200

def test_analyze_requires_role(client: TestClient):
    """Analyze endpoint should require log-viewer role."""
    token = generate_test_token(claims={"realm_access": {"roles": []}})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/v1/analyze", headers=headers, json={...})
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]
```

---

## Development Workflow

### Local Development (Fast Feedback)

#### Option 1: Disable Auth Locally
```bash
# .env
LOG_ANALYZER_DEV_MODE=true
LOG_ANALYZER_OIDC_ENABLED=false

# Start local dev server
just dev

# All requests work without tokens
curl http://localhost:8000/v1/analyze -X POST -d '{...}'
```

**Pros**: Zero overhead, instant testing
**Cons**: Not testing real auth flow

#### Option 2: Mock Keycloak with Docker Compose
```yaml
# docker-compose.yml (local dev only)
services:
  keycloak-dev:
    image: quay.io/keycloak/keycloak:23.0
    command: start-dev
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
      KC_DB: dev-mem  # In-memory H2 database
    ports:
      - "8081:8080"
    volumes:
      - ./infrastructure/keycloak/homelab-realm.json:/opt/keycloak/data/import/realm.json
```

```bash
# Start Keycloak locally
docker-compose up -d keycloak-dev

# Point log-analyzer to local Keycloak
export LOG_ANALYZER_KEYCLOAK_URL=http://localhost:8081
export LOG_ANALYZER_OIDC_ENABLED=true

# Get test token
TOKEN=$(curl -X POST http://localhost:8081/realms/homelab/protocol/openid-connect/token \
  -d "client_id=log-analyzer-cli" \
  -d "username=viewer@homelab.local" \
  -d "password=test123" \
  -d "grant_type=password" \
  | jq -r '.access_token')

# Test with token
curl http://localhost:8000/v1/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -X POST -d '{...}'
```

**Pros**: Real auth flow, fast iteration
**Cons**: Requires Docker, additional setup

#### Option 3: Port-Forward to K8s Keycloak
```bash
# Start port-forward to cluster Keycloak
kubectl port-forward -n keycloak svc/keycloak 8081:8080 &

# Use cluster Keycloak for local dev
export LOG_ANALYZER_KEYCLOAK_URL=http://localhost:8081
just dev
```

**Pros**: Uses real cluster state, no Docker
**Cons**: Requires cluster running, slower

### Justfile Recipes

```makefile
# justfile additions

# Get token from local Keycloak
token-local:
    curl -s -X POST http://localhost:8081/realms/homelab/protocol/openid-connect/token \
      -d "client_id=log-analyzer-cli" \
      -d "username=viewer@homelab.local" \
      -d "password=test123" \
      -d "grant_type=password" \
      | jq -r '.access_token'

# Get token from cluster Keycloak
token-k8s:
    kubectl port-forward -n keycloak svc/keycloak 8081:8080 & \
    sleep 2 && \
    curl -s -X POST http://localhost:8081/realms/homelab/protocol/openid-connect/token \
      -d "client_id=log-analyzer-cli" \
      -d "username=admin@homelab.local" \
      -d "password=$(kubectl get secret -n keycloak keycloak-admin -o jsonpath='{.data.password}' | base64 -d)" \
      -d "grant_type=password" \
      | jq -r '.access_token'

# Analyze with auth (automatically get token)
analyze-auth namespace="llm":
    #!/usr/bin/env bash
    TOKEN=$(just token-local)
    curl -X POST http://localhost:8000/v1/analyze \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "time_range": {"start": "2025-01-01T00:00:00Z", "end": "2025-01-05T23:59:59Z"},
        "filters": {"namespace": "{{namespace}}", "severity": "error"},
        "limit": 10
      }' | jq

# Test token validation
test-auth:
    #!/usr/bin/env bash
    echo "Testing valid token..."
    TOKEN=$(just token-local)
    curl -I http://localhost:8000/prompts -H "Authorization: Bearer $TOKEN"

    echo "\nTesting invalid token..."
    curl -I http://localhost:8000/prompts -H "Authorization: Bearer invalid"

    echo "\nTesting missing token..."
    curl -I http://localhost:8000/prompts
```

### Integration Test Strategy

```python
# tests/test_integration_auth.py
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("KEYCLOAK_URL"), reason="Keycloak not available")
def test_full_auth_flow():
    """Test complete OIDC flow with real Keycloak."""
    keycloak_url = os.getenv("KEYCLOAK_URL")

    # 1. Get token from Keycloak
    token_response = requests.post(
        f"{keycloak_url}/realms/homelab/protocol/openid-connect/token",
        data={
            "client_id": "log-analyzer-cli",
            "username": "viewer@homelab.local",
            "password": "test123",
            "grant_type": "password",
        }
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    # 2. Decode token to inspect claims
    import jwt
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["iss"].endswith("/realms/homelab")
    assert "log-viewer" in claims["realm_access"]["roles"]

    # 3. Call log-analyzer API with token
    response = requests.get(
        "http://localhost:8000/prompts",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal**: Deploy Keycloak, create realm, configure clients

- [ ] Deploy PostgreSQL for Keycloak
- [ ] Deploy Keycloak to cluster
- [ ] Configure Envoy Gateway HTTPRoute for Keycloak
- [ ] Access Keycloak admin UI
- [ ] Create "homelab" realm
- [ ] Configure clients: log-analyzer (API), log-analyzer-cli (user)
- [ ] Create realm roles: sre-admin, log-viewer
- [ ] Create test users
- [ ] Export realm configuration to Git
- [ ] Document admin credentials in 1Password/secure vault

**Validation**:
```bash
# Access Keycloak UI
curl http://node1.local/auth

# Get token via client credentials
curl -X POST http://keycloak.keycloak.svc.cluster.local:8080/realms/homelab/protocol/openid-connect/token \
  -d "client_id=log-analyzer" \
  -d "client_secret=<secret>" \
  -d "grant_type=client_credentials"
```

### Phase 2: Log Analyzer Integration (Week 2)
**Goal**: Add JWT validation to FastAPI, protect endpoints

- [ ] Add python-jose dependency
- [ ] Implement JWKS client with caching
- [ ] Implement JWT validator
- [ ] Create authentication middleware
- [ ] Add role-based authorization helpers
- [ ] Update main.py to require auth on endpoints
- [ ] Add dev_mode bypass for local development
- [ ] Add audit logging with user context
- [ ] Update ConfigMap with KEYCLOAK_URL
- [ ] Deploy updated log-analyzer

**Validation**:
```bash
# Test without token (should fail)
curl -I http://log-analyzer.log-analyzer.svc.cluster.local:8000/prompts

# Test with token (should succeed)
TOKEN=$(just token-k8s)
curl http://log-analyzer.log-analyzer.svc.cluster.local:8000/prompts \
  -H "Authorization: Bearer $TOKEN"
```

### Phase 3: Testing Infrastructure (Week 2-3)
**Goal**: Enable fast feedback loops for development

- [ ] Add docker-compose.yml for local Keycloak
- [ ] Create mock token generator for unit tests
- [ ] Update unit tests to use mocked auth
- [ ] Create integration tests with real Keycloak
- [ ] Add Justfile recipes for token management
- [ ] Document local development workflows
- [ ] Add CI/CD checks for auth tests
- [ ] Create test fixtures for different user roles

**Validation**:
```bash
# Unit tests (mocked, fast)
just test

# Integration tests (real Keycloak)
docker-compose up -d keycloak-dev
just test-int

# Local dev with auth
docker-compose up -d keycloak-dev
just dev
just analyze-auth llm
```

### Phase 4: Advanced Features (Week 3-4)
**Goal**: Add production-ready patterns

- [ ] Implement token introspection (for opaque tokens)
- [ ] Add refresh token support
- [ ] Implement rate limiting per user
- [ ] Add audit logging to Loki with user IDs
- [ ] Create Grafana dashboard for auth metrics
- [ ] Add OpenTelemetry spans for auth operations
- [ ] Implement fine-grained permissions (claims-based)
- [ ] Add user impersonation for debugging (admin only)
- [ ] Document security best practices

**Validation**:
```bash
# View auth metrics in Grafana
# - Failed login attempts
# - Token validation errors
# - Unauthorized access attempts
# - User activity by role

# View auth traces in Tempo
# - JWT validation span
# - JWKS fetch span
# - Authorization decision span
```

### Phase 5: Documentation & Learning (Week 4)
**Goal**: Create educational resources

- [ ] Write comprehensive OIDC learning guide
- [ ] Document JWT structure with examples
- [ ] Create runbook for common auth issues
- [ ] Add troubleshooting guide
- [ ] Document security considerations
- [ ] Create video/screenshots of Keycloak admin UI
- [ ] Write blog post: "OIDC in Kubernetes"
- [ ] Present learnings to team/community

---

## Testing Strategy

### Unit Tests (Fast, Mocked)
```python
# tests/test_auth_unit.py

def test_jwt_validation_valid_token(mock_jwks):
    """Valid token should decode successfully."""
    token = generate_test_token()
    claims = jwt_validator.validate_token(token)
    assert claims["sub"] == "test-user-id"

def test_jwt_validation_expired_token(mock_jwks):
    """Expired token should raise 401."""
    token = generate_test_token(expired=True)
    with pytest.raises(HTTPException) as exc:
        jwt_validator.validate_token(token)
    assert exc.value.status_code == 401

def test_jwt_validation_invalid_audience(mock_jwks):
    """Token with wrong audience should fail."""
    token = generate_test_token(claims={"aud": "wrong-api"})
    with pytest.raises(HTTPException):
        jwt_validator.validate_token(token)

def test_require_roles_authorized():
    """User with required role should be authorized."""
    user = {"realm_access": {"roles": ["sre-admin"]}}
    # Should not raise
    require_roles(["sre-admin"])(user)

def test_require_roles_unauthorized():
    """User without required role should be denied."""
    user = {"realm_access": {"roles": ["log-viewer"]}}
    with pytest.raises(HTTPException) as exc:
        require_roles(["sre-admin"])(user)
    assert exc.value.status_code == 403
```

### Integration Tests (Real Keycloak)
```python
# tests/test_auth_integration.py

@pytest.mark.integration
def test_keycloak_token_flow(keycloak_client):
    """Test full OIDC flow with real Keycloak."""
    # Get token
    token = keycloak_client.get_token(
        username="viewer@homelab.local",
        password="test123"
    )
    assert token is not None

    # Validate token structure
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["iss"].endswith("/realms/homelab")
    assert claims["aud"] == "log-analyzer"

    # Use token in API request
    response = client.get(
        "/prompts",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

@pytest.mark.integration
def test_jwks_key_rotation(keycloak_client):
    """Test JWKS cache handles key rotation."""
    # Get token with key1
    token1 = keycloak_client.get_token(...)

    # Rotate keys in Keycloak
    keycloak_client.rotate_realm_keys()

    # Get token with key2
    token2 = keycloak_client.get_token(...)

    # Both tokens should validate
    jwt_validator.validate_token(token1)
    jwt_validator.validate_token(token2)
```

### End-to-End Tests
```bash
#!/bin/bash
# tests/e2e/test_auth_flow.sh

echo "E2E Auth Flow Test"
echo "=================="

# 1. Deploy Keycloak
echo "Deploying Keycloak..."
kubectl apply -k infrastructure/keycloak/
kubectl wait --for=condition=ready pod -l app=keycloak -n keycloak --timeout=120s

# 2. Import realm
echo "Importing realm..."
kubectl exec -n keycloak deployment/keycloak -- \
  /opt/keycloak/bin/kc.sh import --file /realm/homelab-realm.json

# 3. Deploy log-analyzer
echo "Deploying log-analyzer..."
kubectl apply -k workloads/log-analyzer/
kubectl wait --for=condition=ready pod -l app=log-analyzer -n log-analyzer --timeout=60s

# 4. Get token
echo "Getting access token..."
TOKEN=$(kubectl run curl-test --rm -i --restart=Never --image=curlimages/curl -- \
  -s -X POST http://keycloak.keycloak.svc.cluster.local:8080/realms/homelab/protocol/openid-connect/token \
  -d "client_id=log-analyzer-cli" \
  -d "username=viewer@homelab.local" \
  -d "password=test123" \
  -d "grant_type=password" \
  | jq -r '.access_token')

# 5. Test protected endpoint
echo "Testing protected endpoint..."
RESPONSE=$(kubectl run curl-test --rm -i --restart=Never --image=curlimages/curl -- \
  -s http://log-analyzer.log-analyzer.svc.cluster.local:8000/prompts \
  -H "Authorization: Bearer $TOKEN")

if echo "$RESPONSE" | jq -e '.[]' > /dev/null; then
  echo "✅ E2E test passed"
  exit 0
else
  echo "❌ E2E test failed"
  exit 1
fi
```

---

## Learning Objectives

### Hands-On OIDC Concepts

#### 1. **JWT Structure**
- **Activity**: Decode tokens at jwt.io
- **Observe**: Header (alg, kid), Payload (claims), Signature
- **Experiment**: Modify claims and see validation fail
- **Learn**: Why signatures prevent tampering

#### 2. **Token Lifecycle**
- **Activity**: Watch token expiration in real-time
- **Observe**: Token works, then fails after exp timestamp
- **Experiment**: Set different TTLs (5min vs 1hour)
- **Learn**: Balance between security and user experience

#### 3. **JWKS and Key Rotation**
- **Activity**: Rotate Keycloak keys, observe JWKS changes
- **Observe**: Multiple keys with different `kid` values
- **Experiment**: Cache invalidation in JWKSClient
- **Learn**: Zero-downtime key rotation

#### 4. **Claims and RBAC**
- **Activity**: Create users with different roles
- **Observe**: realm_access.roles in token
- **Experiment**: Add/remove roles, test access
- **Learn**: Claims-based authorization patterns

#### 5. **OIDC Flows**
- **Activity**: Implement all three flows (client credentials, password, auth code)
- **Observe**: Different use cases (service-to-service, CLI, web app)
- **Experiment**: PKCE for authorization code flow
- **Learn**: When to use each flow

### Kubernetes Integration

#### 1. **Service-to-Service Auth**
- **Pattern**: Service accounts with client credentials
- **Learn**: How microservices authenticate to each other
- **Implement**: log-analyzer → LLM service with OIDC

#### 2. **Secrets Management**
- **Pattern**: Keycloak client secrets in Kubernetes Secrets
- **Learn**: Secret rotation without downtime
- **Implement**: External Secrets Operator (optional)

#### 3. **Network Policies**
- **Pattern**: Restrict Keycloak access to specific namespaces
- **Learn**: Defense in depth (network + auth)
- **Implement**: NetworkPolicy for keycloak namespace

#### 4. **Observability**
- **Pattern**: Trace auth operations with OpenTelemetry
- **Learn**: Debug auth failures with distributed tracing
- **Implement**: Custom spans for JWT validation

### Security Best Practices

#### 1. **Token Storage**
- ❌ **Bad**: Store tokens in localStorage (XSS risk)
- ✅ **Good**: HTTP-only cookies, memory only
- **Learn**: OWASP token storage recommendations

#### 2. **Token Validation**
- ❌ **Bad**: Decode without signature verification
- ✅ **Good**: Verify signature, iss, aud, exp, nbf
- **Learn**: Why each claim matters

#### 3. **Least Privilege**
- ❌ **Bad**: Single admin role for everything
- ✅ **Good**: Fine-grained roles per resource
- **Learn**: RBAC vs ABAC tradeoffs

#### 4. **Audit Logging**
- ❌ **Bad**: No logging of auth events
- ✅ **Good**: Log all auth attempts with user context
- **Learn**: Security incident investigation

---

## References

### OIDC Specifications
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [JSON Web Token (JWT) RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
- [JSON Web Signature (JWS) RFC 7515](https://datatracker.ietf.org/doc/html/rfc7515)

### Keycloak Documentation
- [Keycloak Server Administration](https://www.keycloak.org/docs/latest/server_admin/)
- [Keycloak on Kubernetes](https://www.keycloak.org/getting-started/getting-started-kube)
- [Keycloak Docker Images](https://quay.io/repository/keycloak/keycloak)
- [Keycloak Operator](https://www.keycloak.org/operator/installation)

### Python Libraries
- [python-jose](https://github.com/mpdavis/python-jose) - JWT validation
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) - OAuth2 integration
- [Authlib](https://docs.authlib.org/en/latest/) - OIDC client library (alternative)

### Kubernetes Patterns
- [Kubernetes Authentication](https://kubernetes.io/docs/reference/access-authn-authz/authentication/)
- [Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

### Best Practices
- [OWASP JWT Security](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
- [OIDC Best Practices](https://openid.net/specs/openid-connect-basic-1_0.html#BestPractices)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)

### Tools
- [jwt.io](https://jwt.io/) - JWT decoder and validator
- [oauth.tools](https://oauth.tools/) - OAuth 2.0/OIDC playground
- [Keycloak Admin CLI](https://www.keycloak.org/docs/latest/server_admin/#admin-cli) - Command-line management

---

## Next Steps

1. **Review this plan** and ask questions about any unclear concepts
2. **Set up Keycloak** locally with Docker Compose for experimentation
3. **Create a test realm** and explore the admin UI
4. **Generate tokens** manually and decode them at jwt.io
5. **Begin Phase 1** implementation when ready

This implementation will provide production-ready authentication patterns while maintaining the fast feedback loops essential for effective learning and development!
