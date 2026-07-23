from django.contrib import admin
from .models import Vendor, PurchaseOrder, POItem, Receiving, ReceivingItem

admin.site.register(Vendor)
admin.site.register(PurchaseOrder)
admin.site.register(POItem)
admin.site.register(Receiving)
admin.site.register(ReceivingItem)