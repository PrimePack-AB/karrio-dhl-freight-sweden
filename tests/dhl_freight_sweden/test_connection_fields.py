"""Connection fields must serialize to dashboard-renderable input types.

The karrio dashboard renders an input box for a connection field only when
the server's reference builder serializes its attrs annotation to "string"
via ``karrio.references.parse_type``. A ``typing.Optional[str]`` annotation
serializes as its repr ("typing.Optional[str]"), which matches no widget, so
the field's label renders without an input box.
"""

import unittest

import attr

from karrio.mappers.dhl_freight_sweden.settings import Settings
from karrio.references import parse_type

CREDENTIAL_FIELDS = (
    "client_key",
    "account_number",
    "international_account_number",
)


class ConnectionFieldInputTest(unittest.TestCase):
    def test_credential_fields_serialize_as_string_inputs(self):
        fields = {field.name: field for field in attr.fields(Settings)}

        for name in CREDENTIAL_FIELDS:
            with self.subTest(field=name):
                self.assertEqual(parse_type(fields[name].type), "string")


if __name__ == "__main__":
    unittest.main()
