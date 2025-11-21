"""
Serializers for the purchases app.

This module provides DRF serializers for purchase request management,
approval workflows, and receipt submission with proper validation.
"""

from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from decimal import Decimal

from .models import PurchaseRequest, RequestItem, Approval, PurchaseOrder
from documents.models import Document
from documents.serializers import DocumentUploadSerializer


class RequestItemSerializer(serializers.ModelSerializer):
    """
    Serializer for RequestItem model.
    
    Handles line item validation and calculation of line totals.
    """
    
    line_total = serializers.ReadOnlyField()
    
    class Meta:
        model = RequestItem
        fields = [
            'id',
            'name',
            'quantity',
            'unit_price',
            'description',
            'unit_of_measure',
            'line_total',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_quantity(self, value):
        """Validate quantity is positive."""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value
    
    def validate_unit_price(self, value):
        """Validate unit price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Unit price must be greater than zero.")
        return value


class PurchaseRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating purchase requests.
    
    Handles nested item creation and proforma document association.
    """
    
    items = RequestItemSerializer(many=True)
    created_by = serializers.StringRelatedField(read_only=True)
    calculated_total = serializers.ReadOnlyField()
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id',
            'title',
            'description',
            'amount',
            'status',
            'created_by',
            'proforma',
            'items',
            'calculated_total',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'created_by',
            'created_at',
            'updated_at',
        ]
    
    def validate_items(self, value):
        """Validate that at least one item is provided."""
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value
    
    def validate_proforma(self, value):
        """Validate proforma document if provided."""
        if value and value.doc_type != 'PROFORMA':
            raise serializers.ValidationError(
                "Referenced document must be of type PROFORMA."
            )
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Create purchase request with nested items.
        """
        items_data = validated_data.pop('items')
        
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        
        # Create the purchase request
        purchase_request = PurchaseRequest.objects.create(**validated_data)
        
        # Create associated items
        for item_data in items_data:
            RequestItem.objects.create(request=purchase_request, **item_data)
        
        # Update amount to match calculated total
        purchase_request.amount = purchase_request.calculated_total
        purchase_request.save()
        
        return purchase_request


class PurchaseRequestDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for purchase request retrieval and updates.
    """
    
    items = RequestItemSerializer(many=True, read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)
    last_approved_by = serializers.StringRelatedField(read_only=True)
    calculated_total = serializers.ReadOnlyField()
    is_pending = serializers.ReadOnlyField()
    is_approved = serializers.ReadOnlyField()
    is_rejected = serializers.ReadOnlyField()
    is_modifiable = serializers.ReadOnlyField()
    required_approval_levels = serializers.ReadOnlyField(source='get_required_approval_levels')
    pending_approval_levels = serializers.ReadOnlyField(source='get_pending_approval_levels')
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id',
            'title',
            'description',
            'amount',
            'status',
            'created_by',
            'last_approved_by',
            'proforma',
            'version',
            'created_at',
            'updated_at',
            'approved_at',
            'items',
            'calculated_total',
            'is_pending',
            'is_approved',
            'is_rejected',
            'is_modifiable',
            'required_approval_levels',
            'pending_approval_levels',
        ]
        read_only_fields = [
            'id',
            'status',
            'created_by',
            'last_approved_by',
            'version',
            'created_at',
            'updated_at',
            'approved_at',
        ]


class PurchaseRequestListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for purchase request list views.
    """
    
    created_by = serializers.StringRelatedField(read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id',
            'title',
            'amount',
            'status',
            'created_by',
            'created_at',
            'updated_at',
            'item_count',
        ]
    
    def get_item_count(self, obj):
        """Get count of items in the request."""
        return obj.items.count()


class ApprovalSerializer(serializers.ModelSerializer):
    """
    Serializer for approval operations.
    """
    
    approver = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Approval
        fields = [
            'id',
            'level',
            'decision',
            'comment',
            'approver',
            'created_at',
        ]
        read_only_fields = ['id', 'approver', 'created_at']
    
    def validate_level(self, value):
        """Validate approval level."""
        if value not in [1, 2]:
            raise serializers.ValidationError("Approval level must be 1 or 2.")
        return value
    
    def validate_decision(self, value):
        """Validate approval decision."""
        if value not in ['APPROVED', 'REJECTED']:
            raise serializers.ValidationError("Decision must be APPROVED or REJECTED.")
        return value


class ReceiptSubmissionSerializer(serializers.Serializer):
    """
    Serializer for receipt submission to purchase requests.
    
    Handles receipt document upload and validation trigger.
    """
    
    receipt_file = serializers.FileField(
        help_text="Receipt document file (PDF or image)"
    )
    title = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Optional title for the receipt document"
    )
    
    def validate_receipt_file(self, value):
        """Validate receipt file."""
        # Use the same validation as DocumentUploadSerializer
        doc_serializer = DocumentUploadSerializer()
        return doc_serializer.validate_file(value)
    
    def create(self, validated_data):
        """
        Create receipt document and associate with purchase request.
        """
        request = self.context.get('request')
        purchase_request = self.context.get('purchase_request')
        
        if not request or not request.user:
            raise serializers.ValidationError("User authentication required.")
        
        if not purchase_request:
            raise serializers.ValidationError("Purchase request context required.")
        
        # Create document with receipt type
        receipt_file = validated_data['receipt_file']
        title = validated_data.get('title', f"Receipt for {purchase_request.title}")
        
        document = Document.objects.create(
            file=receipt_file,
            doc_type='RECEIPT',
            title=title,
            uploaded_by=request.user
        )
        
        return {
            'document': document,
            'purchase_request': purchase_request,
            'message': 'Receipt uploaded successfully and validation triggered'
        }


class ReceiptValidationStatusSerializer(serializers.Serializer):
    """
    Serializer for receipt validation status reporting.
    """
    
    receipt_id = serializers.UUIDField(read_only=True)
    receipt_filename = serializers.CharField(read_only=True)
    processing_status = serializers.CharField(read_only=True)
    validation_results = serializers.JSONField(read_only=True)
    match_score = serializers.FloatField(read_only=True, required=False)
    discrepancies = serializers.ListField(read_only=True, required=False)
    validation_timestamp = serializers.DateTimeField(read_only=True, required=False)
    
    def to_representation(self, instance):
        """
        Generate validation status representation from document instance.
        """
        if not isinstance(instance, Document):
            return {}
        
        # Extract validation results from metadata
        validation_data = instance.metadata.get('validation', {}) if instance.metadata else {}
        
        return {
            'receipt_id': instance.id,
            'receipt_filename': instance.original_filename,
            'processing_status': instance.processing_status,
            'validation_results': validation_data,
            'match_score': validation_data.get('match_score'),
            'discrepancies': validation_data.get('discrepancies', []),
            'validation_timestamp': instance.processed_at,
        }