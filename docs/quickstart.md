# Quick Start

## Installation

```bash
pip install strawberry-django-extras
```

<br/>

## JWT Authentication

The JWT part of this package is heavily based on
the [django-graphql-jwt](https://github.com/flavors/django-graphql-jwt){:target="_blank"}
package. Noting that, not all features supported by that package are supported here. For details on what is supported
please refer to the the [JWT part of these docs](./guide/jwt.md).

<br />

#### Add the JWT Authentication Backend to your settings

```{.python title="settings.py"}
  AUTHENTICATION_BACKENDS = [
    'strawberry_django_extras.jwt.backend.JWTBackend',
    'django.contrib.auth.backends.ModelBackend',
]
```

<br />

#### Add the JWT Middleware to your settings

```{.python title="settings.py"}
  MIDDLEWARE = [
    ...
    'strawberry_django_extras.jwt.middleware.JWTMiddleware',
]
```

!!! note

    This implementation of the middleware is different from other implementations in that it is designed to handle token based authentication for all
    request containing the `Authorization` header regardless of wether the request is to be consumed by your GraphQL view. This aims to provide a unified
    way of authenticating via JWT tokens issued by this package accross your entire application. 

    If the request contains the `Authorization` header and the token is valid, the user will be authenticated and the `request.user` will be set to the user 
    associated with the token. If the token is expired a `401` response will be returned along with `Token Expired`. If an invalid token is provided a `401`
    response will be returned along with `Invalid Token`.

    If the user is already authenticated by some previous middleware in your middleware stack it will be respected and the token will not be checked at all.
    The order of the middleware in your middleware stack is important and you can set it depending on your needs. 

<br />

#### Expose the mutations in your GraphQL schema
```{.python title="schema.py"}
from strawberry_django_extras import JWTMutations

@strawberry.type
class Mutation:
    request_token = JWTMutations.issue
    revoke_token = JWTMutations.revoke
    verify_token = JWTMutations.verify

```
<br/>

#### Override any settings you might need in your project settings.
```{.python title="settings.py"}
GRAPHQL_JWT = {
    'JWT_ALGORITHM': 'EdDSA',
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LONG_RUNNING_REFRESH_TOKEN': True,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(minutes=5)
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_AUTHENTICATE_INTROSPECTION': True,
    'JWT_REFRESH_TOKEN_N_BYTES': 64,
    'JWT_PRIVATE_KEY': base64.b64decode('YOUR_PRIVATE_KEY'),
    'JWT_PUBLIC_KEY': base64.b64decode('YOUR_PUBLIC_KEY')
}
```
If you set `JWT_LONG_RUNNING_REFRESH_TOKEN` to `True` you will need to add the following to your settings file:
```{.python title="settings.py"}
INSTALLED_APPS = [
    ...
    'strawberry_django_extras.jwt.refresh_token.apps.RefreshTokenConfig',
]
```
and run `python manage.py migrate` to create the refresh token model.

If you set `JWT_AUTHENTICATE_INTROSPECTION` to `True` you will need to add an extension to the root of your schema:
```{.python title="schema.py"}
from strawberry_django_extras.jwt.extensions import DisableAnonymousIntrospection

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        DisableAnonymousIntrospection,
        ...
    ]
)
```

<br/>

## Mutation Hooks
Mutation  hooks are provided via a `field_extension` and can be applied to any strawberry mutation. 
```{.python title="hooks.py"}
def update_user_pre(info: Info, mutation_input: UserUpdateInput):
    mutation_input.lastname = mutation_input.lastname.lower()
    
async def update_user_post(
    info: Info, 
    mutation_input: UserUpdateInput,
    result: Any
):
    await log(f'User {result.id} updated')
```

and then applied to your mutation:
```{.python title="schema.py"}
from strawberry_django_extras import mutation_hooks
from strawberry_django import mutations
from .hooks import update_user_pre, update_user_post

@strawberry.type
class Mutation:
    update_user: UserType = mutations.update(
        UserInputPartial,
        extensions=[
            mutation_hooks(
                pre=update_user_pre,
                post_async=update_user_post
            )
        ]
    )
```
!!! note
    You might have noticed that we are passing both a sync and an async function at the same time. This is possible because if the context is async
    the sync function will be wrapped with sync_to_async and awaited. If the context is sync passing post_async and pre_async will be ignored.
    In either case the async functions are awaited.  

<br/>

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


<br/>

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

## Nested Mutations
This package provides support for deeply nested mutations through a field extension and some wrapper input classes. 

It makes sense for the inputs to be different when updating an object vs creating one. So we provide different input wrappers for each type of operation. 
It also makes sense that the api provided would be different depending on the type of relationship between the related models. Brief explanations of each 
input wrapper is provided below. For details refer to relevant guide on [nested mutations](./guide/mutations.md).

### Wrappers for nested objects on creation

#### One to One
`CRUDOneToOneCreateInput` can be used when you want to create or assign a related object, alongside the creation of your root object. The resulting schema will provide two actions
for your mutation `create` and `assign` which are mutually exclusive. `create` is of type `UserCreateInput` which you will need to provide and `assign` is of type `ID`. A brief
example follows.
```{.python title="models.py"}
    class User(AbstractBaseUser, PermissionsMixin):
        firstname = models.CharField(max_length=30, blank=True)
        lastname = models.CharField(max_length=30, blank=True)
        email = models.EmailField(max_length=254, unique=True)   
        USERNAME_FIELD = 'email'
        EMAIL_FIELD = 'email'
    
    class Goat(models.Model):
        name = models.CharField(max_length=255, default=None, null=True, blank=True)
        user = models.OneToOneField(User, related_name="goat", on_delete=models.CASCADE, null=True, default=None)
```
```{.python title="inputs.py"}
    from strawberry_django_extras import CRUDOneToOneCreateInput
    
    @strawberry_django.input(get_user_model())
    class UserInput:
        firstname: auto
        lastname: auto
        email: auto
        password: auto
        goat: Optional[CRUDOneToOneCreateInput[GoatInput]] = UNSET
    
    @strawberry_django.input(Goat)
    class GoatInput:
        name: auto
        user: Optional[CRUDOneToOneCreateInput['UserInput']] = UNSET
```
```{.python title="schema.py"}
    from strawberry_django_extras import with_cud_relationships
    from strawberry_django import mutations
    
    @strawberry.type
    class Mutation:
        create_user: UserType = mutations.create(
            UserInput,
            extensions=[with_cud_relationships()]
        )
        
        create_goat: GoatType = mutations.create(
            GoatInput,
            extensions=[with_cud_relationships()]
        )
```

Now we can create or assign nested objects on either side of the relationship.
```graphql 
mutation {
  createGoat(data: {
    name: "Marina"
    user: {
      create: {
        firstname: "Lakis"
        lastname: "Lalakis"
        email: "lalakis@gmail.com"
        password: "abc"
      }
    }
  }) {
    id
    name
    user {
      id
      lastname
      firstname
      email
    }
  }
}
```

Or we could create the goat through the creation of the user.
```graphql 
mutation {
  createUser(data: { 
    firstname: "Costas"
    lastname: "Papadopoulos"
    email: "papado@cia.gov", 
    password: "abc"
    goat: {
      create: {
        name: "Mpempeka"
      }
    }
  }) {
    id
    lastname
    firstname
    email
    goat {
      id
      name
    }
  }
}
```

We could ofcourse use the `assign` action to assign an existing goat to a user or vice versa by providing the ID.

!!! note
    There is no limit to how deeply nested the mutations can be. If the goat had a second relationship to another model say `Collar` and `Collar` had a relationship 
    back to the `User` model through a `designer` field we could create or assign the nested objects in one go.

#### One to Many
`CRUDOneToManyCreateInput`. Similarly to the one to one wrapper it provides two actions `create` and `assign` which are mutually exclusive. The only difference is 
that the relationship is through a `ForeignKey` meaning the other side of the relationship would be Many to One requiring a different wrapper. Here's a brief example:

```graphql
mutation {
  createGoat(data: {
    name: "Marina"
    child: {
      create: {
        name: "Mpempeka"
        child: {
          create: {
            name: "Mpempis"
            child: {
              assign: "72"                
            }
          }
        }
      }
    }
  }) {
    id
    name
    child {
      ...
    }
  }
}
```
In the above example we can populate the entire genealogy of the goat with `pk` `72` in one go.

#### Many to One
`CRUDManyToOneCreateInput`. This wrapper is used when the relationship is Many to One. It provides two actions `create` and `assign` which are __NOT mutually exclusive__.
The inputs are of course lists and of type `SomeModelInput` and `ID` respectively. Here's a brief example:

```graphql
mutation {
  createUser(data: { 
    firstname: "Costas"
    lastname: "Papadopoulos"
    email: "papado@cia.gov", 
    password: "abc"
    goats: {
      create: [
        {name: "Myrto"},
        {name: "Aliki"}
      ]
      assign: [
        "29",
        "30"
      ]
    }
  }
  ) {
    id
    lastname
    firstname
    email
    goats {
      id
      name
    }
  }
}
```

#### Many to Many
`CRUDManyToManyCreateInput` is provided for Many-to-Many relationships. It provides two actions `create` and `assign` which are __NOT mutually exclusive__.
The inputs are ofcourse lists again but there's one important difference. They are internally wrapped again to provide a mechanism for the user to provide
`through_defaults` for the relationship either on assignment or creation. The type for through_defaults is JSON and the values should follow snake case.  
For examples please refer to the relevant guide on [nested mutations](./guide/mutations.md).

!!! note
    Please note that the inputs for the nested objects need not be the same as the inputs for the creation of the objects. In fact you have the flexibility
    to define different inputs for the nested objects limiting which fields are exposed through each nested mutation. 

### Wrappers for nested objects on update
These wrappers expect two inputs to be provided instead of the one that was necessary for creation. The first is for creation of new related objects when updating the current 
object and the second is for updates to the data of already related objects.