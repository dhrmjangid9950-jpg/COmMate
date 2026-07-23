from django.db import models
from django.core.validators import MinValueValidator

class Vendor(models.Model):
    name = models.CharField(max_length=255)
    registration_no = models.CharField(max_length=50, blank=True, null=True, unique=True)  # ✅ Vendor Registration No.
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    gst_no = models.CharField(max_length=20, blank=True, null=True) 
    pan_no = models.CharField(max_length=20, blank=True, null=True)  # ✅ PAN Number
    bank_name = models.CharField(max_length=100, blank=True, null=True)  # ✅ Bank Name
    bank_account_no = models.CharField(max_length=50, blank=True, null=True)  # ✅ Bank Account
    bank_ifsc = models.CharField(max_length=20, blank=True, null=True)  # ✅ IFSC Code
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('partially_received', 'Partially Received'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    )
    po_number = models.CharField(max_length=50, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    order_date = models.DateField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # ✅ Subtotal (without tax)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # ✅ Total Tax
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PO {self.po_number}"

class POItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ Subtotal (qty * unit_price)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ Tax Amount
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ Total (subtotal + tax)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        self.tax_amount = (self.subtotal * self.gst_rate) / 100
        self.total_price = self.subtotal + self.tax_amount
        super().save(*args, **kwargs)

class Receiving(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receivings')
    received_date = models.DateField(auto_now_add=True)
    invoice_date = models.DateField(blank=True, null=True) 
    invoice_no = models.CharField(max_length=100)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # ✅ नया
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ नया
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ नया
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ नया
    notes = models.TextField(blank=True)

class ReceivingItem(models.Model):
    receiving = models.ForeignKey(Receiving, on_delete=models.CASCADE, related_name='items')
    po_item = models.ForeignKey(POItem, on_delete=models.CASCADE)
    received_qty = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ नया
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    accepted = models.BooleanField(default=True)
    reject_reason = models.TextField(blank=True)

class VendorLedger(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),  # Invoice raised (Purchase)
        ('debit', 'Debit'),    # Payment made
        ('opening', 'Opening Balance'),
    )
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='ledger_entries')
    transaction_date = models.DateField(auto_now_add=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    po_reference = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vendor.name} - {self.transaction_type} - {self.amount}"


class VendorPayment(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(auto_now_add=True)
    payment_mode = models.CharField(max_length=50, choices=(
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('upi', 'UPI'),
        ('other', 'Other'),
    ))
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vendor.name} - {self.payment_mode} - {self.amount}"