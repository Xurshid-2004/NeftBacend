from django.urls import path

from .views import (
    BalanceListView,
    ChangeView,
    ResetAllView,
    SetView,
    ShipmentAcceptView,
    ShipmentDeleteView,
    ShipmentListCreateView,
    SubtractView,
)

urlpatterns = [
    path("operator/balances/", BalanceListView.as_view(), name="operator-balances"),
    path("operator/subtract/", SubtractView.as_view(), name="operator-subtract"),
    path("operator/set/", SetView.as_view(), name="operator-set"),
    path("operator/change/", ChangeView.as_view(), name="operator-change"),
    path("operator/reset/", ResetAllView.as_view(), name="operator-reset"),
    path("operator/shipments/", ShipmentListCreateView.as_view(), name="operator-shipments"),
    path(
        "operator/shipments/<str:shipment_id>/accept/",
        ShipmentAcceptView.as_view(),
        name="operator-shipment-accept",
    ),
    path(
        "operator/shipments/<str:shipment_id>/",
        ShipmentDeleteView.as_view(),
        name="operator-shipment-delete",
    ),
]
