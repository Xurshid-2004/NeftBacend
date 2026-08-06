from django.urls import path

from .views import (
    BalanceListView,
    CentralTankDistributeView,
    CentralTankPurchaseView,
    CentralTankSubtractView,
    CentralTankView,
    ChangeView,
    ResetAllView,
    SetView,
    ShipmentAcceptView,
    ShipmentDeleteView,
    ShipmentListCreateView,
    ShipmentRequestAllowView,
    ShipmentRequestApproveView,
    ShipmentRequestListCreateView,
    ShipmentRequestRejectView,
    ShipmentRequestSendView,
    SubtractView,
)

urlpatterns = [
    path("operator/balances/", BalanceListView.as_view(), name="operator-balances"),
    path("operator/subtract/", SubtractView.as_view(), name="operator-subtract"),
    path("operator/set/", SetView.as_view(), name="operator-set"),
    path("operator/change/", ChangeView.as_view(), name="operator-change"),
    path("operator/reset/", ResetAllView.as_view(), name="operator-reset"),
    path("operator/central-tank/", CentralTankView.as_view(), name="operator-central-tank"),
    path(
        "operator/central-tank/purchase/",
        CentralTankPurchaseView.as_view(),
        name="operator-central-tank-purchase",
    ),
    path(
        "operator/central-tank/subtract/",
        CentralTankSubtractView.as_view(),
        name="operator-central-tank-subtract",
    ),
    path(
        "operator/central-tank/distribute/",
        CentralTankDistributeView.as_view(),
        name="operator-central-tank-distribute",
    ),
    # Yuborishga ruxsat so'rovlari — "shipments/<id>/" naqshidan OLDIN turishi
    # shart emas (yo'l boshqacha), lekin tartib uchun shu yerda.
    path(
        "operator/shipment-requests/",
        ShipmentRequestListCreateView.as_view(),
        name="operator-shipment-requests",
    ),
    path(
        "operator/shipment-requests/<str:request_id>/approve/",
        ShipmentRequestApproveView.as_view(),
        name="operator-shipment-request-approve",
    ),
    path(
        "operator/shipment-requests/<str:request_id>/allow/",
        ShipmentRequestAllowView.as_view(),
        name="operator-shipment-request-allow",
    ),
    path(
        "operator/shipment-requests/<str:request_id>/send/",
        ShipmentRequestSendView.as_view(),
        name="operator-shipment-request-send",
    ),
    path(
        "operator/shipment-requests/<str:request_id>/reject/",
        ShipmentRequestRejectView.as_view(),
        name="operator-shipment-request-reject",
    ),
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
