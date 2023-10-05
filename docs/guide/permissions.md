## Permissions
Similarly to validations, permission checking is run on input instantiation. Since strawberry does not currently provide a way to pass `permission_classes` to input fields
this package allows you to write your permission checking functions as part of the input class. 

```{.python title="inputs.py"}
@strawberry_django.input(get_user_model())
class UserInput:
    firstname: auto
    lastname: auto
    
    def check_permissions(self, info):
        if not info.context.user.is_staff:
            raise PermissionDenied(
                "You need to be staff to do this"
            )
         
    # Or for individual fields    
    def check_permissions_lastname(self, info, value):
        if value == info.context.user.lastname:
            raise PermissionDenied(
                "You cannot create a user with the same lastname as you"
            )
```

```{.python title="schema.py"}
from strawberry_django_extras import with_permissions
from strawberry_django import mutations

@strawberry.type
class Mutation:
    create_user: UserType = mutations.create(
        UserInput,
        extensions=[with_permissions()]
    )
``` 
!!! note
    As documented by Strawberry extension order does matter so make sure you are passing the `with_permissions()` and `with_validation()` extensions in an order that
    makes sense for your project. 

<br/>