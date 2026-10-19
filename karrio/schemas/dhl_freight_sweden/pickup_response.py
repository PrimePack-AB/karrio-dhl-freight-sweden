import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class PickupResponseType:
    status: typing.Optional[int] = None
    bookingNumber: typing.Optional[str] = None
    pickupDateTime: typing.Optional[str] = None
    message: typing.Optional[str] = None
