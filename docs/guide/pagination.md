# Pagination

This field extension allows you to use the default offset limit pagination provided by 
[strawberry-graphql-django](https://github.com/strawberry-graphql/strawberry-graphql-django){target="_blank"} but wraps the results with total count.

## Usage

```python
import strawberry
import strawberry_django
from strawberry_django_extras import with_total_count

@strawberry.type
class Query:
    Users: list[UserType] = strawberry_django.field( 
        extensions=[with_total_count()]
    )
```

Now you can query your list with pagination and total count:

```graphql
{
  Users(pagination: {offset:0 , limit:1} , order: {lastname: DESC} ) {
    results {
      id
      lastname
      firstname
      email  
    }
    totalCount
  }
}
```