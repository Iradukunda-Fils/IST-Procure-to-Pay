#!/usr/bin/env python
"""
Test script for receipt validation task functionality.

This script tests the receipt validation task implementation including:
- Receipt data extraction and comparison logic
- Validation scoring algorithm
- Discrepancy detection and reporting

Requirements tested: 6.2, 6.3, 6.4
"""

import os
import sys
import django
from decimal import Decimal
from datetime import datetime
import json

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from purchases.tasks import (
    _perform_receipt_validation,
    _compare_vendors_detailed,
    _compare_totals_detailed,
    _compare_items_detailed,
    _determine_confidence_level,
    _check_fraud_indicators
)


def test_vendor_comparison():
    """Test vendor comparison functionality."""
    print("Testing vendor comparison...")
    
    # Test exact match
    receipt_vendor = {'name': 'ABC Company Ltd'}
    po_vendor = {'name': 'ABC Company Ltd'}
    result = _compare_vendors_detailed(receipt_vendor, po_vendor)
    assert result['score'] == 1.0, f"Expected 1.0, got {result['score']}"
    assert result['name_match'] == True
    print("✓ Exact vendor match test passed")
    
    # Test partial match
    receipt_vendor = {'name': 'ABC Company'}
    po_vendor = {'name': 'ABC Company Ltd'}
    result = _compare_vendors_detailed(receipt_vendor, po_vendor)
    assert result['score'] == 0.8, f"Expected 0.8, got {result['score']}"
    print("✓ Partial vendor match test passed")
    
    # Test no match
    receipt_vendor = {'name': 'XYZ Corp'}
    po_vendor = {'name': 'ABC Company Ltd'}
    result = _compare_vendors_detailed(receipt_vendor, po_vendor)
    assert result['score'] <= 0.2, f"Expected <= 0.2, got {result['score']}"
    print("✓ No vendor match test passed")
    
    # Test with contact information
    receipt_vendor = {
        'name': 'ABC Company',
        'email': 'contact@abc.com'
    }
    po_vendor = {
        'name': 'ABC Company Ltd',
        'email': 'contact@abc.com'
    }
    result = _compare_vendors_detailed(receipt_vendor, po_vendor)
    assert result['score'] > 0.8, f"Expected > 0.8, got {result['score']}"
    assert result['contact_match'] == True
    print("✓ Vendor with contact match test passed")


def test_total_comparison():
    """Test total amount comparison functionality."""
    print("\nTesting total comparison...")
    
    # Test exact match
    receipt_totals = {'total': 1000.00}
    po_totals = {'total': 1000.00}
    result = _compare_totals_detailed(receipt_totals, po_totals)
    assert result['score'] == 1.0, f"Expected 1.0, got {result['score']}"
    assert result['percentage_diff'] == 0.0
    print("✓ Exact total match test passed")
    
    # Test small difference (within 1%)
    receipt_totals = {'total': 1005.00}
    po_totals = {'total': 1000.00}
    result = _compare_totals_detailed(receipt_totals, po_totals)
    assert result['score'] >= 0.9, f"Expected >= 0.9, got {result['score']}"
    assert result['percentage_diff'] == 0.5
    print("✓ Small total difference test passed")
    
    # Test large difference
    receipt_totals = {'total': 1500.00}
    po_totals = {'total': 1000.00}
    result = _compare_totals_detailed(receipt_totals, po_totals)
    assert result['score'] <= 0.3, f"Expected <= 0.3, got {result['score']}"
    assert result['percentage_diff'] == 50.0
    print("✓ Large total difference test passed")
    
    # Test missing totals
    receipt_totals = {}
    po_totals = {'total': 1000.00}
    result = _compare_totals_detailed(receipt_totals, po_totals)
    assert result['score'] == 0.0, f"Expected 0.0, got {result['score']}"
    print("✓ Missing total test passed")


def test_items_comparison():
    """Test items comparison functionality."""
    print("\nTesting items comparison...")
    
    # Test exact match
    receipt_items = [
        {'description': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00},
        {'description': 'Mouse', 'quantity': 2, 'unit_price': 25.00}
    ]
    po_items = [
        {'name': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00},
        {'name': 'Mouse', 'quantity': 2, 'unit_price': 25.00}
    ]
    result = _compare_items_detailed(receipt_items, po_items)
    assert result['score'] >= 0.9, f"Expected >= 0.9, got {result['score']}"
    assert result['matched_count'] == 2
    print("✓ Exact items match test passed")
    
    # Test partial match with quantity discrepancy
    receipt_items = [
        {'description': 'Laptop Computer', 'quantity': 3, 'unit_price': 1000.00},
        {'description': 'Mouse', 'quantity': 2, 'unit_price': 25.00}
    ]
    po_items = [
        {'name': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00},
        {'name': 'Mouse', 'quantity': 2, 'unit_price': 25.00}
    ]
    result = _compare_items_detailed(receipt_items, po_items)
    assert len(result['quantity_discrepancies']) == 1
    assert result['quantity_discrepancies'][0]['difference'] == 1
    print("✓ Quantity discrepancy test passed")
    
    # Test extra items
    receipt_items = [
        {'description': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00},
        {'description': 'Mouse', 'quantity': 2, 'unit_price': 25.00},
        {'description': 'Keyboard', 'quantity': 1, 'unit_price': 50.00}
    ]
    po_items = [
        {'name': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00},
        {'name': 'Mouse', 'quantity': 2, 'unit_price': 25.00}
    ]
    result = _compare_items_detailed(receipt_items, po_items)
    assert len(result['extra_items']) == 1
    assert result['extra_items'][0]['description'] == 'keyboard'
    print("✓ Extra items test passed")
    
    # Test missing items
    receipt_items = [
        {'description': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00}
    ]
    po_items = [
        {'name': 'Laptop Computer', 'quantity': 2, 'unit_price': 1000.00},
        {'name': 'Mouse', 'quantity': 2, 'unit_price': 25.00}
    ]
    result = _compare_items_detailed(receipt_items, po_items)
    assert len(result['missing_items']) == 1
    assert result['missing_items'][0]['name'] == 'Mouse'
    print("✓ Missing items test passed")


def test_confidence_level_determination():
    """Test confidence level determination."""
    print("\nTesting confidence level determination...")
    
    # High confidence scenario
    validation_result = {
        'overall_score': 0.95,
        'flags': []
    }
    confidence = _determine_confidence_level(validation_result)
    assert confidence == 'HIGH', f"Expected HIGH, got {confidence}"
    print("✓ High confidence test passed")
    
    # Medium confidence scenario
    validation_result = {
        'overall_score': 0.75,
        'flags': []
    }
    confidence = _determine_confidence_level(validation_result)
    assert confidence == 'MEDIUM', f"Expected MEDIUM, got {confidence}"
    print("✓ Medium confidence test passed")
    
    # Low confidence scenario
    validation_result = {
        'overall_score': 0.5,
        'flags': []
    }
    confidence = _determine_confidence_level(validation_result)
    assert confidence == 'LOW', f"Expected LOW, got {confidence}"
    print("✓ Low confidence test passed")
    
    # Major flags override
    validation_result = {
        'overall_score': 0.9,
        'flags': ['VENDOR_MAJOR_MISMATCH']
    }
    confidence = _determine_confidence_level(validation_result)
    assert confidence == 'LOW', f"Expected LOW due to major flag, got {confidence}"
    print("✓ Major flags override test passed")


def test_fraud_indicators():
    """Test fraud indicator detection."""
    print("\nTesting fraud indicator detection...")
    
    receipt_data = {
        'vendor': {'name': 'Suspicious Vendor'},
        'totals': {'total': 2000.00}
    }
    po_data = {
        'vendor': {'name': 'Legitimate Vendor'},
        'totals': {'total': 1000.00}
    }
    
    # Create validation result with suspicious patterns
    validation_result = {
        'validation_details': {
            'vendor': {'score': 0.1},
            'totals': {'percentage_diff': 100.0},
            'items': {
                'extra_items': [{'description': 'item1'}, {'description': 'item2'}],
                'total_items': 2
            }
        }
    }
    
    indicators = _check_fraud_indicators(receipt_data, po_data, validation_result)
    
    assert 'SUSPICIOUS_AMOUNT_DIFFERENCE' in indicators
    assert 'SUSPICIOUS_VENDOR_MISMATCH' in indicators
    assert 'SUSPICIOUS_EXTRA_ITEMS' in indicators
    print("✓ Fraud indicators detection test passed")


def test_full_receipt_validation():
    """Test complete receipt validation workflow."""
    print("\nTesting full receipt validation workflow...")
    
    # Create realistic test data
    receipt_data = {
        'vendor': {
            'name': 'Tech Solutions Inc',
            'email': 'sales@techsolutions.com'
        },
        'items': [
            {'description': 'Dell Laptop', 'quantity': 2, 'unit_price': 1200.00},
            {'description': 'Wireless Mouse', 'quantity': 2, 'unit_price': 30.00}
        ],
        'totals': {
            'subtotal': 2460.00,
            'tax': 196.80,
            'total': 2656.80
        },
        'transaction': {
            'date': '2024-01-15',
            'transaction_id': 'TXN123456'
        }
    }
    
    po_data = {
        'vendor': {
            'name': 'Tech Solutions Inc'
        },
        'items': [
            {'name': 'Dell Laptop', 'quantity': 2, 'unit_price': 1200.00},
            {'name': 'Wireless Mouse', 'quantity': 2, 'unit_price': 30.00}
        ],
        'totals': {
            'total': 2656.80
        },
        'po_number': 'PO-2024000001123'
    }
    
    # Perform validation
    result = _perform_receipt_validation(receipt_data, po_data)
    
    # Verify results
    assert result['overall_score'] >= 0.9, f"Expected high score, got {result['overall_score']}"
    assert result['vendor_match'] >= 0.9, f"Expected high vendor match, got {result['vendor_match']}"
    assert result['total_match'] >= 0.9, f"Expected high total match, got {result['total_match']}"
    assert result['items_match'] >= 0.9, f"Expected high items match, got {result['items_match']}"
    assert result['confidence_level'] == 'HIGH'
    assert len(result['discrepancies']) == 0, f"Expected no discrepancies, got {len(result['discrepancies'])}"
    
    print("✓ Full validation - perfect match test passed")
    
    # Test with discrepancies
    receipt_data_with_issues = receipt_data.copy()
    receipt_data_with_issues['vendor']['name'] = 'Different Vendor Corp'
    receipt_data_with_issues['totals']['total'] = 3000.00  # 13% higher
    receipt_data_with_issues['items'].append({
        'description': 'Extra Item', 'quantity': 1, 'unit_price': 100.00
    })
    
    result_with_issues = _perform_receipt_validation(receipt_data_with_issues, po_data)
    
    assert result_with_issues['overall_score'] < 0.7, f"Expected low score, got {result_with_issues['overall_score']}"
    assert len(result_with_issues['discrepancies']) >= 2, f"Expected multiple discrepancies, got {len(result_with_issues['discrepancies'])}"
    assert 'REQUIRES_MANUAL_REVIEW' in result_with_issues['flags']
    
    print("✓ Full validation - with discrepancies test passed")


def test_edge_cases():
    """Test edge cases and error conditions."""
    print("\nTesting edge cases...")
    
    # Empty data
    empty_receipt = {'vendor': {}, 'items': [], 'totals': {}}
    empty_po = {'vendor': {}, 'items': [], 'totals': {}}
    result = _perform_receipt_validation(empty_receipt, empty_po)
    assert isinstance(result, dict)
    assert 'overall_score' in result
    print("✓ Empty data test passed")
    
    # Missing vendor names
    receipt_no_vendor = {'vendor': {}, 'items': [], 'totals': {'total': 100}}
    po_with_vendor = {'vendor': {'name': 'Test Vendor'}, 'items': [], 'totals': {'total': 100}}
    result = _perform_receipt_validation(receipt_no_vendor, po_with_vendor)
    assert result['vendor_match'] == 0.0
    print("✓ Missing vendor test passed")
    
    # Zero amounts
    receipt_zero = {'vendor': {'name': 'Test'}, 'items': [], 'totals': {'total': 0}}
    po_nonzero = {'vendor': {'name': 'Test'}, 'items': [], 'totals': {'total': 100}}
    result = _perform_receipt_validation(receipt_zero, po_nonzero)
    assert result['total_match'] == 0.0
    print("✓ Zero amounts test passed")


def print_validation_summary(result):
    """Print a detailed summary of validation results."""
    print("\n" + "="*60)
    print("RECEIPT VALIDATION SUMMARY")
    print("="*60)
    print(f"Overall Score: {result['overall_score']:.2f}")
    print(f"Confidence Level: {result['confidence_level']}")
    print(f"Vendor Match: {result['vendor_match']:.2f}")
    print(f"Total Match: {result['total_match']:.2f}")
    print(f"Items Match: {result['items_match']:.2f}")
    print(f"Date Match: {result['date_match']:.2f}")
    
    if result['flags']:
        print(f"\nFlags: {', '.join(result['flags'])}")
    
    if result['discrepancies']:
        print(f"\nDiscrepancies ({len(result['discrepancies'])}):")
        for i, disc in enumerate(result['discrepancies'], 1):
            print(f"  {i}. {disc['type']} ({disc['severity']})")
            print(f"     {disc.get('suggested_action', 'No action suggested')}")
    
    print("="*60)


def main():
    """Run all tests."""
    print("Starting Receipt Validation Task Tests")
    print("="*50)
    
    try:
        test_vendor_comparison()
        test_total_comparison()
        test_items_comparison()
        test_confidence_level_determination()
        test_fraud_indicators()
        test_full_receipt_validation()
        test_edge_cases()
        
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("Receipt validation task implementation is working correctly.")
        print("Requirements 6.2, 6.3, and 6.4 have been successfully implemented.")
        
        # Demonstrate with a realistic example
        print("\n" + "="*50)
        print("DEMONSTRATION WITH REALISTIC DATA")
        
        receipt_data = {
            'vendor': {'name': 'Office Supplies Co', 'email': 'orders@officesupplies.com'},
            'items': [
                {'description': 'Office Chair', 'quantity': 5, 'unit_price': 150.00},
                {'description': 'Desk Lamp', 'quantity': 5, 'unit_price': 45.00}
            ],
            'totals': {'subtotal': 975.00, 'tax': 78.00, 'total': 1053.00},
            'transaction': {'date': '2024-01-20', 'transaction_id': 'TXN789012'}
        }
        
        po_data = {
            'vendor': {'name': 'Office Supplies Co'},
            'items': [
                {'name': 'Office Chair', 'quantity': 5, 'unit_price': 150.00},
                {'name': 'Desk Lamp', 'quantity': 5, 'unit_price': 45.00}
            ],
            'totals': {'total': 1053.00},
            'po_number': 'PO-2024000002456'
        }
        
        demo_result = _perform_receipt_validation(receipt_data, po_data)
        print_validation_summary(demo_result)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)