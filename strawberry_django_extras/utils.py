from strawberry.type import StrawberryContainer


def unwrap_type(type_):
    while isinstance(type_, StrawberryContainer):
        type_ = type_.of_type

    return type_
