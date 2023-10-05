## Input Validations
Much inspired by the way [graphene-django-cud](https://github.com/tOgg1/graphene-django-cud){:target="_blank"} handles validation, this package provides
a similar way to validate your input when the respective input classes are instantiated. 

```{.python title="inputs.py"}
@strawberry_django.input(get_user_model())
class UserInput:
    firstname: auto
    lastname: auto
    
    def validate(self, info):
        if self.firstname == self.lastname:
            raise ValidationError(
                "Firstname and lastname cannot be the same"
            )
         
    # Or for individual fields    
    def validate_lastname(self, info, value):
        if value == self.firstname:
            raise ValidationError(
                "Firstname and lastname cannot be the same"
            )
```

When updating an existing object the `pk` will be available through `self.id` so you can validate values in comparison to existing ones. Also info is provided in case
validations need to be run against the user making the request. 

Finally add this to each mutation that needs to run validations:
```{.python title="schema.py"}
from strawberry_django_extras import with_validation
from strawberry_django import mutations

@strawberry.type
class Mutation:
    create_user: UserType = mutations.create(
        UserInput,
        extensions=[with_validation()]
    )
``` 
