from rest_framework.routers import SimpleRouter

from .views import OrderViewSet

router = SimpleRouter(trailing_slash=False)
router.register("orders", OrderViewSet, basename="order")

urlpatterns = router.urls