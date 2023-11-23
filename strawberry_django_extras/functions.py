from __future__ import annotations

from typing import List

from django.db import models, transaction
from django.db.models.fields.related import (
    ForeignKey,
    ManyToManyField,
    ManyToManyRel,
    ManyToOneRel,
    OneToOneField,
    OneToOneRel,
)
from strawberry import UNSET
from strawberry.utils.str_converters import to_camel_case
from strawberry_django.utils.inspect import get_model_fields

from .exceptions import SDJExtrasError
from .inputs import (
    CRUDManyToManyCreateInput,
    CRUDManyToManyUpdateInput,
    CRUDManyToOneCreateInput,
    CRUDManyToOneUpdateInput,
    CRUDOneToManyCreateInput,
    CRUDOneToManyUpdateInput,
    CRUDOneToOneCreateInput,
    CRUDOneToOneUpdateInput,
)


@transaction.atomic
def kill_a_rabbit(  # noqa: PLR0912, PLR0913, PLR0915
    data,
    caller_data,
    is_before=True,
    is_root: bool = False,
    next_=None,
    source=None,
    info=None,
    ni=None,
):
    if data.get("before"):
        for item in data.get("before"):
            kill_a_rabbit(item, data)

    obj = None
    if is_root:
        obj = next_(source, info, **{"data": ni})  # noqa: PIE804
        # this is necessary because when I have a nested update input with a OneToOneField down the chain
        # strawberry_django will not update parent object correctly and will have a Traceback in the place
        # of the related One2One object
        for k, v in data.get("data").items():
            setattr(obj, k, v)
        obj.save()

    else:  # noqa: PLR5501
        if data.get("operation") == "create":
            if data.get("m2m", False) is True:
                manager = data.get("manager")
                obj = (
                    manager.create(
                        **data.get("data"),
                        through_defaults=data.get("through_defaults"),
                    )
                    if data.get("through_defaults", None) is not None
                    else manager.create(**data.get("data"))
                )
            else:
                obj = data.get("model").objects.create(**data.get("data"))

        elif data.get("operation") == "assign":
            if data.get("m2m", False) is True:
                manager = data.get("manager")
                if data.get("data").through_defaults is not None:
                    manager.add(
                        data.get("data").id,
                        through_defaults=data.get("data").through_defaults,
                    )
                else:
                    manager.add(data.get("data").id)
                obj = manager.get(pk=data.get("data").id)

        elif data.get("operation") == "update":
            if data.get("m2m", False) is True:
                manager = data.get("manager")
                obj = manager.get(pk=data.get("data").get("id"))
                for k, v in data.get("data").items():
                    setattr(obj, k, v)
                obj.save()
                if hasattr(manager, "through"):
                    # TODO: Check if this works for SYMMETRICAL m2m
                    im = manager.through.objects.get(
                        **{
                            manager.source_field_name: data.get("p_obj"),
                            manager.target_field_name: obj,
                        },
                    )
                    for k, v in data.get("through_defaults", {}).items():
                        setattr(im, k, v)
                    im.save()

            else:  # noqa: PLR5501
                if data.get("manager", None) is not None:
                    obj = data.get("manager").get(pk=data.get("pk"))
                    for k, v in data.get("data").items():
                        setattr(obj, k, v)
                    obj.save()
                else:
                    obj = data.get("model").objects.get(pk=data.get("pk"))
                    for k, v in data.get("data").items():
                        setattr(obj, k, v)
                    obj.save()

        elif data.get("operation") == "remove":
            if data.get("m2m", False) is True:
                manager = data.get("manager")
                if data.get("data").get("delete") is True:
                    manager.get(pk=int(data.get("data").get("id"))).delete()
                else:
                    manager.remove(data.get("data").get("id"))

        elif data.get("operation") == "skip":
            pass

        else:
            raise SDJExtrasError("Unknown operation")

    if data.get("set_manager", False) is True and obj is not None:
        for item in data.get("after"):
            if item.get("m2m", False) is True and item.get("manager", None) is None:
                item.update({"manager": getattr(obj, item.get("accessor"))})

    if is_before:  # noqa: SIM102
        # Only necessary for create operations
        if data.get("operation") in ["create", "update"]:
            caller_data.get("data").update({data.get("data_id"): obj})

    if data.get("after"):
        for item in data.get("after"):
            if item.get("m2m", False) is False and item.get("operation", None) == "create":
                item.get("data").update({item.get("rel_data_id"): obj})
            kill_a_rabbit(item, data, False)

    if data.get("assignments"):
        for assignment in data.get("assignments"):
            assignment.get("objs").update(**{assignment.get("assignment_id"): obj})

    if data.get("deletions"):
        for deletion in data.get("deletions"):
            if data.get("manager", None) is not None:
                deletion.get("manager").filter(pk__in=deletion.get("pks")).delete()
            else:
                deletion.get("model").objects.filter(
                    pk__in=deletion.get("pks"),
                ).delete()

    if data.get("removals"):
        for removal in data.get("removals"):
            if data.get("manager", None) is not None:
                removal.get("manager").filter(pk__in=removal.get("pks")).update(
                    **{removal.get("rel_data_id"): None},
                )
            else:
                removal.get("model").objects.filter(pk__in=removal.get("pks")).update(
                    **{removal.get("rel_data_id"): None},
                )

    if is_root:
        return obj
    return None


# noinspection DuplicatedCode
def rabbit_hole(model, _input, rel, through_defaults=None):  # noqa: PLR0912, PLR0915
    if (
        hasattr(_input, "__strawberry_definition__")
        and _input.__strawberry_definition__.is_input is True
    ):
        field_items = get_model_fields(model).items()

        fields = {
            k: v
            for k, v in field_items
            if hasattr(_input, k) and _input.__dict__.get(k) is not UNSET
        }

        rel.update(
            {
                "model": model,
                "before": [],
                "after": [],
                "data": {},
                "assignments": [],
                "removals": [],
                "deletions": [],
                "set_manager": False,
                "through_defaults": through_defaults,
            },
        )
        for key, val in fields.items():
            if isinstance(val, (OneToOneField, OneToOneRel)):
                _rel_input = _input.__dict__.get(key)
                when = "after" if isinstance(val, OneToOneRel) else "before"
                if isinstance(_rel_input, CRUDOneToOneCreateInput):
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign")
                    if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                        raise SDJExtrasError(
                            "Cannot create and assign at the same time",
                        )
                    if _rel_input.assign is not UNSET:
                        rel.get("data").update(
                            {
                                key: val.related_model.objects.get(
                                    pk=int(_rel_input.assign),
                                ),
                            },
                        )
                    if _rel_input.create is not UNSET:
                        rel[when].append(
                            {
                                "data_id": key,
                                "operation": "create",
                                "rel_data_id": val.remote_field.name,
                            },
                        )
                        rabbit_hole(
                            val.related_model,
                            _input.__dict__.get(key).create,
                            rel[when][-1],
                        )

                if isinstance(_rel_input, CRUDOneToOneUpdateInput):
                    parent_instance = model.objects.get(pk=int(_input.id))
                    try:
                        existing_instance = getattr(parent_instance, key)
                    except val.related_model.DoesNotExist:
                        existing_instance = None

                    if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                        raise SDJExtrasError(
                            "You can either create a new object or assign an existing"
                            " one but not both at the same time",
                        )
                    if _rel_input.update is not UNSET and (
                        _rel_input.assign is not UNSET or _rel_input.create is not UNSET
                    ):
                        raise SDJExtrasError(
                            "Updating an object is only supported without" " create/assign.",
                        )
                    if _rel_input.assign is not UNSET:
                        if isinstance(val, OneToOneRel):
                            if val.remote_field.null is False:
                                if _rel_input.delete is not True and existing_instance is not None:
                                    raise SDJExtrasError(
                                        f"There is a {key} already assigned to this"
                                        f" {val.remote_field.name} and the field is not"
                                        " nullable. Maybe specify delete to replace"
                                        f" the {key} ?",
                                    )
                            else:  # noqa: PLR5501
                                if _rel_input.delete is not True and existing_instance is not None:
                                    rel["before"].append(
                                        {
                                            "operation": "skip",
                                            "removals": [
                                                {
                                                    "model": val.related_model,
                                                    "rel_data_id": (val.remote_field.name),
                                                    "pks": [existing_instance.pk],
                                                },
                                            ],
                                        },
                                    )

                            if _rel_input.assign is not None:
                                rel.get("data").update(
                                    {
                                        key: val.related_model.objects.get(
                                            pk=_rel_input.assign,
                                        ),
                                    },
                                )

                        elif isinstance(val, OneToOneField):
                            if _rel_input.assign is None:
                                if val.null is False:
                                    raise SDJExtrasError(
                                        "Cannot assign null to non nullable field",
                                    )
                                rel.get("data").update({key: None})
                            else:
                                rel.get("data").update(
                                    {
                                        key: val.related_model.objects.get(
                                            pk=_rel_input.assign,
                                        ),
                                    },
                                )

                        else:
                            raise SDJExtrasError("Invalid field type for %s" % key)
                    if _rel_input.create is not UNSET:
                        if (
                            isinstance(val, OneToOneRel)
                            and _rel_input.delete is not True
                            and existing_instance is not None
                        ):
                            if val.remote_field.null is False:
                                raise SDJExtrasError(
                                    f"There is a {key} already assigned to this"
                                    f" {val.remote_field.name}. Maybe specify delete to"
                                    f" replace the {key} ?",
                                )
                            else:  # noqa: RET506
                                rel["before"].append(
                                    {
                                        "operation": "skip",
                                        "removals": [
                                            {
                                                "model": val.related_model,
                                                "rel_data_id": val.remote_field.name,
                                                "pks": [existing_instance.pk],
                                            },
                                        ],
                                    },
                                )

                        rel[when].append(
                            {
                                "data_id": key,
                                "operation": "create",
                                "rel_data_id": val.remote_field.name,
                            },
                        )
                        rabbit_hole(
                            val.related_model,
                            _input.__dict__.get(key).create,
                            rel[when][-1],
                        )
                    if _rel_input.update is not UNSET:
                        if existing_instance is None:
                            raise SDJExtrasError("Cannot update non existing object")
                        _rel_input.update.id = existing_instance.pk
                        rel[when].append(
                            {
                                "data_id": key,
                                "operation": "update",
                                "pk": existing_instance.pk,
                            },
                        )
                        rabbit_hole(
                            val.related_model,
                            _input.__dict__.get(key).update,
                            rel[when][-1],
                        )
                    if _rel_input.delete is True and existing_instance is not None:
                        if isinstance(val, OneToOneField):
                            if (
                                val.remote_field.on_delete is models.CASCADE
                                and _rel_input.assign is UNSET
                                and _rel_input.create is UNSET
                            ):
                                raise SDJExtrasError(
                                    "Deleting the child object when CASCADE has been"
                                    " set makes ZERO sense. Maybe delete the parent"
                                    " object instead ?",
                                )
                            rel["after"].append(
                                {
                                    "deletions": [
                                        {
                                            "model": val.related_model,
                                            "pks": [existing_instance.pk],
                                        },
                                    ],
                                    "operation": "skip",
                                },
                            )
                        elif isinstance(val, OneToOneRel):
                            rel["before"].append(
                                {
                                    "deletions": [
                                        {
                                            "model": val.related_model,
                                            "pks": [existing_instance.pk],
                                        },
                                    ],
                                    "operation": "skip",
                                },
                            )

            if isinstance(val, ForeignKey):
                _rel_input = _input.__dict__.get(key)
                if isinstance(_rel_input, CRUDOneToManyCreateInput):
                    if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                        raise SDJExtrasError(
                            "Cannot create and assign at the same time",
                        )
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign")
                    if _rel_input.assign is not UNSET:
                        rel.get("data").update(
                            {key: val.related_model.objects.get(pk=_rel_input.assign)},
                        )
                    if _rel_input.create is not UNSET:
                        rel["before"].append({"data_id": key, "operation": "create"})
                        rabbit_hole(
                            val.related_model,
                            _input.__dict__.get(key).create,
                            rel["before"][-1],
                        )

                elif isinstance(_rel_input, CRUDOneToManyUpdateInput):
                    if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                        raise SDJExtrasError(
                            "You can either create a new object or assign an existing"
                            " one but not both at the same time",
                        )
                    if _rel_input.update is not UNSET and (
                        _rel_input.assign is not UNSET or _rel_input.create is not UNSET
                    ):
                        raise SDJExtrasError(
                            "Updating an object is only supported without" " create/assign.",
                        )
                    if _rel_input.assign is not UNSET:
                        if _rel_input.assign is None:
                            if val.null is False:
                                raise SDJExtrasError(
                                    "Cannot assign null to non nullable field",
                                )
                            rel.get("data").update({key: None})
                        else:
                            rel.get("data").update(
                                {
                                    key: val.related_model.objects.get(
                                        pk=_rel_input.assign,
                                    ),
                                },
                            )
                    if _rel_input.create is not UNSET:
                        rel["before"].append({"data_id": key, "operation": "create"})
                        rabbit_hole(
                            val.related_model,
                            _input.__dict__.get(key).create,
                            rel["before"][-1],
                        )
                    if _rel_input.update is not UNSET:
                        rel_obj = getattr(
                            val.model.objects.get(pk=int(_input.id)),
                            val.name,
                        )
                        if rel_obj is None:
                            raise SDJExtrasError(
                                "Cannot update non existing object for key %s" % key,
                            )
                        _rel_input.update.id = rel_obj.pk
                        rel["before"].append(
                            {"data_id": key, "operation": "update", "pk": rel_obj.pk},
                        )
                        rabbit_hole(
                            val.related_model,
                            _input.__dict__.get(key).update,
                            rel["before"][-1],
                        )
                    if _rel_input.delete is True:
                        if _rel_input.assign is UNSET and _rel_input.create is UNSET:
                            raise SDJExtrasError(
                                "Cannot delete remote object without assigning or"
                                " creating a new one. If the relationship is nullable"
                                " you can assign null to unset the relationship",
                            )
                        if not hasattr(_input, "id") or _input.id is UNSET or _input.id is None:
                            raise SDJExtrasError(
                                "Cannot locate remote object to delete without id and"
                                " the parent update input had no id field provided.",
                            )
                        rel_obj = getattr(
                            val.model.objects.get(pk=int(_input.id)),
                            val.name,
                        )
                        rel["deletions"].append(
                            {"model": val.related_model, "pks": [rel_obj.pk]},
                        )

            elif isinstance(val, ManyToOneRel):
                _rel_input = _input.__dict__.get(key)
                if isinstance(_rel_input, CRUDManyToOneCreateInput):
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign or both")
                    if _rel_input.assign is not UNSET:
                        rel_objs = val.related_model.objects.filter(
                            pk__in=[int(pk) for pk in _rel_input.assign],
                        )
                        if rel_objs.count() != len(_rel_input.assign):
                            raise SDJExtrasError(
                                "Not all assigned objects found for %s"
                                % val.related_model.__name__,
                            )
                        rel["assignments"].append(
                            {"assignment_id": val.remote_field.name, "objs": rel_objs},
                        )
                    if _rel_input.create is not UNSET:
                        for item in _input.__dict__.get(key).create:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "rel_data_id": val.remote_field.name,
                                    "operation": "create",
                                },
                            )
                            rabbit_hole(val.related_model, item, rel["after"][-1])

                elif isinstance(_rel_input, CRUDManyToOneUpdateInput):
                    if _rel_input.assign is not UNSET:
                        rel_objs = val.related_model.objects.filter(
                            pk__in=[int(pk) for pk in _rel_input.assign],
                        )
                        if rel_objs.count() != len(_rel_input.assign):
                            raise SDJExtrasError(
                                "Not all assigned objects found for %s"
                                % val.related_model.__name__,
                            )
                        rel["assignments"].append(
                            {"assignment_id": val.remote_field.name, "objs": rel_objs},
                        )
                    if _rel_input.create is not UNSET:
                        for item in _input.__dict__.get(key).create:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "rel_data_id": val.remote_field.name,
                                    "operation": "create",
                                },
                            )
                            rabbit_hole(val.related_model, item, rel["after"][-1])
                    if _rel_input.update is not UNSET:
                        for item in _input.__dict__.get(key).update:
                            manager = getattr(
                                val.model.objects.get(pk=int(_input.id)),
                                val.get_accessor_name(),
                            )
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "rel_data_id": val.remote_field.name,
                                    "operation": "update",
                                    "pk": item.id,
                                    "manager": manager,
                                },
                            )
                            rabbit_hole(val.related_model, item, rel["after"][-1])
                    if _rel_input.remove is not UNSET:
                        del_pks = [
                            int(item.id)
                            for item in _input.__dict__.get(key).remove
                            if item.delete is True
                        ]
                        rem_pks = [
                            int(item.id)
                            for item in _input.__dict__.get(key).remove
                            if item.delete is not True
                        ]
                        if len(rem_pks) > 0 and val.remote_field.null is not True:
                            raise SDJExtrasError(
                                "Cannot remove remote objects from non nullable field"
                                f" ( rel: {key} , model: {val.related_model.__name__})",
                            )
                        manager = getattr(
                            val.model.objects.get(pk=int(_input.id)),
                            val.get_accessor_name(),
                        )
                        if len(del_pks) > 0:
                            rel["deletions"].append(
                                {
                                    "model": val.related_model,
                                    "pks": del_pks,
                                    "manager": manager,
                                },
                            )
                        if len(rem_pks) > 0:
                            rel["removals"].append(
                                {
                                    "model": val.related_model,
                                    "rel_data_id": val.remote_field.name,
                                    "pks": rem_pks,
                                    "manager": manager,
                                },
                            )

            elif isinstance(val, (ManyToManyField, ManyToManyRel)):
                _rel_input = _input.__dict__.get(key)
                if isinstance(_rel_input, CRUDManyToManyCreateInput):
                    if isinstance(val, ManyToManyField):
                        rel_name = val.name
                    elif isinstance(val, ManyToManyRel):
                        rel_name = val.get_accessor_name()
                    else:
                        raise SDJExtrasError(
                            "Unable to determine manager for %s" % val.__class__.__name__,
                        )
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign or both")
                    if _rel_input.create is not UNSET:
                        for item in _rel_input.create:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "operation": "create",
                                    "accessor": rel_name,
                                    "m2m": True,
                                },
                            )
                            rel.update({"set_manager": True})
                            rabbit_hole(
                                val.related_model,
                                item.object_data,
                                rel["after"][-1],
                                through_defaults=item.through_defaults,
                            )
                    if _rel_input.assign is not UNSET:
                        for item in _rel_input.assign:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "operation": "assign",
                                    "accessor": rel_name,
                                    "m2m": True,
                                    "data": item,
                                },
                            )
                            rel.update({"set_manager": True})
                            rabbit_hole(
                                val.related_model,
                                item.id,
                                rel["after"][-1],
                                through_defaults=item.through_defaults,
                            )

                if isinstance(_rel_input, CRUDManyToManyUpdateInput):
                    if isinstance(val, ManyToManyField):
                        rel_name = val.name
                    elif isinstance(val, ManyToManyRel):
                        rel_name = val.get_accessor_name()
                    else:
                        raise SDJExtrasError(
                            "Unable to determine manager for %s" % val.__class__.__name__,
                        )
                    p_obj = val.model.objects.get(pk=int(_input.id))
                    manager = getattr(p_obj, rel_name)
                    if _rel_input.create is not UNSET:
                        for item in _rel_input.create:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "operation": "create",
                                    "accessor": rel_name,
                                    "manager": manager,
                                    "m2m": True,
                                },
                            )

                            rabbit_hole(
                                val.related_model,
                                item.object_data,
                                rel["after"][-1],
                                through_defaults=item.through_defaults,
                            )
                    if _rel_input.assign is not UNSET:
                        for item in _rel_input.assign:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "operation": "assign",
                                    "accessor": rel_name,
                                    "manager": manager,
                                    "m2m": True,
                                    "data": item,
                                },
                            )
                            rabbit_hole(
                                val.related_model,
                                item.id,
                                rel["after"][-1],
                                through_defaults=item.through_defaults,
                            )
                    if _rel_input.update is not UNSET:
                        for item in _rel_input.update:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "operation": "update",
                                    "accessor": rel_name,
                                    "manager": manager,
                                    "m2m": True,
                                    "p_obj": p_obj,
                                },
                            )

                            rabbit_hole(
                                val.related_model,
                                item.object_data,
                                rel["after"][-1],
                                through_defaults=item.through_defaults,
                            )
                    if _rel_input.remove is not UNSET:
                        for item in _rel_input.remove:
                            rel["after"].append(
                                {
                                    "data_id": key,
                                    "operation": "remove",
                                    "accessor": rel_name,
                                    "manager": manager,
                                    "m2m": True,
                                    "data": item.__dict__,
                                },
                            )

            else:
                rel["data"].update({key: _input.__dict__.get(key)})


# noinspection DuplicatedCode
def perform_validation(_input, info):
    if isinstance(_input, List):
        for item in _input:
            perform_validation(item, info)

    if (
        hasattr(_input, "__strawberry_definition__")
        and _input.__strawberry_definition__.is_input is True
    ):
        for v in _input.__dict__.values():
            if isinstance(v, List):
                for item in v:
                    perform_validation(item, info)

            if (
                hasattr(v, "__strawberry_definition__")
                and v.__strawberry_definition__.is_input is True
            ):
                perform_validation(v, info)

        if hasattr(_input, "validate") and callable(_input.validate):
            _input.validate(info)

        for key, val in _input.__dict__.items():
            if val is not None and val is not UNSET:
                if hasattr(_input, f"validate_{to_camel_case(key)}") and callable(
                    getattr(_input, f"validate_{to_camel_case(key)}")
                ):
                    getattr(_input, f"validate_{to_camel_case(key)}")(info, val)
                    continue

                if hasattr(_input, f"validate_{key}") and callable(
                    getattr(_input, f"validate_{key}")
                ):
                    getattr(_input, f"validate_{key}")(info, val)
                    continue


# noinspection DuplicatedCode
def check_permissions(_input, info):
    if isinstance(_input, List):
        for item in _input:
            check_permissions(item, info)

    if (
        hasattr(_input, "__strawberry_definition__")
        and _input.__strawberry_definition__.is_input is True
    ):
        for v in _input.__dict__.values():
            if isinstance(v, List):
                for item in v:
                    check_permissions(item, info)

            if (
                hasattr(v, "__strawberry_definition__")
                and v.__strawberry_definition__.is_input is True
            ):
                check_permissions(v, info)

        if hasattr(_input, "check_permissions") and callable(_input.check_permissions):
            _input.check_permissions(info)

        for key, val in _input.__dict__.items():
            if val is not None and val is not UNSET:
                if hasattr(_input, f"check_permissions_{to_camel_case(key)}") and callable(
                    getattr(_input, f"check_permissions_{to_camel_case(key)}")
                ):
                    getattr(_input, f"check_permissions_{to_camel_case(key)}")(info, val)
                    continue

                if hasattr(_input, f"check_permissions_{key}") and callable(
                    getattr(_input, f"check_permissions_{key}")
                ):
                    getattr(_input, f"check_permissions_{key}")(info, val)
                    continue
