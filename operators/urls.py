from django.urls import path

from .views import BalanceListView, ChangeView, SetView, SubtractView

urlpatterns = [
    path("operator/balances/", BalanceListView.as_view(), name="operator-balances"),
    path("operator/subtract/", SubtractView.as_view(), name="operator-subtract"),
    path("operator/set/", SetView.as_view(), name="operator-set"),
    path("operator/change/", ChangeView.as_view(), name="operator-change"),
]
