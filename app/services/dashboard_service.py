"""
Service module for dashboard metrics calculation including contract analytics,
performance monitoring, and caching capabilities.

Version: 1.0
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import structlog
from cachetools import TTLCache
from app.schemas.dashboard import (
    ContractStatusCount,
    ContractStatusDetails,
    DashboardMetrics,
    ActiveContractsMetrics,
    ProcessingQueueMetrics,
    PendingReviewMetrics,
    POsGeneratedMetrics,
    StatusDistribution
)

# Configure logging
logger = structlog.get_logger(__name__)


class DashboardService:
    """Service class for dashboard metrics calculation."""

    def __init__(self, db):
        """Initialize dashboard service with database connection."""
        self.db = db
        # Initialize cache with 5-minute TTL
        self.metrics_cache = TTLCache(maxsize=100, ttl=300)
        # Initialize performance tracking
        self.processing_times = []
        self.processing_failures = 0
        self.last_refresh = datetime.utcnow()

    async def _get_status_counts(self, user_id: str) -> ContractStatusCount:
        """Calculate contract status counts using MongoDB aggregation."""
        try:
            # role = await self.get_user_role(user_id)
            # match_stage = {} if role == "ADMIN" else {"metadata.uploaded_by": user_id}
            match_stage = {}
            # Pipeline for counting POs from both validated/completed contracts and purchase_orders
            # Main pipeline for other metrics
            # Main pipeline for contract metrics
            pipeline = [
                {"$match": match_stage},
                {
                    "$facet": {
                        "active_contracts": [
                            {
                                "$match": {
                                    "status": {
                                        "$nin": ["COMPLETED", "FAILED", "VALIDATED"]
                                    }
                                }
                            },
                            {
                                "$group": {
                                    "_id": None,
                                    "count": {"$sum": 1},
                                    "avg_age": {
                                        "$avg": {
                                            "$divide": [
                                                {"$subtract": [
                                                    "$$NOW", "$created_at"]},
                                                86400000  # Convert ms to days
                                            ]
                                        }
                                    },
                                    "oldest_contract": {"$min": "$created_at"}
                                }
                            }
                        ],
                        "processing_queue": [
                            {
                                "$match": {
                                    "status": {"$in": ["PENDING", "PROCESSING"]}
                                }
                            },
                            {
                                "$group": {
                                    "_id": None,
                                    "count": {"$sum": 1},
                                    "processing_times": {
                                        "$push": {
                                            "$subtract": [
                                                "$updated_at",
                                                "$created_at"
                                            ]
                                        }
                                    }
                                }
                            }
                        ],
                        "pending_review": [
                            {
                                "$match": {
                                    "status": "VALIDATION_REQUIRED"
                                }
                            },
                            {
                                "$group": {
                                    "_id": None,
                                    "count": {"$sum": 1},
                                    "urgent_reviews": {
                                        "$sum": {
                                            "$cond": [
                                                {
                                                    "$gt": [
                                                        {"$subtract": [
                                                            "$$NOW", "$updated_at"]},
                                                        86400000  # 24 hours in milliseconds
                                                    ]
                                                },
                                                1,
                                                0
                                            ]
                                        }
                                    }
                                }
                            }
                        ],
                        "total": [
                            {
                                "$group": {
                                    "_id": None,
                                    "count": {"$sum": 1}
                                }
                            }
                        ],
                        "failed": [
                            {
                                "$match": {
                                    "status": "FAILED"
                                }
                            },
                            {
                                "$group": {
                                    "_id": None,
                                    "count": {"$sum": 1}
                                }
                            }
                        ]
                    }
                }
            ]

            # Simple pipeline for PO metrics - just count all entries
            po_pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "count": {"$sum": 1}  # Total count of POs
                    }
                }
            ]

            # Execute both pipelines
            results = await self.db.contracts.aggregate(pipeline).to_list(length=1)
            po_results = await self.db.purchase_orders.aggregate(po_pipeline).to_list(length=1)

            if not results:
                return self._create_empty_metrics()

            result = results[0]
            po_result = po_results[0] if po_results else {}

            # Extract metrics
            active = result.get('active_contracts', [{}])[
                0] if result.get('active_contracts') else {}
            processing = result.get('processing_queue', [{}])[
                0] if result.get('processing_queue') else {}
            review = result.get('pending_review', [{}])[
                0] if result.get('pending_review') else {}
            total = result.get('total', [{}])[0] if result.get('total') else {}
            failed = result.get('failed', [{}])[
                0] if result.get('failed') else {}

            # Get total PO count
            total_pos = po_result.get('count', 0)

            # Calculate metrics
            avg_processing_time = (
                sum(self.processing_times) / len(self.processing_times)
                if self.processing_times else 0.0
            )

            success_rate = (
                (len(self.processing_times) - self.processing_failures)
                / len(self.processing_times) * 100
                if self.processing_times else 100.0
            )

            return ContractStatusCount(
                active_contracts=ActiveContractsMetrics(
                    count=active.get('count', 0),
                    average_age=round(active.get('avg_age', 0), 2),
                    oldest_contract=active.get('oldest_contract')
                ),
                processing_queue=ProcessingQueueMetrics(
                    count=processing.get('count', 0),
                    average_processing_time=round(avg_processing_time, 2),
                    success_rate=round(success_rate, 2),
                    failures=failed.get('count', 0)
                ),
                pending_review=PendingReviewMetrics(
                    count=review.get('count', 0),
                    urgent_reviews=review.get('urgent_reviews', 0),
                    average_wait_time=0.0
                ),
                pos_generated=POsGeneratedMetrics(
                    count=total_pos,  # Simply use total PO count
                    total_pos=total_pos,  # Same as count in this case
                    average_pos_per_contract=1.0  # Since we're not tracking unique contracts
                ),
                total_contracts=total.get('count', 0),
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.error("Failed to get status counts",
                         error=str(e), user_id=user_id)
            raise

    def _create_empty_metrics(self) -> ContractStatusCount:
        """Create empty metrics response when no data is available."""
        return ContractStatusCount(
            active_contracts=ActiveContractsMetrics(
                count=0,
                average_age=0.0,
                oldest_contract=None
            ),
            processing_queue=ProcessingQueueMetrics(
                count=0,
                average_processing_time=0.0,
                success_rate=100.0,
                failures=0
            ),
            pending_review=PendingReviewMetrics(
                count=0,
                urgent_reviews=0,
                average_wait_time=0.0
            ),
            pos_generated=POsGeneratedMetrics(
                count=0,
                total_pos=0,
                average_pos_per_contract=0.0
            ),
            total_contracts=0,
            last_updated=datetime.utcnow()
        )

    async def get_status_distribution(self, user_id: str, days: int = 30) -> StatusDistribution:
        """Calculate status distribution over time."""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "created_at": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$created_at"
                            }
                        },
                        "active": {
                            "$sum": {
                                "$cond": [
                                    {"$not": [
                                        {"$in": ["$status", ["COMPLETED", "FAILED"]]}]},
                                    1,
                                    0
                                ]
                            }
                        },
                        "processing": {
                            "$sum": {
                                "$cond": [
                                    {"$in": ["$status", [
                                        "PENDING", "PROCESSING"]]},
                                    1,
                                    0
                                ]
                            }
                        },
                        "review": {
                            "$sum": {
                                "$cond": [{"$eq": ["$status", "VALIDATION_REQUIRED"]}, 1, 0]
                            }
                        },
                        "completed": {
                            "$sum": {
                                "$cond": [{"$eq": ["$status", "COMPLETED"]}, 1, 0]
                            }
                        }
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            results = await self.db.contracts.aggregate(pipeline).to_list(None)

            # Generate all dates in range
            dates = []
            active = []
            processing = []
            review = []
            completed = []

            current_date = start_date
            results_dict = {r["_id"]: r for r in results}

            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                dates.append(date_str)

                result = results_dict.get(date_str, {})
                active.append(result.get("active", 0))
                processing.append(result.get("processing", 0))
                review.append(result.get("review", 0))
                completed.append(result.get("completed", 0))

                current_date += timedelta(days=1)

            return StatusDistribution(
                time_periods=dates,
                active_contracts=active,
                processing_queue=processing,
                pending_review=review,
                pos_generated=completed
            )

        except Exception as e:
            logger.error("Failed to get status distribution", error=str(e))
            raise

    async def get_dashboard_metrics(self, user_id: str) -> DashboardMetrics:
        """Get comprehensive dashboard metrics with caching."""
        try:
            cache_key = f"dashboard_metrics_{user_id}"
            # Check cache first
            if cache_key in self.metrics_cache:
                return self.metrics_cache[cache_key]

            # Calculate all metrics
            status_counts = await self._get_status_counts(user_id)
            status_distribution = await self.get_status_distribution(user_id)

            metrics = DashboardMetrics(
                status_counts=status_counts,
                status_distribution=status_distribution
            )

            # Update cache
            self.metrics_cache[cache_key] = metrics

            return metrics

        except Exception as e:
            logger.error("Failed to get dashboard metrics",
                         error=str(e), user_id=user_id)
            raise

    async def get_contracts_by_status(
        self,
        status: str,
        user_id: str,
        skip: int = 0,
        limit: int = 10
    ) -> List[ContractStatusDetails]:
        """Get filtered and paginated contract list by status."""
        try:
            # Define status mappings
            status_mappings = {
                'active_contracts': {'$nin': ['COMPLETED', 'FAILED']},
                'processing_queue': {'$in': ['PENDING', 'PROCESSING']},
                'pending_review': 'VALIDATION_REQUIRED',
                'pos_generated': 'COMPLETED'
            }

            if status not in status_mappings:
                raise ValueError(f"Invalid status filter: {status}")

            # Build query
            query = {
                'user_id': user_id,
                'status': status_mappings[status]
            }

            # Execute query with pagination
            cursor = self.db.contracts.find(query)\
                .sort('created_at', -1)\
                .skip(skip)\
                .limit(limit)

            contracts = await cursor.to_list(length=limit)
            now = datetime.utcnow()

            # Transform contract documents
            return [
                ContractStatusDetails(
                    id=str(contract['_id']),
                    file_path=contract['file_path'],
                    status=contract['status'],
                    created_at=contract['created_at'],
                    updated_at=contract['updated_at'],
                    metadata=contract.get('metadata', {}),
                    po_numbers=contract.get('po_numbers', []),
                    age_in_days=(now - contract['created_at']).days,
                    processing_time=self._calculate_processing_time(contract),
                    review_wait_time=self._calculate_review_wait_time(contract)
                )
                for contract in contracts
            ]

        except ValueError as e:
            raise
        except Exception as e:
            logger.error(
                "Failed to get contracts by status",
                error=str(e),
                status=status,
                user_id=user_id
            )
            raise

    def _calculate_processing_time(self, contract: Dict) -> Optional[float]:
        """Calculate processing time in minutes."""
        if not contract.get('processing_start'):
            return None
        end_time = contract.get('processed_at', datetime.utcnow())
        return (end_time - contract['processing_start']).total_seconds() / 60

    def _calculate_review_wait_time(self, contract: Dict) -> Optional[float]:
        """Calculate review wait time in hours."""
        if contract['status'] != 'VALIDATION_REQUIRED':
            return None
        return (datetime.utcnow() - contract['updated_at']).total_seconds() / 3600

    async def refresh_metrics_cache(self, user_id: str) -> None:
        """
        Force refresh of metrics cache.

        Args:
            user_id: User ID for filtering contracts
        """
        try:
            # Recalculate all metrics
            status_counts = await self._get_status_counts(user_id)
            status_distribution = await self.get_status_distribution(user_id)

            metrics = DashboardMetrics(
                status_counts=status_counts,
                status_distribution=status_distribution
            )

            # Update cache
            cache_key = f"dashboard_metrics_{user_id}"
            self.metrics_cache[cache_key] = metrics

            # Update refresh timestamp
            self.last_refresh = datetime.utcnow()

            logger.info(
                "Successfully refreshed metrics cache",
                user_id=user_id,
                timestamp=self.last_refresh
            )

        except Exception as e:
            logger.error(
                "Failed to refresh metrics cache",
                error=str(e),
                user_id=user_id
            )
            raise
