---
title: "Duplicating a shipment carries hidden connector options"
created: 2026-10-06
---

## Status

The user reported this behaviour on 2026-10-06, and it has not been verified in this repository.

## Reported behaviour

In the Karrio dashboard, duplicating a previous shipment copies its options, including the `dhl_freight_sweden_service_point*` options set through the API.
Selecting a different service on the copy then fails with a connector field error such as "Product 601 to PL accepts no access point; got ParcelShop" (`ServicePointEligibilityError`).
Upstream Karrio has no service-point selection in its user interface, so an operator can neither see nor clear those options.
A shipment created through the API with service-point options therefore cannot be given a different service from the dashboard.
The SENT free option (`dhl_freight_sweden_sent_free`) is likewise carried over and hidden from the operator.

## Decisions and open direction

Editing the dashboard's exposed `metadata` field is not the intended remedy (user decision, 2026-10-06).
A remedy on the plugin's user-interface side or in the connector, where possible, is an open direction that has not been investigated.
