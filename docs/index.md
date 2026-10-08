---
title: "karrio DHL Freight Sweden"
template: splash
hero:
  tagline: A karrio carrier plugin that books DHL Freight Sweden shipments and returns their labels.
  actions:
    - text: Booking rules
      link: /karrio-dhl-freight-sweden/concepts/booking-rules/
    - text: Development
      link: /karrio-dhl-freight-sweden/development/
      variant: secondary
    - text: README on GitHub
      link: https://github.com/PrimePack-AB/karrio-dhl-freight-sweden#readme
      variant: minimal
---

## What the connector does

The connector registers with karrio as the `dhl_freight_sweden` carrier and books shipments through the DHL Freight (Sweden) API Farm, printing each label in the same call.
It also rates from a static rate sheet, validates addresses, and looks up the products and service points DHL offers for an address.
The README is the consumer guide to installing, connecting, and booking; this site holds the reference pages behind it.

## Concepts

The concept pages explain the rules the connector applies before it books, each with its product manual citation and evidence.

- [Booking rules](concepts/booking-rules.md)
- [Destinations](concepts/destinations.md)
- [Products](concepts/products.md)
- [Labels](concepts/labels.md)

## Guides

The guides cover the connector-local lookups and running the opt-in suite against the DHL sandbox.

- [Service-point lookups](guides/lookups.md)
- [Running the sandbox suite](guides/sandbox-runs.md)

## Development

The development pages are for working on the connector itself: setup and tests, the package layout, this documentation site, and the sandbox evidence.

- [Development](development/index.md)
- [Plugin layout](development/architecture/plugin-layout.md)
- [Documentation site](development/architecture/docs-site.md)
- [Sandbox suite and evidence](development/traceability/sandbox-suite.md)
