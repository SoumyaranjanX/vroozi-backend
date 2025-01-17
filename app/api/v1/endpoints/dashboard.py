"""
FastAPI router endpoints for dashboard metrics providing comprehensive contract 
status overview with monitoring and caching capabilities.

Version: 1.0
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Dict, List, Optional
import logging
import structlog
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram

# Internal imports
from app.core.security import RequiresRole
from app.core.dependencies import get_dashboard_service
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import (
    DashboardMetrics,
    ContractStatusDetails,
    StatusDistribution
)

# Initialize router
router = APIRouter(tags=['dashboard'])

# Configure logging
logger = structlog.get_logger(__name__)

# Prometheus metrics
DASHBOARD_REQUESTS = Counter(
    'dashboard_requests_total',
    'Total number of dashboard API requests',
    ['endpoint', 'method']
)

DASHBOARD_LATENCY = Histogram(
    'dashboard_request_duration_seconds',
    'Dashboard endpoint latency in seconds',
    ['endpoint']
)


@router.get(
    "/metrics",
    response_model=DashboardMetrics,
    description="Get comprehensive dashboard metrics"
)
async def get_dashboard_metrics(
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
    background_tasks: BackgroundTasks = None,
    refresh: bool = Query(False, description="Force refresh cache")
) -> DashboardMetrics:
    """
    Get comprehensive dashboard metrics including contract statuses,
    processing times, and status distribution.

    Args:
        current_user: Current authenticated user
        dashboard_service: Dashboard service instance
        background_tasks: Background tasks handler
        refresh: Force refresh cache flag

    Returns:
        DashboardMetrics: Comprehensive dashboard metrics
    """
    try:
        start_time = datetime.utcnow()

        # Record request metric
        DASHBOARD_REQUESTS.labels(
            endpoint='/dashboard/metrics',
            method='GET'
        ).inc()

        if refresh:
            # If refresh is requested, force refresh the cache
            await dashboard_service.refresh_metrics_cache(current_user['id'])

        # Get metrics from service
        metrics = await dashboard_service.get_dashboard_metrics(current_user['id'])

        # Schedule background refresh for next time if needed
        if background_tasks and not refresh:
            background_tasks.add_task(
                dashboard_service.refresh_metrics_cache,
                current_user['id']
            )

        # Record latency
        DASHBOARD_LATENCY.labels(
            endpoint='/dashboard/metrics'
        ).observe((datetime.utcnow() - start_time).total_seconds())

        return metrics

    except Exception as e:
        logger.error(f"Dashboard metrics failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard metrics"
        )


@router.get(
    "/contracts/{status}",
    response_model=List[ContractStatusDetails],
    description="Get detailed contract list by status"
)
async def get_contracts_by_status(
    status: str,
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
    page: int = Query(1, gt=0),
    limit: int = Query(10, gt=0, le=100)
) -> List[ContractStatusDetails]:
    """
    Get paginated list of contracts filtered by status category.

    Args:
        status: Status category to filter by
        current_user: Current authenticated user
        dashboard_service: Dashboard service instance
        page: Page number for pagination
        limit: Items per page

    Returns:
        List[ContractStatusDetails]: Filtered contract list
    """
    try:
        start_time = datetime.utcnow()

        # Record request metric
        DASHBOARD_REQUESTS.labels(
            endpoint='/dashboard/contracts/status',
            method='GET'
        ).inc()

        contracts = await dashboard_service.get_contracts_by_status(
            status=status,
            user_id=current_user['id'],
            skip=(page - 1) * limit,
            limit=limit
        )

        # Record latency
        DASHBOARD_LATENCY.labels(
            endpoint='/dashboard/contracts/status'
        ).observe((datetime.utcnow() - start_time).total_seconds())

        return contracts

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get contracts by status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve contracts"
        )


@router.get(
    "/status-distribution",
    response_model=StatusDistribution,
    description="Get contract status distribution over time"
)
async def get_status_distribution(
    current_user: Dict = Depends(RequiresRole(['ADMIN', 'CONTRACT_MANAGER'])),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
    days: int = Query(30, gt=0, le=365)
) -> StatusDistribution:
    """
    Get contract status distribution over specified time period.

    Args:
        current_user: Current authenticated user
        dashboard_service: Dashboard service instance
        days: Number of days to analyze

    Returns:
        StatusDistribution: Status distribution metrics
    """
    try:
        start_time = datetime.utcnow()

        # Record request metric
        DASHBOARD_REQUESTS.labels(
            endpoint='/dashboard/status-distribution',
            method='GET'
        ).inc()

        distribution = await dashboard_service.get_status_distribution(
            user_id=current_user['id'],
            days=days
        )

        # Record latency
        DASHBOARD_LATENCY.labels(
            endpoint='/dashboard/status-distribution'
        ).observe((datetime.utcnow() - start_time).total_seconds())

        return distribution

    except Exception as e:
        logger.error(f"Failed to get status distribution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate status distribution"
        )

# Export router
__all__ = ['router']
