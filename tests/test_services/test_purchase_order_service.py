"""
Test suite for PurchaseOrderService class validating purchase order generation,
processing, and management functionality.

Version: 1.0
"""

# External imports with versions
import pytest  # v7.3+
import pytest_asyncio  # v0.21+
from unittest.mock import Mock, AsyncMock, patch  # built-in
from freezegun import freeze_time  # v1.2+
from datetime import datetime, timedelta
import json
from typing import Dict, List

# Internal imports
from app.services.purchase_order_service import PurchaseOrderService
from app.services.s3_service import S3Service
from app.services.email_service import EmailService
from app.models.purchase_order import PurchaseOrder, PO_STATUS_CHOICES

# Test fixtures and data
@pytest.fixture
def po_service(mocker):
    """
    Fixture providing configured PurchaseOrderService instance with mocked dependencies.
    """
    # Mock S3 service
    mock_s3 = AsyncMock(spec=S3Service)
    mock_s3.upload_file.return_value = {
        'status': 'success',
        'version_id': 'test-version',
        'etag': 'test-etag',
        'metadata': {'test': 'metadata'}
    }
    mock_s3.get_file_url.return_value = 'https://test-bucket.s3.amazonaws.com/test.pdf'

    # Mock email service
    mock_email = AsyncMock(spec=EmailService)
    mock_email.send_po_generated_notification.return_value = True

    # Mock configuration
    mock_config = {
        'templates_path': 'app/templates/purchase_orders',
        'max_batch_size': 50
    }

    return PurchaseOrderService(mock_s3, mock_email, mock_config)

class TestPurchaseOrderService:
    """Test class for comprehensive PurchaseOrderService functionality validation."""

    def setup_method(self):
        """Prepares test environment before each test."""
        self.test_po_data = {
            'template_type': 'standard',
            'output_format': 'pdf',
            'include_logo': True,
            'digital_signature': True,
            'recipient_email': 'test@example.com',
            'contract_details': {
                'vendor': 'Test Vendor',
                'amount': 1000.00,
                'terms': 'Net 30'
            }
        }
        
        self.test_contract_data = {
            'id': 'test-contract-123',
            'status': 'active',
            'vendor': 'Test Vendor',
            'amount': 1000.00
        }

    def teardown_method(self):
        """Cleans up test environment after each test."""
        pass

    @pytest.mark.asyncio
    @pytest.mark.parametrize('template_type,output_format', [
        ('standard', 'pdf'),
        ('standard', 'docx'),
        ('custom', 'pdf'),
        ('custom', 'docx')
    ])
    async def test_create_purchase_order_success(
        self,
        po_service: PurchaseOrderService,
        template_type: str,
        output_format: str
    ):
        """Tests successful creation of a purchase order with different templates and formats."""
        # Arrange
        contract_id = 'test-contract-123'
        user_id = 'test-user-456'
        po_data = {
            **self.test_po_data,
            'template_type': template_type,
            'output_format': output_format
        }

        # Start performance timer
        start_time = datetime.utcnow()

        # Act
        result = await po_service.create_purchase_order(
            contract_id=contract_id,
            po_data=po_data,
            user_id=user_id,
            send_notification=True
        )

        # Assert timing requirement (<5 seconds)
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        assert processing_time < 5, f"PO generation took {processing_time} seconds, exceeding 5 second limit"

        # Verify PO creation success
        assert isinstance(result, PurchaseOrder)
        assert result.contract_id == contract_id
        assert result.generated_by == user_id
        assert result.template_type == template_type
        assert result.output_format == output_format
        assert result.status == 'generated'
        assert result.file_path.startswith('s3://')

        # Verify S3 upload
        po_service._s3_service.upload_file.assert_called_once()
        upload_args = po_service._s3_service.upload_file.call_args[1]
        assert upload_args['metadata']['po_number'] == result.po_number
        assert upload_args['metadata']['contract_id'] == contract_id

        # Verify notification
        po_service._email_service.send_po_generated_notification.assert_called_once_with(
            recipient_email=po_data['recipient_email'],
            po_number=result.po_number,
            po_data=pytest.approx({
                'status': 'generated',
                'generated_at': result.created_at.isoformat(),
                'download_url': 'https://test-bucket.s3.amazonaws.com/test.pdf'
            })
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize('batch_size', [1, 10, 50, 100])
    async def test_batch_generate_pos(
        self,
        po_service: PurchaseOrderService,
        batch_size: int
    ):
        """Tests batch generation of purchase orders with performance monitoring."""
        # Arrange
        user_id = 'test-user-456'
        batch_data = [
            {
                'contract_id': f'test-contract-{i}',
                'po_data': {**self.test_po_data, 'reference': f'PO-{i}'}
            }
            for i in range(batch_size)
        ]

        # Start performance timer
        start_time = datetime.utcnow()

        # Act
        results = await po_service.batch_generate_pos(
            batch_data=batch_data,
            user_id=user_id
        )

        # Assert timing requirement (batch_size * 5 seconds max)
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        max_allowed_time = batch_size * 5
        assert processing_time < max_allowed_time, \
            f"Batch processing took {processing_time} seconds, exceeding {max_allowed_time} second limit"

        # Verify batch results
        assert len(results) == batch_size
        assert all(isinstance(po, PurchaseOrder) for po in results)
        assert all(po.status == 'generated' for po in results)

        # Verify S3 uploads
        assert po_service._s3_service.upload_file.call_count == batch_size

        # Verify notifications
        assert po_service._email_service.send_po_generated_notification.call_count == batch_size

    @pytest.mark.asyncio
    @pytest.mark.parametrize('status,expected_notifications', [
        ('draft', False),
        ('pending', True),
        ('approved', True),
        ('rejected', True)
    ])
    async def test_update_po_status(
        self,
        po_service: PurchaseOrderService,
        status: str,
        expected_notifications: bool
    ):
        """Tests purchase order status updates with validation and notifications."""
        # Arrange
        po_id = 'test-po-123'
        initial_status = 'draft'

        # Mock PO document
        mock_po = AsyncMock(spec=PurchaseOrder)
        mock_po.po_number = po_id
        mock_po.status = initial_status
        mock_po.update_status.return_value = True

        with patch('app.models.purchase_order.PurchaseOrder.objects.get', 
                  return_value=mock_po):
            # Act
            result = await po_service.update_po_status(
                po_id=po_id,
                new_status=status
            )

            # Assert
            assert result is True
            mock_po.update_status.assert_called_once_with(status)

            # Verify notification behavior
            if expected_notifications:
                po_service._email_service.send_po_generated_notification.assert_called_once()
            else:
                po_service._email_service.send_po_generated_notification.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize('expiration_minutes', [5, 15, 30, 60])
    async def test_get_po_download_url(
        self,
        po_service: PurchaseOrderService,
        expiration_minutes: int
    ):
        """Tests secure generation of PO download URLs with expiration."""
        # Arrange
        po_id = 'test-po-123'
        expected_url = 'https://test-bucket.s3.amazonaws.com/test.pdf'

        # Mock PO document
        mock_po = AsyncMock(spec=PurchaseOrder)
        mock_po.po_number = po_id
        mock_po.file_path = 's3://test-bucket/test.pdf'

        with patch('app.models.purchase_order.PurchaseOrder.objects.get',
                  return_value=mock_po):
            # Act
            url = await po_service.get_po_download_url(
                po_number=po_id,
                expiration_minutes=expiration_minutes
            )

            # Assert
            assert url == expected_url
            po_service._s3_service.get_file_url.assert_called_once_with(
                'test-bucket/test.pdf',
                expiry=expiration_minutes * 60
            )