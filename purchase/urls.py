from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'purchase'

router = DefaultRouter()
router.register(r'vendors', views.VendorViewSet)
router.register(r'pos', views.PurchaseOrderViewSet)
router.register(r'receivings', views.ReceivingViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.dashboard, name='dashboard'),
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('pos/', views.po_list, name='po_list'),
    path('receiving/', views.receiving_create, name='receiving_create'),
    path('receiving-list/', views.receiving_list, name='receiving_list'),
]