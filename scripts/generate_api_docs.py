"""
Enhanced API documentation generator for the Contract Processing System.
Implements comprehensive documentation generation with security, versioning,
and rate limiting details using FastAPI's OpenAPI schema.

Version: 1.0
"""

# External imports with version specifications
import json  # built-in
from pathlib import Path  # built-in
import typer  # typer v0.7.0
import yaml  # pyyaml v6.0.1
from jinja2 import Environment, FileSystemLoader  # jinja2 v3.1.2
import logging
from datetime import datetime

# Internal imports
from app.main import app, openapi, middleware
from app.api.v1.router import api_router

# Configure logging
logger = logging.getLogger(__name__)

# Global constants
OUTPUT_DIR = Path('docs/api')
TEMPLATE_DIR = Path('templates/docs')
VERSION = '1.0.0'

# Initialize CLI app
app = typer.Typer(help='API Documentation Generator')

def generate_openapi_spec() -> dict:
    """
    Generates enhanced OpenAPI specification with comprehensive security,
    versioning, and rate limiting details.

    Returns:
        dict: Enhanced OpenAPI specification with complete documentation
    """
    try:
        # Get base OpenAPI schema
        base_spec = app.openapi()

        # Add enhanced security schemes
        security_schemes = {
            "OAuth2": {
                "type": "oauth2",
                "flows": {
                    "password": {
                        "tokenUrl": "/api/v1/auth/token",
                        "refreshUrl": "/api/v1/auth/refresh",
                        "scopes": {
                            "read": "Read access",
                            "write": "Write access"
                        }
                    }
                }
            },
            "JWT": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        }
        base_spec["components"]["securitySchemes"] = security_schemes

        # Add rate limiting information
        rate_limiting = {
            "description": "API Rate Limiting",
            "headers": {
                "X-RateLimit-Limit": {
                    "description": "Request limit per minute",
                    "schema": {"type": "integer", "default": 100}
                },
                "X-RateLimit-Remaining": {
                    "description": "Remaining requests for the time window",
                    "schema": {"type": "integer"}
                },
                "X-RateLimit-Reset": {
                    "description": "Time until rate limit reset",
                    "schema": {"type": "integer"}
                }
            }
        }
        base_spec["components"]["responses"]["RateLimitExceeded"] = rate_limiting

        # Add versioning information
        base_spec["info"]["version"] = VERSION
        base_spec["info"]["x-api-lifecycle"] = {
            "deprecation": {
                "policy": "12 months notice",
                "supported_versions": ["v1"],
                "sunset_schedule": {
                    "v1": None  # No sunset date yet
                }
            }
        }

        return base_spec

    except Exception as e:
        logger.error(f"Failed to generate OpenAPI spec: {str(e)}")
        raise

def enhance_documentation(openapi_spec: dict) -> dict:
    """
    Enhances OpenAPI specification with additional enterprise-grade documentation features.

    Args:
        openapi_spec: Base OpenAPI specification

    Returns:
        dict: Enhanced specification with enterprise features
    """
    try:
        # Add comprehensive error responses
        error_responses = {
            "400": {
                "description": "Bad Request - Invalid input parameters",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {"type": "string"},
                                        "message": {"type": "string"},
                                        "details": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "401": {"description": "Unauthorized - Authentication required"},
            "403": {"description": "Forbidden - Insufficient permissions"},
            "429": {"description": "Too Many Requests - Rate limit exceeded"}
        }

        # Add error responses to all endpoints
        for path in openapi_spec["paths"].values():
            for operation in path.values():
                operation["responses"].update(error_responses)

        # Add authentication flows
        openapi_spec["components"]["securitySchemes"]["OAuth2"]["flows"]["password"].update({
            "tokenLifetime": "60 minutes",
            "refreshTokenLifetime": "7 days",
            "securityLevel": "high"
        })

        # Add performance considerations
        openapi_spec["info"]["x-performance"] = {
            "rate_limits": {
                "default": "100 requests per minute",
                "burst": "120 requests per minute",
                "sustained": "1000 requests per hour"
            },
            "timeouts": {
                "read": "30 seconds",
                "write": "60 seconds"
            }
        }

        return openapi_spec

    except Exception as e:
        logger.error(f"Failed to enhance documentation: {str(e)}")
        raise

def save_documentation(api_spec: dict, output_dir: str) -> None:
    """
    Saves API documentation in multiple formats with enhanced formatting and accessibility.

    Args:
        api_spec: Enhanced API specification
        output_dir: Output directory path
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save OpenAPI JSON
        json_path = output_path / 'openapi.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(api_spec, f, indent=2, ensure_ascii=False)

        # Save OpenAPI YAML
        yaml_path = output_path / 'openapi.yaml'
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(api_spec, f, allow_unicode=True, sort_keys=False)

        # Generate HTML documentation
        env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=True
        )
        template = env.get_template('api.html.j2')
        html_content = template.render(
            spec=api_spec,
            generated_at=datetime.utcnow().isoformat(),
            version=VERSION
        )

        html_path = output_path / 'index.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Documentation generated successfully in {output_dir}")

    except Exception as e:
        logger.error(f"Failed to save documentation: {str(e)}")
        raise

@app.command()
def main(
    output_dir: str = str(OUTPUT_DIR),
    format: str = "all"
) -> None:
    """
    Main CLI entry point for documentation generation.

    Args:
        output_dir: Output directory for documentation
        format: Output format (json, yaml, html, all)
    """
    try:
        logger.info("Starting API documentation generation")

        # Generate enhanced OpenAPI spec
        api_spec = generate_openapi_spec()
        logger.info("Generated base OpenAPI specification")

        # Add enterprise documentation features
        enhanced_spec = enhance_documentation(api_spec)
        logger.info("Enhanced documentation with enterprise features")

        # Save documentation
        save_documentation(enhanced_spec, output_dir)
        logger.info(f"Documentation saved to {output_dir}")

    except Exception as e:
        logger.error(f"Documentation generation failed: {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()