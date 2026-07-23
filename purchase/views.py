from rest_framework import viewsets, status
from django.shortcuts import render
from rest_framework.response import Response
from django.db.models import Count, Sum
from django.http import FileResponse
from rest_framework.decorators import action
from datetime import datetime, timedelta

from .models import Vendor, PurchaseOrder, Receiving, ReceivingItem, POItem, VendorLedger, VendorPayment
from .serializers import VendorSerializer, PurchaseOrderSerializer, ReceivingSerializer
from .utils import generate_po_pdf, generate_vendor_pdf


# ==================== API VIEWS ====================

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer

    def perform_create(self, serializer):
        """Auto-generate registration number on create"""
        count = Vendor.objects.count() + 1
        reg_no = f"VENDOR-{datetime.now().strftime('%Y%m%d')}-{count:04d}"
        serializer.save(registration_no=reg_no)

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download Vendor Registration PDF"""
        vendor = self.get_object()
        pdf_buffer = generate_vendor_pdf(vendor)
        response = FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"Vendor_{vendor.registration_no or vendor.id}.pdf"
        )
        return response

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        """Get vendor ledger with all transactions"""
        vendor = self.get_object()
        
        # Get all ledger entries
        ledger_entries = VendorLedger.objects.filter(vendor=vendor).order_by('created_at')
        
        # Get all payments
        payments = VendorPayment.objects.filter(vendor=vendor).order_by('-payment_date')
        
        # Calculate totals
        total_credit = ledger_entries.filter(transaction_type='credit').aggregate(total=Sum('amount'))['total'] or 0
        total_debit = ledger_entries.filter(transaction_type='debit').aggregate(total=Sum('amount'))['total'] or 0
        opening_balance = ledger_entries.filter(transaction_type='opening').aggregate(total=Sum('amount'))['total'] or 0
        
        # Outstanding = Total Credit - Total Debit
        outstanding = total_credit - total_debit
        
        # Prepare ledger data
        ledger_data = []
        running_balance = 0
        for entry in ledger_entries:
            if entry.transaction_type == 'credit':
                running_balance += entry.amount
            elif entry.transaction_type == 'debit':
                running_balance -= entry.amount
            elif entry.transaction_type == 'opening':
                running_balance = entry.amount
            
            ledger_data.append({
                'id': entry.id,
                'date': entry.transaction_date.strftime('%d-%m-%Y'),
                'type': entry.transaction_type,
                'invoice_no': entry.invoice_no,
                'amount': str(entry.amount),
                'balance': str(running_balance),
                'description': entry.description,
            })
        
        # Prepare payment data
        payment_data = []
        for payment in payments:
            payment_data.append({
                'id': payment.id,
                'date': payment.payment_date.strftime('%d-%m-%Y'),
                'mode': payment.payment_mode,
                'amount': str(payment.amount),
                'reference_no': payment.reference_no,
                'notes': payment.notes,
            })
        
        return Response({
            'vendor': {
                'id': vendor.id,
                'name': vendor.name,
                'contact': vendor.contact_person,
                'phone': vendor.phone,
                'email': vendor.email,
            },
            'summary': {
                'total_credit': str(total_credit),
                'total_debit': str(total_debit),
                'opening_balance': str(opening_balance),
                'outstanding': str(outstanding),
            },
            'ledger': ledger_data,
            'payments': payment_data,
        })

    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """Add payment against vendor"""
        vendor = self.get_object()
        
        payment_mode = request.data.get('payment_mode')
        amount = request.data.get('amount')
        reference_no = request.data.get('reference_no', '')
        notes = request.data.get('notes', '')
        
        if not payment_mode or not amount:
            return Response({'error': 'Payment mode and amount are required'}, status=400)
        
        try:
            amount = float(amount)
        except ValueError:
            return Response({'error': 'Invalid amount'}, status=400)
        
        # Create payment record
        payment = VendorPayment.objects.create(
            vendor=vendor,
            payment_mode=payment_mode,
            amount=amount,
            reference_no=reference_no,
            notes=notes
        )
        
        # Create ledger entry (debit)
        VendorLedger.objects.create(
            vendor=vendor,
            transaction_type='debit',
            invoice_no=f"PAY-{payment.id}",
            amount=amount,
            description=notes or f"Payment via {payment_mode}"
        )
        
        return Response({
            'message': 'Payment added successfully',
            'payment': {
                'id': payment.id,
                'date': payment.payment_date.strftime('%d-%m-%Y'),
                'mode': payment.payment_mode,
                'amount': str(payment.amount),
                'reference_no': payment.reference_no,
            }
        })

    @action(detail=True, methods=['post'])
    def add_opening_balance(self, request, pk=None):
        """Add opening balance for vendor"""
        vendor = self.get_object()
        amount = request.data.get('amount')
        
        if amount is None:
            return Response({'error': 'Amount is required'}, status=400)
        
        try:
            amount = float(amount)
        except ValueError:
            return Response({'error': 'Invalid amount'}, status=400)
        
        # Check if opening balance already exists
        existing = VendorLedger.objects.filter(vendor=vendor, transaction_type='opening').first()
        if existing:
            existing.amount = amount
            existing.save()
        else:
            VendorLedger.objects.create(
                vendor=vendor,
                transaction_type='opening',
                amount=amount,
                description='Opening Balance'
            )
        
        return Response({
            'message': 'Opening balance added successfully',
            'amount': amount
        })

    def destroy(self, request, *args, **kwargs):
        """Delete vendor and all related data"""
        try:
            instance = self.get_object()
            vendor_name = instance.name
            
            # Check if vendor has any POs or payments before deleting
            pos_count = PurchaseOrder.objects.filter(vendor=instance).count()
            payments_count = VendorPayment.objects.filter(vendor=instance).count()
            ledger_count = VendorLedger.objects.filter(vendor=instance).count()
            
            # Delete related ledger entries first
            VendorLedger.objects.filter(vendor=instance).delete()
            
            # Delete payments
            VendorPayment.objects.filter(vendor=instance).delete()
            
            # Delete POs (cascade will handle PO items and receivings)
            PurchaseOrder.objects.filter(vendor=instance).delete()
            
            # Delete vendor
            instance.delete()
            
            return Response({
                'message': f'Vendor "{vendor_name}" and all related data deleted successfully',
                'deleted_pos': pos_count,
                'deleted_payments': payments_count,
                'deleted_ledger_entries': ledger_count
            }, status=status.HTTP_200_OK)
            
        except Vendor.DoesNotExist:
            return Response({'error': 'Vendor not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all().order_by('-created_at')
    serializer_class = PurchaseOrderSerializer

    def perform_create(self, serializer):
        """Create PO - No ledger entry here"""
        po = serializer.save()
        # ❌ PO create se ledger me kuch nahi jayega
        return po

    def get_queryset(self):
        queryset = PurchaseOrder.objects.all().order_by('-created_at')
        
        # Filter by vendor
        vendor_id = self.request.query_params.get('vendor')
        if vendor_id:
            queryset = queryset.filter(vendor_id=vendor_id)
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date (single date)
        date = self.request.query_params.get('date')
        if date:
            queryset = queryset.filter(order_date=date)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(order_date__range=[date_from, date_to])
        elif date_from:
            queryset = queryset.filter(order_date__gte=date_from)
        elif date_to:
            queryset = queryset.filter(order_date__lte=date_to)
        
        return queryset

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        po = self.get_object()
        new_status = request.data.get('status')
        if new_status not in dict(PurchaseOrder.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validations
        if po.status == 'cancelled':
            return Response({'error': 'Cannot change status of cancelled PO'}, status=400)
        if po.status == 'closed':
            return Response({'error': 'Cannot change status of closed PO'}, status=400)
        
        # Allow status changes
        po.status = new_status
        po.save()
        return Response({'status': po.status})

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download PO as PDF"""
        po = self.get_object()
        pdf_buffer = generate_po_pdf(po)
        response = FileResponse(
            pdf_buffer, 
            as_attachment=True, 
            filename=f"PO_{po.po_number}.pdf"
        )
        return response


class ReceivingViewSet(viewsets.ModelViewSet):
    queryset = Receiving.objects.all().order_by('-received_date')
    serializer_class = ReceivingSerializer

    def perform_create(self, serializer):
        """Create receiving and add credit entry in vendor ledger"""
        receiving = serializer.save()
        po = receiving.po
        
        # ✅ Add credit entry in vendor ledger (Invoice received)
        VendorLedger.objects.create(
            vendor=po.vendor,
            transaction_type='credit',
            invoice_no=receiving.invoice_no or f"REC-{receiving.id}",
            po_reference=po,
            amount=receiving.total_amount,
            description=f"Invoice {receiving.invoice_no or 'N/A'} - PO: {po.po_number}"
        )
        
        # Update PO status
        total_ordered = sum(item.quantity for item in po.items.all())
        total_received = ReceivingItem.objects.filter(
            receiving__po=po
        ).aggregate(total=Sum('received_qty'))['total'] or 0
        
        if total_received >= total_ordered:
            po.status = 'closed'
        else:
            po.status = 'partially_received'
        po.save()
        
        return receiving

    def get_queryset(self):
        queryset = Receiving.objects.all().order_by('-received_date')
        
        # Filter by PO
        po_id = self.request.query_params.get('po')
        if po_id:
            queryset = queryset.filter(po_id=po_id)
        
        # Filter by Invoice No
        invoice_no = self.request.query_params.get('invoice_no')
        if invoice_no:
            queryset = queryset.filter(invoice_no__icontains=invoice_no)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(received_date__range=[date_from, date_to])
        elif date_from:
            queryset = queryset.filter(received_date__gte=date_from)
        elif date_to:
            queryset = queryset.filter(received_date__lte=date_to)
        
        return queryset

    @action(detail=True, methods=['delete'])
    def delete_receiving(self, request, pk=None):
        """Delete a receiving entry and update PO status and ledger"""
        receiving = self.get_object()
        po = receiving.po
        
        # ✅ Delete ledger entry for this receiving
        VendorLedger.objects.filter(
            vendor=po.vendor,
            invoice_no=receiving.invoice_no
        ).delete()
        
        # Delete the receiving
        receiving.delete()
        
        # Update PO status based on remaining receivings
        total_ordered = sum(item.quantity for item in po.items.all())
        total_received = ReceivingItem.objects.filter(
            receiving__po=po
        ).aggregate(total=Sum('received_qty'))['total'] or 0
        
        if total_received >= total_ordered:
            po.status = 'closed'
        elif total_received > 0:
            po.status = 'partially_received'
        else:
            po.status = 'sent'
        
        po.save()
        
        return Response({'message': 'Receiving deleted successfully'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put', 'patch'])
    def update_receiving(self, request, pk=None):
        """Update a receiving entry and update ledger"""
        receiving = self.get_object()
        data = request.data
        
        # Update basic fields
        if 'invoice_no' in data:
            receiving.invoice_no = data['invoice_no']
        if 'invoice_date' in data:
            receiving.invoice_date = data['invoice_date']
        if 'gst_percentage' in data:
            receiving.gst_percentage = data['gst_percentage']
        if 'notes' in data:
            receiving.notes = data['notes']
        
        # Update items if provided
        if 'items' in data:
            # Delete old items
            receiving.items.all().delete()
            
            # Create new items
            subtotal = 0
            for item_data in data['items']:
                po_item = POItem.objects.get(id=item_data['po_item'])
                unit_price = item_data.get('unit_price', po_item.unit_price)
                received_qty = item_data['received_qty']
                total_price = received_qty * unit_price
                subtotal += total_price
                
                ReceivingItem.objects.create(
                    receiving=receiving,
                    po_item=po_item,
                    received_qty=received_qty,
                    unit_price=unit_price,
                    total_price=total_price,
                    accepted=item_data.get('accepted', True),
                    reject_reason=item_data.get('reject_reason', '')
                )
            
            # Calculate GST and total
            gst_percentage = receiving.gst_percentage or 0
            gst_amount = (subtotal * gst_percentage) / 100
            total_amount = subtotal + gst_amount
            
            receiving.subtotal = subtotal
            receiving.gst_amount = gst_amount
            receiving.total_amount = total_amount
            
            # ✅ Update ledger entry
            VendorLedger.objects.filter(
                vendor=receiving.po.vendor,
                invoice_no=receiving.invoice_no
            ).update(
                amount=total_amount,
                description=f"Invoice {receiving.invoice_no or 'N/A'} - Updated"
            )
        
        receiving.save()
        
        # Update PO status
        po = receiving.po
        total_ordered = sum(item.quantity for item in po.items.all())
        total_received = ReceivingItem.objects.filter(
            receiving__po=po
        ).aggregate(total=Sum('received_qty'))['total'] or 0
        
        if total_received >= total_ordered:
            po.status = 'closed'
        elif total_received > 0:
            po.status = 'partially_received'
        else:
            po.status = 'sent'
        po.save()
        
        serializer = ReceivingSerializer(receiving)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==================== FRONTEND VIEWS ====================

def dashboard(request):
    total_vendors = Vendor.objects.count()
    total_pos = PurchaseOrder.objects.count()
    
    # Status wise PO count
    status_counts = PurchaseOrder.objects.values('status').annotate(count=Count('id'))
    status_dict = {item['status']: item['count'] for item in status_counts}
    
    # Recent POs (last 10)
    recent_pos = PurchaseOrder.objects.all().order_by('-created_at')[:10]
    
    # Total amount of all POs
    total_amount = PurchaseOrder.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Pending POs (sent/partially_received)
    pending_pos = PurchaseOrder.objects.filter(status__in=['sent', 'partially_received']).count()
    
    # Today's POs
    today = datetime.now().date()
    today_pos = PurchaseOrder.objects.filter(order_date=today).count()
    
    context = {
        'total_vendors': total_vendors,
        'total_pos': total_pos,
        'status_counts': status_dict,
        'recent_pos': recent_pos,
        'total_amount': total_amount,
        'pending_pos': pending_pos,
        'today_pos': today_pos,
    }
    
    return render(request, 'purchase/dashboard.html', context)


def vendor_list(request):
    return render(request, 'purchase/vendor_list.html')


def po_list(request):
    return render(request, 'purchase/po_list.html')


def receiving_create(request):
    return render(request, 'purchase/receiving_create.html')


def receiving_list(request):
    return render(request, 'purchase/receiving_list.html')