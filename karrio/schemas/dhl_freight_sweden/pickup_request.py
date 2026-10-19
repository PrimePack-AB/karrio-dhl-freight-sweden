import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class CashOnDeliveryType:
    amount: typing.Optional[float] = None
    bankGiroNumber: typing.Optional[str] = None
    plusGiroNumber: typing.Optional[str] = None
    reference: typing.Optional[str] = None
    currency: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class InsuranceType:
    value: typing.Optional[float] = None
    currency: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class PreAdviceByDriverType:
    phone: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ThermoType:
    min: typing.Optional[float] = None
    max: typing.Optional[float] = None


@attr.s(auto_attribs=True)
class TimeDefiniteLoadingType:
    dateTime: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class AdditionalServicesType:
    cashOnDelivery: typing.Optional[CashOnDeliveryType] = jstruct.JStruct[CashOnDeliveryType]
    dangerousGoods: typing.Optional[bool] = None
    dangerousGoodsDomestic: typing.Optional[bool] = None
    deliveryAtConstructionSite: typing.Optional[bool] = None
    deliveryWithoutProofOfDelivery: typing.Optional[bool] = None
    dangerousGoodsLimitedQuantity: typing.Optional[bool] = None
    emptyPalletPickup: typing.Optional[bool] = None
    indoorDelivery: typing.Optional[bool] = None
    notification: typing.Optional[bool] = None
    insurance: typing.Optional[InsuranceType] = jstruct.JStruct[InsuranceType]
    preAdviceByDriver: typing.Optional[PreAdviceByDriverType] = jstruct.JStruct[PreAdviceByDriverType]
    tailLiftLoading: typing.Optional[bool] = None
    tailLiftUnloading: typing.Optional[bool] = None
    thermoCold: typing.Optional[ThermoType] = jstruct.JStruct[ThermoType]
    thermoFreeze: typing.Optional[ThermoType] = jstruct.JStruct[ThermoType]
    thermoWarm: typing.Optional[ThermoType] = jstruct.JStruct[ThermoType]
    timeDefiniteLoading: typing.Optional[TimeDefiniteLoadingType] = jstruct.JStruct[TimeDefiniteLoadingType]
    timeDefiniteUnloading: typing.Optional[TimeDefiniteLoadingType] = jstruct.JStruct[TimeDefiniteLoadingType]
    twoManHandling: typing.Optional[bool] = None
    priorityServiceG7: typing.Optional[bool] = None
    priorityServiceG10: typing.Optional[bool] = None
    priorityServiceG12: typing.Optional[bool] = None
    truck: typing.Optional[bool] = None
    preAdvicePickup: typing.Optional[bool] = None
    preAdviceByDriverPickup: typing.Optional[PreAdviceByDriverType] = jstruct.JStruct[PreAdviceByDriverType]


@attr.s(auto_attribs=True)
class AddressType:
    street: typing.Optional[str] = None
    streetNumber: typing.Optional[str] = None
    additionalAddressInfo: typing.Optional[str] = None
    cityName: typing.Optional[str] = None
    postalCode: typing.Optional[str] = None
    countryCode: typing.Optional[str] = None
    accessCode: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class PartyType:
    id: typing.Optional[str] = None
    type: typing.Optional[str] = None
    name: typing.Optional[str] = None
    contactName: typing.Optional[str] = None
    references: typing.Optional[typing.List[str]] = None
    address: typing.Optional[AddressType] = jstruct.JStruct[AddressType]
    phone: typing.Optional[str] = None
    email: typing.Optional[str] = None
    fax: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class PayerCodeType:
    code: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class PieceType:
    id: typing.Optional[typing.List[str]] = None
    goodsType: typing.Optional[str] = None
    packageType: typing.Optional[str] = None
    marksAndNumbers: typing.Optional[str] = None
    numberOfPieces: typing.Optional[int] = None
    weight: typing.Optional[float] = None
    volume: typing.Optional[float] = None
    loadingMeters: typing.Optional[float] = None
    loadingMetres: typing.Optional[float] = None
    palletPlaces: typing.Optional[float] = None
    width: typing.Optional[float] = None
    height: typing.Optional[float] = None
    length: typing.Optional[float] = None
    stackable: typing.Optional[bool] = None


@attr.s(auto_attribs=True)
class PickupRequestType:
    id: typing.Optional[str] = None
    productCode: typing.Optional[str] = None
    pickupDate: typing.Optional[str] = None
    pickupInstruction: typing.Optional[str] = None
    deliveryInstruction: typing.Optional[str] = None
    totalNumberOfPieces: typing.Optional[int] = None
    totalWeight: typing.Optional[float] = None
    totalVolume: typing.Optional[float] = None
    totalLoadingMeters: typing.Optional[float] = None
    totalLoadingMetres: typing.Optional[float] = None
    totalPalletPlaces: typing.Optional[float] = None
    payerCode: typing.Optional[PayerCodeType] = jstruct.JStruct[PayerCodeType]
    parties: typing.Optional[typing.List[PartyType]] = jstruct.JList[PartyType]
    pieces: typing.Optional[typing.List[PieceType]] = jstruct.JList[PieceType]
    additionalServices: typing.Optional[AdditionalServicesType] = jstruct.JStruct[AdditionalServicesType]
