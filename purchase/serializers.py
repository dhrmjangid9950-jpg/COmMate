from rest_framework import serializers
from django.db import models
from .models import Vendor, PurchaseOrder, POItem, Receiving, ReceivingItem


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'registration_no', 'name', 'contact_person', 'email', 'phone', 'address', 
                  'gst_no', 'pan_no', 'bank_name', 'bank_account_no', 'bank_ifsc', 'created_at']
        read_only_fields = ['registration_no']


class POItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = POItem
        fields = ['id', 'product_name', 'description', 'hsn_code', 'gst_rate', 
                  'quantity', 'unit_price', 'subtotal', 'tax_amount', 'total_price']
        read_only_fields = ['subtotal', 'tax_amount', 'total_price']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = POItemSerializer(many=True)

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'po_number', 'vendor', 'order_date', 'expected_delivery', 
                  'status', 'subtotal', 'tax_total', 'total_amount', 'created_at', 'items']
        read_only_fields = ['po_number', 'subtotal', 'tax_total', 'total_amount', 'status', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        from datetime import datetime
        po_number = f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        validated_data['po_number'] = po_number
        validated_data['status'] = 'sent'
        
        # Calculate totals
        subtotal_total = 0
        tax_total = 0
        
        for item_data in items_data:
            item_subtotal = item_data['quantity'] * item_data['unit_price']
            item_tax = (item_subtotal * item_data.get('gst_rate', 0)) / 100
            item_total = item_subtotal + item_tax
            
            subtotal_total += item_subtotal
            tax_total += item_tax
            
            # Add calculated fields to item_data
            item_data['subtotal'] = item_subtotal
            item_data['tax_amount'] = item_tax
            item_data['total_price'] = item_total
        
        validated_data['subtotal'] = subtotal_total
        validated_data['tax_total'] = tax_total
        validated_data['total_amount'] = subtotal_total + tax_total
        
        po = PurchaseOrder.objects.create(**validated_data)
        
        for item_data in items_data:
            POItem.objects.create(po=po, **item_data)
        
        return po

    def update(self, instance, validated_data):
        # Allow update for all status except cancelled and closed
        if instance.status in ['cancelled', 'closed']:
            raise serializers.ValidationError("Cannot update cancelled or closed PO")
        
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if items_data is not None:
            instance.items.all().delete()
            subtotal_total = 0
            tax_total = 0
            
            for item_data in items_data:
                item_subtotal = item_data['quantity'] * item_data['unit_price']
                item_tax = (item_subtotal * item_data.get('gst_rate', 0)) / 100
                item_total = item_subtotal + item_tax
                
                subtotal_total += item_subtotal
                tax_total += item_tax
                
                item_data['subtotal'] = item_subtotal
                item_data['tax_amount'] = item_tax
                item_data['total_price'] = item_total
                
                POItem.objects.create(po=instance, **item_data)
            
            instance.subtotal = subtotal_total
            instance.tax_total = tax_total
            instance.total_amount = subtotal_total + tax_total
            instance.save()
        
        return instance


# ==================== RECEIVING SERIALIZERS ====================

class ReceivingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceivingItem
        fields = ['id', 'po_item', 'received_qty', 'unit_price', 'total_price', 'accepted', 'reject_reason']
        read_only_fields = ['total_price']

    def validate(self, data):
        # Auto-calculate total price
        data['total_price'] = data['received_qty'] * data.get('unit_price', 0)
        return data


class ReceivingSerializer(serializers.ModelSerializer):
    items = ReceivingItemSerializer(many=True)

    class Meta:
        model = Receiving
        fields = ['id', 'po', 'received_date', 'invoice_no', 'invoice_date', 
                  'gst_percentage', 'gst_amount', 'subtotal', 'total_amount', 
                  'notes', 'items']
        read_only_fields = ['received_date', 'gst_amount', 'subtotal', 'total_amount']

    def validate(self, data):
        """Validate invoice_no is provided"""
        if not data.get('invoice_no'):
            raise serializers.ValidationError({'invoice_no': 'Invoice number is required'})
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # ✅ Validate invoice_no is provided
        if not validated_data.get('invoice_no'):
            raise serializers.ValidationError({'invoice_no': 'Invoice number is required'})
        
        # Calculate subtotal from items
        subtotal = 0
        for item_data in items_data:
            # Get unit price from POItem if not provided
            if not item_data.get('unit_price'):
                po_item = item_data['po_item']
                item_data['unit_price'] = po_item.unit_price
            
            item_data['total_price'] = item_data['received_qty'] * item_data.get('unit_price', 0)
            subtotal += item_data['total_price']
        
        # Calculate GST
        gst_percentage = validated_data.get('gst_percentage', 0)
        gst_amount = (subtotal * gst_percentage) / 100
        total_amount = subtotal + gst_amount
        
        validated_data['subtotal'] = subtotal
        validated_data['gst_amount'] = gst_amount
        validated_data['total_amount'] = total_amount
        
        receiving = Receiving.objects.create(**validated_data)
        po = receiving.po
        
        # Validate and create receiving items
        for item_data in items_data:
            po_item = item_data['po_item']
            if po_item.po != po:
                raise serializers.ValidationError("PO item not in this PO")
            
            # Check cumulative received quantity
            already_received = ReceivingItem.objects.filter(
                po_item=po_item
            ).aggregate(total=models.Sum('received_qty'))['total'] or 0
            
            if already_received + item_data['received_qty'] > po_item.quantity:
                raise serializers.ValidationError(
                    f"Received qty exceeds ordered qty for {po_item.product_name}"
                )
            
            ReceivingItem.objects.create(receiving=receiving, **item_data)
        
        # Update PO status (ledger entry will be created in views.py perform_create)
        total_ordered = sum(item.quantity for item in po.items.all())
        total_received = ReceivingItem.objects.filter(
            receiving__po=po
        ).aggregate(total=models.Sum('received_qty'))['total'] or 0
        
        if total_received >= total_ordered:
            po.status = 'closed'
        else:
            po.status = 'partially_received'
        po.save()
        
        return receiving