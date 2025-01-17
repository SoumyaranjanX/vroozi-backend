"""
Pydantic models for dashboard data validation and serialization.
Implements comprehensive schema definitions for dashboard metrics and analytics.

Version: 1.1
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime


class ActiveContractsMetrics(BaseModel):
    """Schema for active contracts metrics."""
    count: int = Field(..., description="Number of active contracts")
    average_age: float = Field(...,
                               description="Average age of active contracts in days")
    oldest_contract: Optional[datetime] = Field(
        None, description="Timestamp of oldest active contract")

    class Config:
        schema_extra = {
            "example": {
                "count": 24,
                "average_age": 15.5,
                "oldest_contract": "2024-01-01T10:00:00Z"
            }
        }


class ProcessingQueueMetrics(BaseModel):
    """Schema for processing queue metrics."""
    count: int = Field(...,
                       description="Number of contracts in processing queue")
    average_processing_time: float = Field(...,
                                           description="Average processing time in minutes")
    success_rate: float = Field(...,
                                description="Processing success rate percentage")
    failures: int = Field(..., description="Number of processing failures")

    class Config:
        schema_extra = {
            "example": {
                "count": 12,
                "average_processing_time": 5.5,
                "success_rate": 95.5,
                "failures": 2
            }
        }


class PendingReviewMetrics(BaseModel):
    """Schema for pending review metrics."""
    count: int = Field(..., description="Number of contracts pending review")
    urgent_reviews: int = Field(...,
                                description="Number of urgent reviews (>24h)")
    average_wait_time: float = Field(...,
                                     description="Average time in review queue in hours")

    class Config:
        schema_extra = {
            "example": {
                "count": 8,
                "urgent_reviews": 2,
                "average_wait_time": 12.5
            }
        }


class POsGeneratedMetrics(BaseModel):
    """Schema for generated POs metrics."""
    count: int = Field(...,
                       description="Number of contracts with POs generated")
    total_pos: int = Field(..., description="Total number of POs generated")
    average_pos_per_contract: float = Field(...,
                                            description="Average POs per contract")

    class Config:
        schema_extra = {
            "example": {
                "count": 45,
                "total_pos": 67,
                "average_pos_per_contract": 1.5
            }
        }


class ContractStatusCount(BaseModel):
    """Schema for detailed contract status counts."""
    active_contracts: ActiveContractsMetrics
    processing_queue: ProcessingQueueMetrics
    pending_review: PendingReviewMetrics
    pos_generated: POsGeneratedMetrics
    total_contracts: int = Field(..., description="Total number of contracts")
    last_updated: datetime = Field(..., description="Last update timestamp")

    class Config:
        schema_extra = {
            "example": {
                "active_contracts": {
                    "count": 24,
                    "average_age": 15.5,
                    "oldest_contract": "2024-01-01T10:00:00Z"
                },
                "processing_queue": {
                    "count": 12,
                    "average_processing_time": 5.5,
                    "success_rate": 95.5,
                    "failures": 2
                },
                "pending_review": {
                    "count": 8,
                    "urgent_reviews": 2,
                    "average_wait_time": 12.5
                },
                "pos_generated": {
                    "count": 45,
                    "total_pos": 67,
                    "average_pos_per_contract": 1.5
                },
                "total_contracts": 89,
                "last_updated": "2024-01-16T10:00:00Z"
            }
        }


class ContractStatusDetails(BaseModel):
    """Schema for detailed contract information."""
    id: str = Field(..., description="Contract ID")
    file_path: str = Field(..., description="Contract file path")
    status: str = Field(..., description="Current contract status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict = Field(..., description="Contract metadata")
    po_numbers: List[str] = Field(
        default=[], description="Associated PO numbers")
    age_in_days: float = Field(..., description="Contract age in days")
    processing_time: Optional[float] = Field(
        None, description="Processing time in minutes")
    review_wait_time: Optional[float] = Field(
        None, description="Time in review queue in hours")


class StatusDistribution(BaseModel):
    """Schema for contract status distribution over time."""
    time_periods: List[str] = Field(..., description="Time period labels")
    active_contracts: List[int] = Field(...,
                                        description="Active contract counts")
    processing_queue: List[int] = Field(...,
                                        description="Processing queue counts")
    pending_review: List[int] = Field(..., description="Pending review counts")
    pos_generated: List[int] = Field(..., description="POs generated counts")

    class Config:
        schema_extra = {
            "example": {
                "time_periods": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "active_contracts": [20, 22, 24],
                "processing_queue": [10, 12, 8],
                "pending_review": [5, 8, 6],
                "pos_generated": [40, 43, 45]
            }
        }


class DashboardMetrics(BaseModel):
    """Schema for comprehensive dashboard metrics."""
    status_counts: ContractStatusCount = Field(
        ..., description="Detailed status counts and metrics")
    status_distribution: Optional[StatusDistribution] = Field(
        None, description="Status distribution over time")

    class Config:
        schema_extra = {
            "example": {
                "status_counts": ContractStatusCount.Config.schema_extra["example"],
                "status_distribution": StatusDistribution.Config.schema_extra["example"]
            }
        }
