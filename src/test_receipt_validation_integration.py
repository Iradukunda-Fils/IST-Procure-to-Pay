#!/usr/bin/env python
"""
Integration test for receipt validation Celery task.

This script tests the complete receipt validation workflow
including the Celery task integration.
"""

import os
import sys
import django
from decimal import Decimal

# Add the src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from documents.models import Document
from purchases.models import PurchaseRequest, PurchaseOrder, RequestItem
from purchases.tasks import validate_receipt_against_po

User = get_user_model()


def create_test_data():
    """Create test data for integration testing."""
    print("Creating test data...")
    
    # Create test user
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'role': 'staff',
            'first_name': 'Test',
            'last_name': 'User'
        }
    )
    
    # Create purchase request
    pr = PurchaseRequest.objects.create(
        title='Test Purchase Request',
        description='Test purchase for validation',
        amount=Decimal('1000.00'),
        created_by=user,
        status='APPROVED'
    )
    
    # Add items to the request
    RequestItem.objects.create(
        request=pr,
        name='Test Product A',
        quantity=2,
        unit_price=Decimal('300.00')
    )
    
    RequestItem.objects.create(
        request=pr,
        name='Test Product B',
        quantity=1,
        unit_price=Decimal('400.00')
    )
    
    # Create purchase order
    po = PurchaseOrder.objects.create(
        po_number='PO-TEST-001',
        request=pr,
        vendor='Test Vendor Inc',
        total=Decimal('1000.00'),
        data={
            'items': [
                {'name': 'Test Product A', 'quantity': 2, 'unit_price': 300.00},
                {'name': 'Test Product B', 'quantity': 1, 'unit_price': 400.00}
            ]
        }
    )
    
    # Create receipt document with metadata
    receipt_doc = Document.objects.create(
        original_filename='test_receipt.pdf',
        file_size=1024,
        file_hash='test_hash_123',
        doc_type='RECEIPT',
        title='Test Receipt',
        uploaded_by=user,
        processing_status='COMPLETED',
        metadata={
            'vendor': {'name': 'Test Vendor Inc', 'email': 'vendor@test.com'},
            'items': [
                {'description': 'Test Product A', 'quantity': 2, 'unit_price': 300.00},
                {'description': 'Test Product B', 'quantity': 1, 'unit_price': 400.00}
            ],
            'totals': {'total': 1000.00, 'subtotal': 1000.00, 'tax': 0.00},
            'transaction': {'date': '2024-11-20', 'transaction_id': 'TXN-TEST-001'}
        }
    )
    
    return pr, po, receipt_doc


def test_receipt_validation_task():
    """Test the complete receipt validation task."""
    print("Testing receipt validation task integration...")
    
    # Create test data
    pr, po, receipt_doc = create_test_data()
    
    # Run the validation task (synchronously for testing)
    result = validate_receipt_against_po(str(receipt_doc.id), str(po.id))
    
    print(f"Task result: {result}")
    
    # Verify the task completed successfully
    assert result['status'] == 'completed', f"Task should complete successfully, got: {result}"
    assert 'validation_score' in result, "Result should include validation score"
    assert 'needs_review' in result, "Result should include needs_review flag"
    assert 'discrepancies' in result, "Result should include discrepancies"
    
    # Check that the receipt document was updated with validation results
    receipt_doc.refresh_from_db()
    assert receipt_doc.metadata is not None, "Receipt metadata should exist"
    assert 'validation' in receipt_doc.metadata, "Receipt should have validation metadata"
    
    validation_metadata = receipt_doc.metadata['validation']
    assert 'results' in validation_metadata, "Validation metadata should have results"
    assert 'po_number' in validation_metadata, "Validation should reference PO number"
    assert validation_metadata['po_number'] == po.po_number, "PO number should match"
    
    # Verify validation scores
    validation_results = validation_metadata['results']
    assert 'overall_score' in validation_results, "Should have overall score"
    assert 'vendor_match' in validation_results, "Should have vendor match score"
    assert 'total_match' in validation_results, "Should have total match score"
    assert 'items_match' in validation_results, "Should have items match score"
    
    # For this perfect match test case, scores should be high
    assert validation_results['overall_score'] >= 0.8, f"Overall score should be high for perfect match, got: {validation_results['overall_score']}"
    assert validation_results['vendor_match'] >= 0.8, f"Vendor match should be high, got: {validation_results['vendor_match']}"
    assert validation_results['total_match'] >= 0.9, f"Total match should be high, got: {validation_results['total_match']}"
    
    print("✓ Receipt validation task integration test passed")
    
    # Clean up test data
    receipt_doc.delete()
    po.delete()
    pr.delete()
    
    return result


def test_receipt_validation_with_discrepancies():
    """Test receipt validation with discrepancies."""
    print("Testing receipt validation with discrepancies...")
    
    # Create test data
    pr, po, receipt_doc = create_test_data()
    
    # Modify receipt to have discrepancies
    receipt_doc.metadata = {
        'vendor': {'name': 'Different Vendor Corp'},  # Different vendor
        'items': [
            {'description': 'Different Product', 'quantity': 1, 'unit_price': 1200.00}  # Different items
        ],
        'totals': {'total': 1200.00},  # Different total
        'transaction': {'date': '2024-11-20'}
    }
    receipt_doc.save()
    
    # Run validation
    result = validate_receipt_against_po(str(receipt_doc.id), str(po.id))
    
    print(f"Discrepancy test result: {result}")
    
    # Verify discrepancies were detected
    assert result['status'] == 'completed', "Task should complete"
    assert result['needs_review'] == True, "Should flag for manual review"
    assert len(result['discrepancies']) > 0, "Should detect discrepancies"
    assert result['validation_score'] < 0.6, f"Validation score should be low, got: {result['validation_score']}"
    
    # Check validation metadata
    receipt_doc.refresh_from_db()
    validation_results = receipt_doc.metadata['validation']['results']
    assert len(validation_results['discrepancies']) > 0, "Should have recorded discrepancies"
    assert 'REQUIRES_MANUAL_REVIEW' in validation_results.get('flags', []), "Should flag for manual review"
    
    print("✓ Receipt validation with discrepancies test passed")
    
    # Clean up
    receipt_doc.delete()
    po.delete()
    pr.delete()


def main():
    """Run integration tests."""
    print("Starting receipt validation integration tests...\n")
    
    try:
        test_receipt_validation_task()
        test_receipt_validation_with_discrepancies()
        
        print("\n🎉 All integration tests passed!")
        print("\nValidated functionality:")
        print("✓ Complete receipt validation workflow")
        print("✓ Celery task integration")
        print("✓ Database metadata storage")
        print("✓ Discrepancy detection and flagging")
        print("✓ Manual review triggering")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())