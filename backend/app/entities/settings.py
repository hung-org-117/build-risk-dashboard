"""Application settings entity stored in MongoDB."""

from typing import Optional

from pydantic import Field

from .base import BaseEntity

DEFAULT_SONARQUBE_CONFIG = """
sonar.sources=.
sonar.sourceEncoding=UTF-8
sonar.scm.disabled=true
sonar.java.binaries=.

# Exclude non-source directories and files
sonar.exclusions=**/.git/**,**/.hg/**,**/.svn/**,**/node_modules/**,**/vendor/**,**/dist/**,**/build/**,**/target/**,**/out/**,**/.next/**,**/.nuxt/**,**/.cache/**,**/__pycache__/**,**/*.min.js,**/*.min.css,**/.m2/**,**/.gradle/**,**/.npm/**,**/.yarn/**,**/.pnpm/**,**/coverage/**,**/.nyc_output/**,**/.pytest_cache/**,**/.tox/**,**/.venv/**,**/venv/**,**/env/**,**/.env/**,**/virtualenv/**,**/.idea/**,**/.vscode/**,**/.eclipse/**,**/logs/**,**/log/**,**/tmp/**,**/temp/**,**/.DS_Store,**/Thumbs.db,**/*.lock,**/package-lock.json,**/yarn.lock,**/pnpm-lock.yaml,**/poetry.lock,**/Pipfile.lock,**/go.sum,**/Cargo.lock,**/composer.lock,**/Gemfile.lock

sonar.inclusions=**/*
"""

DEFAULT_TRIVY_CONFIG = """
timeout: 10m

severity:
  - CRITICAL
  - HIGH
  - MEDIUM
  - LOW
  - UNKNOWN

scanners:
  - vuln
  - misconfig
  # Note: 'secret' scanner disabled for performance - it's very slow
  # - secret
  - license

list-all-pkgs: true

ignore-unfixed: false

format: json
output: trivy-result.json

# Performance optimizations
# Skip Java DB update to avoid Maven dependency resolution timeouts
skip-java-db-update: true

# Offline mode - skip downloading vulnerability DB during scan
# (assumes Trivy server has the DB)
offline-scan: true

scan:
  skip-dirs:
    # Package managers / dependencies
    - node_modules
    - vendor
    - .npm
    - .yarn
    - .pnpm
    - .m2
    - .gradle
    - .ivy2
    - .sbt
    - .cargo
    - .rustup
    # Version control
    - .git
    - .hg
    - .svn
    # Build outputs
    - dist
    - build
    - target
    - out
    - bin
    - obj
    - .next
    - .nuxt
    - .output
    # Cache / temp
    - .cache
    - __pycache__
    - .pytest_cache
    - .tox
    - .mypy_cache
    - .ruff_cache
    - coverage
    - .nyc_output
    - tmp
    - temp
    - logs
    - log
    # Virtual environments
    - .venv
    - venv
    - env
    - .env
    - virtualenv
    # IDE / Editor
    - .idea
    - .vscode
    - .eclipse
    # Test data / fixtures
    - testdata
    - test-fixtures
    - fixtures
    - mocks

  skip-files:
    - "**/*.min.js"
    - "**/*.min.css"
    - "**/*.map"
    - "**/*.png"
    - "**/*.jpg"
    - "**/*.jpeg"
    - "**/*.gif"
    - "**/*.ico"
    - "**/*.svg"
    - "**/*.webp"
    - "**/*.pdf"
    - "**/*.zip"
    - "**/*.tar"
    - "**/*.tar.gz"
    - "**/*.tgz"
    - "**/*.gz"
    - "**/*.bz2"
    - "**/*.xz"
    - "**/*.rar"
    - "**/*.7z"
    - "**/*.jar"
    - "**/*.war"
    - "**/*.ear"
    - "**/*.exe"
    - "**/*.dll"
    - "**/*.so"
    - "**/*.dylib"
    - "**/*.woff"
    - "**/*.woff2"
    - "**/*.ttf"
    - "**/*.eot"
    - "**/*.otf"
    - "**/*.mp3"
    - "**/*.mp4"
    - "**/*.avi"
    - "**/*.mov"
    - "**/*.wmv"
    - "**/*.flv"
    - "**/*.webm"
    - "**/package-lock.json"
    - "**/yarn.lock"
    - "**/pnpm-lock.yaml"
    - "**/poetry.lock"
    - "**/Pipfile.lock"
    - "**/go.sum"
    - "**/Cargo.lock"
    - "**/composer.lock"
    - "**/Gemfile.lock"
"""


class CircleCISettings(BaseEntity):
    """CircleCI integration settings."""

    base_url: str = "https://circleci.com/api/v2"
    token_encrypted: Optional[str] = None


class TravisCISettings(BaseEntity):
    """Travis CI integration settings."""

    base_url: str = "https://api.travis-ci.com"
    token_encrypted: Optional[str] = None


class SonarQubeSettings(BaseEntity):
    """
    SonarQube settings.

    - Connection: host_url, token
    - Auth: webhook_secret (for callback verification)
    - Default Config: default_config (sonar-project.properties content)
    """

    # Connection settings
    host_url: str = "http://localhost:9000"
    token_encrypted: Optional[str] = None

    # Webhook auth
    webhook_secret_encrypted: Optional[str] = None

    # Default config content (editable in UI)
    # Used when user doesn't provide custom config during scan
    default_config: str = Field(default=DEFAULT_SONARQUBE_CONFIG)


class TrivySettings(BaseEntity):
    """
    Trivy settings.

    - Connection: server_url (for client/server mode, optional)
    - Default Config: default_config (trivy.yaml content)
    """

    # Connection settings (optional - for server mode)
    server_url: str = "http://localhost:4954"

    # Default config content (editable in UI)
    # Used when user doesn't provide custom config during scan
    default_config: str = Field(default=DEFAULT_TRIVY_CONFIG)


class ApplicationSettings(BaseEntity):
    """Main application settings document - UI-editable configs only."""

    # Override id to allow string ID for singleton document
    id: str = Field("app_settings_v1", alias="_id")

    settings_version: int = 1

    # CI Provider settings
    circleci: CircleCISettings = Field(default_factory=CircleCISettings)
    travis: TravisCISettings = Field(default_factory=TravisCISettings)

    # Scan tool settings
    sonarqube: SonarQubeSettings = Field(default_factory=SonarQubeSettings)
    trivy: TrivySettings = Field(default_factory=TrivySettings)
