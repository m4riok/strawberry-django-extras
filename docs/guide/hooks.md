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
