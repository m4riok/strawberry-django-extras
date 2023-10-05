## Nested Mutations
This package provides support for deeply nested mutations through a field extension and some wrapper input classes. 

It makes sense for the inputs to be different when updating an object vs creating one. So we provide different input wrappers for each type of operation. 
It also makes sense that the api provided would be different depending on the type of relationship between the related models. 

### Wrappers for nested objects for create mutations

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
        email: "lalakis@domaim.tld"
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
    email: "papado@domain.tld", 
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
    email: "papado@domain.tld", 
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

!!! note
    Please note that the inputs for the nested objects need not be the same as the inputs for the creation of the objects. In fact you have the flexibility
    to define different inputs for the nested objects limiting which fields are exposed through each nested mutation. 

### Wrappers for nested objects for update mutations
These wrappers expect two inputs to be provided instead of the one that was necessary for creation. The first is for creation of new related objects when updating the current 
object and the second is for updates to the data of already related objects.

#### One to One
`CRUDOneToOneUpdateInput` can be used when alongside an update mutation you want to update related objects. The resulting schema will provide three possible actions for your 
mutation and a boolean flag. 

- `create` of type `UserInput` used to create a new related object.
- `assign` of type `ID` used to assign an existing objects as related.
  > Note that you can use `null` to remove the relationship if the field is nullable.
- `update` of type `UserPartial` used to update the fields of an existing related object.
- `delete` of type `bool` indicating whether the related object should be deleted.
  > Note that this flag can be used together with assign or create to delete the previously related object.

The respective update input of the example used for the One to One creation mutation above would read:
```python
@strawberry_django.partial(Goat)
class GoatPartial:
    id: ID
    name: auto
    user: Optional[CRUDOneToOneUpdateInput['UserInput','UserPartial']] = UNSET

@strawberry_django.partial(get_user_model())
class UserPartial:
    id: ID
    firstname: auto
    lastname: auto
    ...
    goat: Optional[CRUDOneToOneUpdateInput[GoatInput, GoatPartial]] = UNSET
```

!!! note
    Currently when using `@strawberry_django.partial` all fields are marked as optional when auto is used. However, the ID is required for performing nested updates. For
    consistency and to avoid any errors you should always use `id: ID` when defining partials for update mutations when it is the root object. The `id` can be omitted
    when the partial is used as a nested input and if defined it won't be used in any way to update the related object.

#### One to Many
`CRUDOneToManyUpdateInput` can be used when alongside an update mutation you want to update related objects. The resulting schema will provide three possible actions for
your mutation and a boolean flag. These are the same as the ones provided by the One to One wrapper, and they function in exactly the same fashion. 

#### Many to One
`CRUDManyToOneUpdateInput` can be used when alongside an update mutation you want to update related objects. The resulting schema will provide __four__ possible actions 
for your mutation. These are as follows:

- `create` of type `List[UserInput]` used to create new related objects.
- `assign` of type `List[ID]` used to assign relations with existing objects.
- `update` of type `List[UserPartial]` used to update the fields of existing related objects.
- `remove` of type `List[CRUDRemoveInput]` which wraps an `ID` and a `bool` flag indicating whether the removed object should be deleted. 

!!! note
    Please note that the `UserPartial` used in the example above unlike the case with One to Many and One to One has a requirement for the `id` field. Please take care
    to ensure the `id` is declared as mandatory when declaring your input class.


#### Many to Many
`CRUDManyToManyUpdateInput` can be used when alongside an update mutation you want to update related objects. The resulting schema will provide __four__ possible actions
for your mutation. These are as follows:

- `create` of type `List[CRUDManyToManyItem]` which wraps two inputs.
    - `objectData` of type `UserInput` used for the fields of the related object.
    - `throughDefaults` of type `JSON` used for any data stored in the `through` model if one exists.
- `assign` of type `List[CRUDManyToManyID]` which wraps two inputs.
    - `id` of type `ID` used to assign relations with existing objects.
    - `throughDefaults` of type `JSON` used for any data stored in the `through` model if one exists.
- `update` of type `List[CRUDManyToManyItemUpdate]` which wraps two inputs.
    - `objectData` of type `UserPartial` used to update the fields of the related object.
    - `throughDefaults` of type `JSON` used to update the fields of the `through` model if one exists.
- `remove` of type `List[CRUDRemoveInput]` which wraps an `ID` and a `bool` flag indicating whether the removed object should be deleted.

!!! note
    Please note that again the `UserPartial` input must declare an `id` field of type `ID` and __not__ `auto`. 

