from django.urls import path
from . import views
from . import extra_views
urlpatterns = [path("pricing/",extra_views.pricing,name="pricing"),path("batches/",extra_views.batches,name="batches")]
urlpatterns += [path("customers/<int:pk>/prices/",extra_views.customer_prices,name="customer_prices")]
urlpatterns += [path("visits/",extra_views.visits,name="visits"),path("invoices/<int:pk>/mock/",extra_views.mock_documents,name="mock_documents"),path("reports/tally/",extra_views.tally_download,name="tally_download")]
urlpatterns += [path("offline/",views.offline_shell,name="offline"),path("offline/catalog/",views.offline_catalog),path("offline/sync/",views.offline_sync),path("service-worker.js",views.service_worker),path("reports/",views.reports,name="reports"),path("invoices/<int:pk>/pdf/",views.download_invoice,name="invoice_pdf"),path("",views.home,name="home"),path("orders/",views.orders,name="orders"),path("orders/<int:pk>/",views.order_detail,name="order"),path("production/",views.production,name="production"),path("production/<int:pk>/",views.run_detail,name="run"),path("stock/",views.stock,name="stock"),path("stock/<str:code>/",views.ledger,name="ledger"),path("sources/<int:pk>/",views.source_document,name="source")]
