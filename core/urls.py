from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from purchase.views import VendorViewSet, PurchaseOrderViewSet, ReceivingViewSet

# API Router
router = DefaultRouter()
router.register(r'vendors', VendorViewSet)
router.register(r'pos', PurchaseOrderViewSet)
router.register(r'receivings', ReceivingViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)), 
    path('', include('purchase.urls')), 
    path('', include('purchase.urls')), 
]