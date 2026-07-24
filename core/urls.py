from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from purchase.views import VendorViewSet, PurchaseOrderViewSet, ReceivingViewSet, dashboard, vendor_list, po_list, receiving_create, receiving_list

# ✅ Router define करें
router = DefaultRouter()
router.register(r'vendors', VendorViewSet)
router.register(r'pos', PurchaseOrderViewSet)
router.register(r'receivings', ReceivingViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),  # ✅ API URLs
    path('', dashboard, name='dashboard'),  # ✅ Dashboard
    path('vendors/', vendor_list, name='vendor_list'),
    path('pos/', po_list, name='po_list'),
    path('receiving/', receiving_create, name='receiving_create'),
    path('receiving-list/', receiving_list, name='receiving_list'),
]