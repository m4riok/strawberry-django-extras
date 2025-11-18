from typing import Generic, TypeVar

import strawberry
from strawberry import ID, UNSET
from strawberry.scalars import JSON

T_CREATE = TypeVar("T_CREATE")
T_UPDATE = TypeVar("T_UPDATE")


@strawberry.input(name="CRUDInput", description="CRUDInput Base Class for all CRUD Inputs")
class CRUDInput:
    pass


@strawberry.input(
    name="CRUDRemoveInput",
    description="Provides the ability to remove a related object with an optional boolean delete to delete the object after the fKey is assigned",
)
class CRUDRemoveInput:
    id: ID
    delete: bool | None = False


@strawberry.input(
    name="CRUDManyToManyItem",
    description="Provides through defaults and object data separately for ManyToMany relationships",
)
class CRUDManyToManyItem(Generic[T_CREATE]):
    object_data: T_CREATE
    through_defaults: JSON | None = UNSET  # pyright: ignore[reportInvalidTypeForm]


@strawberry.input(
    name="CRUDManyToManyItemUpdate",
    description="Provides through defaults and object data separately for ManyToMany relationships",
)
class CRUDManyToManyItemUpdate(Generic[T_UPDATE]):
    object_data: T_UPDATE
    through_defaults: JSON | None = UNSET  # pyright: ignore[reportInvalidTypeForm]


@strawberry.input(
    name="CRUDManyToManyID",
    description="Provides through defaults and object IDs to be assigned separately for ManyToMany relationships",
)
class CRUDManyToManyID:
    id: ID
    through_defaults: JSON | None = UNSET  # pyright: ignore[reportInvalidTypeForm]


# CREATE INPUTS
@strawberry.input(
    name="__One2OneCreateInput",
    description="Used for OneToOne relationships when creating an object. Allows to either create nested objects or assign existing objects to the newly created object.",
)
class CRUDOneToOneCreateInput(CRUDInput, Generic[T_CREATE]):
    create: T_CREATE | None = UNSET
    assign: ID | None = UNSET


@strawberry.input(
    name="__Many2OneCreateInput",
    description="Used for ManyToOne relationships when creating an object. Allows to either create nested objects or assign existing objects to the newly created object.",
)
class CRUDManyToOneCreateInput(CRUDInput, Generic[T_CREATE]):
    create: list[T_CREATE] | None = UNSET
    assign: list[ID] | None = UNSET


@strawberry.input(
    name="__One2ManyCreateInput",
    description="Used for OneToMany relationships when creating an object. Allows to either create nested objects or assign existing objects to the newly created object.",
)
class CRUDOneToManyCreateInput(CRUDInput, Generic[T_CREATE]):
    create: T_CREATE | None = UNSET
    assign: ID | None = UNSET


@strawberry.input(
    name="__Many2ManyCreateInput",
    description="Used for ManyToMany relationships when creating an object. Allows to either create nested objects or assign existing objects to the newly created object.",
)
class CRUDManyToManyCreateInput(CRUDInput, Generic[T_CREATE]):
    create: list[CRUDManyToManyItem[T_CREATE]] | None = UNSET
    assign: list[CRUDManyToManyID] | None = UNSET


# UPDATE INPUTS


@strawberry.input(
    name="__One2OneUpdateInput",
    description="Used for OneToOne relationships when updating an object. Supports nested creation, assignment to object or null if the field is nullable, updates to the data of existing related objects and an optional delete flag to delete the previously assigned object in case of reassignment.",
)
class CRUDOneToOneUpdateInput(CRUDInput, Generic[T_CREATE, T_UPDATE]):
    create: T_CREATE | None = UNSET
    assign: ID | None = UNSET
    update: T_UPDATE | None = UNSET
    delete: bool | None = False


@strawberry.input(
    name="__One2ManyUpdateInput",
    description="Used for OneToMany relationships when updating an object. Supports nested creation, assignment to object or null if the field is nullable, updates to the data of existing related objects and an optional delete flag to delete the previously assigned object in case of reassignment.",
)
class CRUDOneToManyUpdateInput(CRUDInput, Generic[T_CREATE, T_UPDATE]):
    create: T_CREATE | None = UNSET
    assign: ID | None = UNSET
    update: T_UPDATE | None = UNSET
    delete: bool | None = False


@strawberry.input(
    name="__Many2OneUpdateInput",
    description="Used for ManyToOne relationships when updating an object. Supports nested creation, assignment of objects, updates to the data of existing related objects (IDs must be provided by the Input) and removal of related with an optional delete flag to delete the previously assigned objects.",
)
class CRUDManyToOneUpdateInput(CRUDInput, Generic[T_CREATE, T_UPDATE]):
    create: list[T_CREATE] | None = UNSET
    update: list[T_UPDATE] | None = UNSET
    assign: list[ID] | None = UNSET
    remove: list[CRUDRemoveInput] | None = UNSET


@strawberry.input(
    name="__Many2ManyUpdateInput",
    description="Used for ManyToMany relationships when updating an object. Supports nested creation, assignment of objects, updates to the data of existing related objects (IDs must be provided by the Input) and removal of related with an optional delete flag to delete the previously assigned objects.",
)
class CRUDManyToManyUpdateInput(CRUDInput, Generic[T_CREATE, T_UPDATE]):
    create: list[CRUDManyToManyItem[T_CREATE]] | None = UNSET
    update: list[CRUDManyToManyItemUpdate[T_UPDATE]] | None = UNSET
    assign: list[CRUDManyToManyID] | None = UNSET
    remove: list[CRUDRemoveInput] | None = UNSET
