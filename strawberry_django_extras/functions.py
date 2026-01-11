from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
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
def kill_a_rabbit(  # noqa: PLR0912, PLR0913, PLR0915, PLR0917
    data,
    caller_data,
    is_before=True,
    is_root: bool = False,
    next_=None,
    source=None,
    info=None,
    ni=None,
    argument_name="data",
):
    if data.get("before"):
        for item in data.get("before"):
            kill_a_rabbit(item, data)

    obj = None
    if is_root:
        obj = next_(source, info, **{argument_name: ni})  # pyright: ignore[reportOptionalCall]
        # this is necessary because when I have a nested update input with a OneToOneField down the chain
        # strawberry_django will not update parent object correctly and will have a Traceback in the place
        # of the related One2One object
        for k, v in data.get("data").items():
            setattr(obj, k, v)
        obj.save()

    else:  # noqa: PLR5501
        if data.get("operation") == "create":
            if data.get("is_generic_fk_target"):
                obj = data.get("model").objects.create(**data.get("data"))

                parent_data = caller_data.get("data")
                parent_data.update({
                    data.get("parent_ct_field"): data.get("target_ct"),
                    data.get("parent_fk_field"): obj.pk,
                })

            elif data.get("m2m", False) is True:
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
            data_id = data.get("data_id")
            if data_id is not None and data_id is not UNSET:
                caller_data.get("data").update({data_id: obj})

    if data.get("after"):
        for item in data.get("after"):
            if item.get("m2m", False) is False and item.get("operation", None) == "create":
                if item.get("is_generic_relation"):
                    fk_field_name = item.get("fk_field_name")
                    if fk_field_name not in item.get("data"):
                        item.get("data").update({fk_field_name: obj.pk})  # pyright: ignore[reportOptionalMemberAccess]
                else:
                    item.get("data").update({item.get("rel_data_id"): obj})
            kill_a_rabbit(item, data, False)

    if data.get("assignments"):
        for assignment in data.get("assignments"):
            assignment.get("objs").update(**{assignment.get("assignment_id"): obj})

    if data.get("generic_assignments"):
        parent_obj = data.get("obj") or obj

        for assignment in data.get("generic_assignments"):
            parent_ct = assignment["parent_ct"]
            qs = assignment["model"].objects.filter(
                pk__in=assignment.get("pks") or [assignment["pk"]]
            )

            updated = qs.update(**{
                assignment["ct_field_name"]: parent_ct,
                assignment["fk_field_name"]: parent_obj.pk,  # pyright: ignore[reportOptionalMemberAccess]
            })

            if updated == 0:
                raise SDJExtrasError("No targets available for assignment")

    if data.get("deletions"):
        for deletion in data.get("deletions"):
            if data.get("manager", None) is not None:
                deletion.get("manager").filter(pk__in=deletion.get("pks")).delete()
            else:
                deletion.get("model").objects.filter(
                    pk__in=deletion.get("pks"),
                ).delete()

    if data.get("generic_removals"):
        parent_obj = data.get("obj") or obj

        for removal in data.get("generic_removals"):
            parent_ct = removal["parent_ct"]
            updated = (
                removal["model"]
                .objects.filter(
                    pk__in=removal["pks"],
                    **{
                        removal["ct_field_name"]: parent_ct,
                        removal["fk_field_name"]: parent_obj.pk,  # pyright: ignore[reportOptionalMemberAccess]
                    },
                )
                .update(
                    **{
                        removal["ct_field_name"]: None,
                        removal["fk_field_name"]: None,
                    },
                )
            )
            if updated != len(removal["pks"]):
                raise SDJExtrasError("Some targets were not attached to this parent")

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
def rabbit_hole(model, _input, rel, through_defaults=None):  # noqa: PLR0912, PLR0914, PLR0915
    if (  # noqa: PLR1702
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
            if isinstance(val, GenericForeignKey):
                _rel_input = _input.__dict__.get(key)  # noqa: RUF052
                ct_field = val.ct_field
                fk_field = val.fk_field

                if isinstance(_rel_input, CRUDOneToManyCreateInput):
                    if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                        raise SDJExtrasError("Cannot create and assign at the same time")
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign")

                    if _rel_input.assign is not UNSET and _rel_input.assign is not None:
                        target_model = None
                        target_pk = None
                        for field_name in _rel_input.assign.__dataclass_fields__:
                            value = getattr(_rel_input.assign, field_name)
                            if value is not None and value is not UNSET:
                                target_model = _rel_input.assign._model_mapping[field_name]  # noqa: SLF001
                                target_pk = int(value)
                                break

                        if target_model is None:
                            raise SDJExtrasError("oneOf input has no field set")

                        content_type = ContentType.objects.get_for_model(target_model)
                        rel.get("data").update({
                            ct_field: content_type,
                            fk_field: target_pk,
                        })

                    if _rel_input.create is not UNSET and _rel_input.create is not None:
                        target_model = None
                        target_data = None
                        for field_name in _rel_input.create.__dataclass_fields__:
                            value = getattr(_rel_input.create, field_name)
                            if value is not None and value is not UNSET:
                                target_model = _rel_input.create._model_mapping[field_name]  # noqa: SLF001
                                target_data = value
                                break

                        if target_model is None:
                            raise SDJExtrasError("oneOf input has no field set")

                        target_ct = ContentType.objects.get_for_model(target_model)
                        rel["before"].append({
                            "operation": "create",
                            "is_generic_fk_target": True,
                            "target_ct": target_ct,
                            "parent_ct_field": ct_field,
                            "parent_fk_field": fk_field,
                        })
                        rabbit_hole(target_model, target_data, rel["before"][-1])

                elif isinstance(_rel_input, CRUDOneToManyUpdateInput):
                    parent_instance = model.objects.get(pk=int(_input.id))
                    current_content_type = getattr(parent_instance, ct_field)
                    current_object_id = getattr(parent_instance, fk_field)

                    if _rel_input.assign is not UNSET:
                        if _rel_input.assign is None:
                            ct_model_field = model._meta.get_field(ct_field)
                            fk_model_field = model._meta.get_field(fk_field)
                            if ct_model_field.null is False or fk_model_field.null is False:
                                raise SDJExtrasError("Cannot assign null to non nullable field")
                            rel.get("data").update({ct_field: None, fk_field: None})
                        else:
                            target_model = None
                            target_pk = None
                            for field_name in _rel_input.assign.__dataclass_fields__:
                                value = getattr(_rel_input.assign, field_name)
                                if value is not None and value is not UNSET:
                                    target_model = _rel_input.assign._model_mapping[field_name]  # noqa: SLF001
                                    target_pk = int(value)
                                    break

                            if target_model is None:
                                raise SDJExtrasError("oneOf input has no field set")

                            content_type = ContentType.objects.get_for_model(target_model)
                            rel.get("data").update({
                                ct_field: content_type,
                                fk_field: target_pk,
                            })

                    if _rel_input.create is not UNSET and _rel_input.create is not None:
                        target_model = None
                        target_data = None
                        for field_name in _rel_input.create.__dataclass_fields__:
                            value = getattr(_rel_input.create, field_name)
                            if value is not None and value is not UNSET:
                                target_model = _rel_input.create._model_mapping[field_name]  # noqa: SLF001
                                target_data = value
                                break

                        if target_model is None:
                            raise SDJExtrasError("oneOf input has no field set")

                        target_ct = ContentType.objects.get_for_model(target_model)
                        rel["before"].append({
                            "operation": "create",
                            "is_generic_fk_target": True,
                            "target_ct": target_ct,
                            "parent_ct_field": ct_field,
                            "parent_fk_field": fk_field,
                        })
                        rabbit_hole(target_model, target_data, rel["before"][-1])

                    if _rel_input.update is not UNSET and _rel_input.update is not None:
                        if current_content_type is None:
                            raise SDJExtrasError("Cannot update non-existing content_object")

                        target_model = None
                        target_data = None
                        for field_name in _rel_input.update.__dataclass_fields__:
                            value = getattr(_rel_input.update, field_name)
                            if value is not None and value is not UNSET:
                                target_model = _rel_input.update._model_mapping[field_name]  # noqa: SLF001
                                target_data = value
                                break

                        if target_model is None:
                            raise SDJExtrasError("oneOf input has no field set")

                        expected_ct = ContentType.objects.get_for_model(target_model)
                        if current_content_type != expected_ct:
                            raise SDJExtrasError(
                                f"Update target type mismatch: current is {current_content_type.model}, "
                                f"update specifies {expected_ct.model}"
                            )

                        target_data.id = current_object_id  # pyright: ignore[reportOptionalMemberAccess]
                        rel["before"].append({
                            "operation": "update",
                            "pk": current_object_id,
                            "data_id": key,
                        })
                        rabbit_hole(target_model, target_data, rel["before"][-1])

                    if _rel_input.delete is True:
                        if _rel_input.assign is UNSET and _rel_input.create is UNSET:
                            raise SDJExtrasError(
                                "Cannot delete remote object without assigning or"
                                " creating a new one. If the relationship is nullable"
                                " you can assign null to unset the relationship"
                            )
                        if current_content_type is not None and current_object_id is not None:
                            target_model = current_content_type.model_class()
                            if target_model is None:
                                raise SDJExtrasError(
                                    "Cannot resolve model class for current content type"
                                )
                            rel["deletions"].append({
                                "model": target_model,
                                "pks": [current_object_id],
                            })

                else:
                    raise SDJExtrasError(
                        f"GenericForeignKey field '{key}' requires "
                        f"CRUDOneToManyCreateInput or CRUDOneToManyUpdateInput"
                    )

            elif isinstance(val, GenericRelation):
                _rel_input = _input.__dict__.get(key)  # noqa: RUF052
                ct_field_name = val.content_type_field_name
                fk_field_name = val.object_id_field_name
                related_model = val.related_model

                is_one_to_one = False
                for constraint in related_model._meta.unique_together:  # noqa: SLF001
                    if set(constraint) == {ct_field_name, fk_field_name}:
                        is_one_to_one = True
                        break

                if not is_one_to_one:
                    for constraint in related_model._meta.constraints:  # noqa: SLF001
                        if isinstance(constraint, models.UniqueConstraint):  # noqa: SIM102
                            if set(constraint.fields) == {ct_field_name, fk_field_name}:
                                is_one_to_one = True
                                break

                if is_one_to_one:
                    if isinstance(_rel_input, CRUDOneToOneCreateInput):
                        if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                            raise SDJExtrasError("Must create or assign")
                        if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                            raise SDJExtrasError("Cannot create and assign at the same time")

                        if _rel_input.create is not UNSET:
                            rel["after"].append({
                                "operation": "create",
                                "is_generic_relation": True,
                                "fk_field_name": fk_field_name,
                                "data_id": key,
                                "rel_data_id": fk_field_name,
                            })
                            rabbit_hole(related_model, _rel_input.create, rel["after"][-1])

                            content_type = ContentType.objects.get_for_model(model)
                            rel["after"][-1].get("data").update({ct_field_name: content_type})

                        if _rel_input.assign is not UNSET:
                            if _rel_input.assign is None:
                                raise SDJExtrasError("assign cannot be null")
                            rel["generic_assignments"] = rel.get("generic_assignments", [])
                            rel["generic_assignments"].append({
                                "model": related_model,
                                "pk": int(_rel_input.assign),
                                "ct_field_name": ct_field_name,
                                "fk_field_name": fk_field_name,
                            })

                    elif isinstance(_rel_input, CRUDOneToOneUpdateInput):
                        parent_instance = model.objects.get(pk=int(_input.id))
                        parent_ct = ContentType.objects.get_for_model(model)
                        try:
                            existing_instance = getattr(parent_instance, key)
                        except related_model.DoesNotExist:
                            existing_instance = None

                        if _rel_input.create is not UNSET and _rel_input.assign is not UNSET:
                            raise SDJExtrasError("Cannot create and assign at the same time")
                        if _rel_input.update is not UNSET and (
                            _rel_input.assign is not UNSET or _rel_input.create is not UNSET
                        ):
                            raise SDJExtrasError("Updating is only supported without create/assign")

                        if _rel_input.assign is not UNSET:
                            if _rel_input.assign is None:
                                if existing_instance is not None:
                                    rel["generic_removals"] = rel.get("generic_removals", [])
                                    rel["generic_removals"].append({
                                        "model": related_model,
                                        "pks": [existing_instance.pk],
                                        "parent_ct": parent_ct,
                                        "ct_field_name": ct_field_name,
                                        "fk_field_name": fk_field_name,
                                    })
                            else:
                                if existing_instance is not None and _rel_input.delete is not True:
                                    rel["generic_removals"] = rel.get("generic_removals", [])
                                    rel["generic_removals"].append({
                                        "model": related_model,
                                        "pks": [existing_instance.pk],
                                        "parent_ct": parent_ct,
                                        "ct_field_name": ct_field_name,
                                        "fk_field_name": fk_field_name,
                                    })

                                rel["generic_assignments"] = rel.get("generic_assignments", [])
                                rel["generic_assignments"].append({
                                    "model": related_model,
                                    "pk": int(_rel_input.assign),
                                    "parent_ct": parent_ct,
                                    "ct_field_name": ct_field_name,
                                    "fk_field_name": fk_field_name,
                                })

                        if _rel_input.create is not UNSET:
                            if existing_instance is not None and _rel_input.delete is not True:
                                raise SDJExtrasError(
                                    f"There is already a {key} assigned. Maybe specify delete to replace?"
                                )

                            if existing_instance is not None and _rel_input.delete is True:
                                rel["deletions"].append({
                                    "model": related_model,
                                    "pks": [existing_instance.pk],
                                })

                            rel["after"].append({
                                "operation": "create",
                                "is_generic_relation": True,
                                "fk_field_name": fk_field_name,
                                "data_id": key,
                                "rel_data_id": fk_field_name,
                            })
                            rabbit_hole(related_model, _rel_input.create, rel["after"][-1])

                            content_type = ContentType.objects.get_for_model(model)
                            rel["after"][-1].get("data").update({
                                ct_field_name: content_type,
                                fk_field_name: int(_input.id),
                            })

                        if _rel_input.update is not UNSET:
                            if existing_instance is None:
                                raise SDJExtrasError("Cannot update non-existing object")

                            _rel_input.update.id = existing_instance.pk  # pyright: ignore[reportOptionalMemberAccess]
                            rel["after"].append({
                                "operation": "update",
                                "pk": existing_instance.pk,
                                "data_id": key,
                                "rel_data_id": fk_field_name,
                            })
                            rabbit_hole(related_model, _rel_input.update, rel["after"][-1])

                        if _rel_input.delete is True and existing_instance is not None:
                            rel["deletions"].append({
                                "model": related_model,
                                "pks": [existing_instance.pk],
                            })

                    else:
                        raise SDJExtrasError(
                            f"GenericRelation field '{key}' with unique_together requires "
                            f"CRUDOneToOneCreateInput or CRUDOneToOneUpdateInput"
                        )

                # ManyToOne semantics (no constraint)
                # CREATE
                elif isinstance(_rel_input, CRUDManyToOneCreateInput):
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign or both")

                    parent_ct = ContentType.objects.get_for_model(model)

                    if _rel_input.create is not UNSET:
                        if _rel_input.create is None:
                            raise SDJExtrasError("create cannot be null")
                        for item in _rel_input.create:
                            rel["after"].append({
                                "operation": "create",
                                "is_generic_relation": True,
                                "fk_field_name": fk_field_name,
                                "data_id": key,
                                "rel_data_id": fk_field_name,
                            })
                            rabbit_hole(related_model, item, rel["after"][-1])

                            rel["after"][-1].get("data").update({ct_field_name: parent_ct})

                    if _rel_input.assign is not UNSET:
                        if _rel_input.assign is None:
                            raise SDJExtrasError("assign cannot be null")
                        rel["generic_assignments"] = rel.get("generic_assignments", [])
                        rel["generic_assignments"].append({
                            "model": related_model,
                            "pks": [int(pk) for pk in _rel_input.assign],
                            "parent_ct": parent_ct,
                            "ct_field_name": ct_field_name,
                            "fk_field_name": fk_field_name,
                        })

                # UPDATE
                elif isinstance(_rel_input, CRUDManyToOneUpdateInput):
                    parent_instance = model.objects.get(pk=int(_input.id))
                    parent_ct = ContentType.objects.get_for_model(model)
                    manager = getattr(parent_instance, key)

                    if _rel_input.create is not UNSET:
                        if _rel_input.create is None:
                            raise SDJExtrasError("create cannot be null")
                        for item in _rel_input.create:
                            rel["after"].append({
                                "operation": "create",
                                "is_generic_relation": True,
                                "fk_field_name": fk_field_name,
                                "data_id": key,
                                "rel_data_id": fk_field_name,
                            })
                            rabbit_hole(related_model, item, rel["after"][-1])

                            rel["after"][-1].get("data").update({
                                ct_field_name: parent_ct,
                                fk_field_name: int(_input.id),
                            })

                    if _rel_input.assign is not UNSET:
                        if _rel_input.assign is None:
                            raise SDJExtrasError("assign cannot be null")
                        rel["generic_assignments"] = rel.get("generic_assignments", [])
                        rel["generic_assignments"].append({
                            "model": related_model,
                            "pks": [int(pk) for pk in _rel_input.assign],
                            "parent_ct": parent_ct,
                            "ct_field_name": ct_field_name,
                            "fk_field_name": fk_field_name,
                        })

                    if _rel_input.update is not UNSET:
                        if _rel_input.update is None:
                            raise SDJExtrasError("update cannot be null")
                        for item in _rel_input.update:
                            rel["after"].append({
                                "operation": "update",
                                "pk": item.id,
                                "manager": manager,
                                "data_id": key,
                                "rel_data_id": fk_field_name,
                            })
                            rabbit_hole(related_model, item, rel["after"][-1])

                    if _rel_input.remove is not UNSET:
                        if _rel_input.remove is None:
                            raise SDJExtrasError("remove cannot be null")
                        del_pks = [
                            int(item.id) for item in _rel_input.remove if item.delete is True
                        ]
                        rem_pks = [
                            int(item.id) for item in _rel_input.remove if item.delete is not True
                        ]

                        if len(del_pks) > 0:
                            rel["deletions"].append({
                                "model": related_model,
                                "pks": del_pks,
                            })

                        if len(rem_pks) > 0:
                            rel["generic_removals"] = rel.get("generic_removals", [])
                            rel["generic_removals"].append({
                                "model": related_model,
                                "pks": rem_pks,
                                "parent_ct": parent_ct,
                                "ct_field_name": ct_field_name,
                                "fk_field_name": fk_field_name,
                            })

                else:
                    raise SDJExtrasError(
                        f"GenericRelation field '{key}' requires "
                        f"CRUDManyToOneCreateInput or CRUDManyToOneUpdateInput"
                    )

            elif isinstance(val, (OneToOneField, OneToOneRel)):
                _rel_input = _input.__dict__.get(key)  # noqa: RUF052
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
                                    pk=int(_rel_input.assign),  # pyright: ignore[reportArgumentType]
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
                            "Updating an object is only supported without create/assign.",
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
                            raise SDJExtrasError(f"Invalid field type for {key}")
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
                        _rel_input.update.id = existing_instance.pk  # pyright: ignore[reportOptionalMemberAccess]
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
                                val.remote_field.on_delete is models.CASCADE  # pyright: ignore[reportAttributeAccessIssue]
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

            elif isinstance(val, ForeignKey):
                _rel_input = _input.__dict__.get(key)  # noqa: RUF052
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
                            "Updating an object is only supported without create/assign.",
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
                                f"Cannot update non existing object for key {key}",
                            )
                        _rel_input.update.id = rel_obj.pk  # pyright: ignore[reportOptionalMemberAccess]
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
                _rel_input = _input.__dict__.get(key)  # noqa: RUF052
                if isinstance(_rel_input, CRUDManyToOneCreateInput):
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign or both")
                    if _rel_input.assign is not UNSET:
                        rel_objs = val.related_model.objects.filter(
                            pk__in=[int(pk) for pk in _rel_input.assign],  # pyright: ignore[reportOptionalIterable]
                        )
                        if rel_objs.count() != len(_rel_input.assign):  # pyright: ignore[reportArgumentType]
                            raise SDJExtrasError(
                                f"Not all assigned objects found for {val.related_model.__name__}",
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
                            pk__in=[int(pk) for pk in _rel_input.assign],  # pyright: ignore[reportOptionalIterable]
                        )
                        if rel_objs.count() != len(_rel_input.assign):  # pyright: ignore[reportArgumentType]
                            raise SDJExtrasError(
                                f"Not all assigned objects found for {val.related_model.__name__}",
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
                                val.model.objects.get(pk=int(_input.id)),  # pyright: ignore[reportAttributeAccessIssue]
                                val.get_accessor_name(),  # pyright: ignore[reportArgumentType]
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
                            val.model.objects.get(pk=int(_input.id)),  # pyright: ignore[reportAttributeAccessIssue]
                            val.get_accessor_name(),  # pyright: ignore[reportArgumentType]
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
                _rel_input = _input.__dict__.get(key)  # noqa: RUF052
                if isinstance(_rel_input, CRUDManyToManyCreateInput):
                    if isinstance(val, ManyToManyField):
                        rel_name = val.name
                    elif isinstance(val, ManyToManyRel):
                        rel_name = val.get_accessor_name()
                    else:
                        raise SDJExtrasError(
                            f"Unable to determine manager for {val.__class__.__name__}",
                        )
                    if _rel_input.create is UNSET and _rel_input.assign is UNSET:
                        raise SDJExtrasError("Must create or assign or both")
                    if _rel_input.create is not UNSET:
                        for item in _rel_input.create:  # pyright: ignore[reportOptionalIterable]
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
                        for item in _rel_input.assign:  # pyright: ignore[reportOptionalIterable]
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
                            f"Unable to determine manager for {val.__class__.__name__}",
                        )
                    p_obj = val.model.objects.get(pk=int(_input.id))  # pyright: ignore[reportAttributeAccessIssue]
                    manager = getattr(p_obj, rel_name)  # pyright: ignore[reportArgumentType]
                    if _rel_input.create is not UNSET:
                        for item in _rel_input.create:  # pyright: ignore[reportOptionalIterable]
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
                        for item in _rel_input.assign:  # pyright: ignore[reportOptionalIterable]
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
                        for item in _rel_input.update:  # pyright: ignore[reportOptionalIterable]
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
                        for item in _rel_input.remove:  # pyright: ignore[reportOptionalIterable]
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
    if isinstance(_input, list):
        for item in _input:
            perform_validation(item, info)

    if (
        hasattr(_input, "__strawberry_definition__")
        and _input.__strawberry_definition__.is_input is True  # pyright: ignore[reportAttributeAccessIssue]
    ):
        for v in _input.__dict__.values():
            if isinstance(v, list):
                for item in v:
                    perform_validation(item, info)

            if (
                hasattr(v, "__strawberry_definition__")
                and v.__strawberry_definition__.is_input is True  # pyright: ignore[reportAttributeAccessIssue]
            ):
                perform_validation(v, info)

        if hasattr(_input, "validate") and callable(_input.validate):  # pyright: ignore[reportAttributeAccessIssue]
            _input.validate(info)  # pyright: ignore[reportAttributeAccessIssue]

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
    if isinstance(_input, list):
        for item in _input:
            check_permissions(item, info)

    if (
        hasattr(_input, "__strawberry_definition__")
        and _input.__strawberry_definition__.is_input is True  # pyright: ignore[reportAttributeAccessIssue]
    ):
        for v in _input.__dict__.values():
            if isinstance(v, list):
                for item in v:
                    check_permissions(item, info)

            if (
                hasattr(v, "__strawberry_definition__")
                and v.__strawberry_definition__.is_input is True  # pyright: ignore[reportAttributeAccessIssue]
            ):
                check_permissions(v, info)

        if hasattr(_input, "check_permissions") and callable(_input.check_permissions):  # pyright: ignore[reportAttributeAccessIssue]
            _input.check_permissions(info)  # pyright: ignore[reportAttributeAccessIssue]

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
