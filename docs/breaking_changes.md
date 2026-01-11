# Breaking Changes

## One-to-Many Assign Type Parameter (v0.2.6)

### Summary

`CRUDOneToManyCreateInput` and `CRUDOneToManyUpdateInput` now require an explicit **assign** type parameter to support GenericForeignKey relationships. This is a **breaking change** for type annotations.

### Why This Change Was Made

GenericForeignKey assignments use a one-of input type rather than a simple `ID`. To support both FK and GFK in a typed way, the assign input type is now a generic parameter.

### What You Need to Do

Update any usages of `CRUDOneToManyCreateInput` and `CRUDOneToManyUpdateInput` to include the assign type.

### Migration Examples

#### Create Input
```python
# ❌ OLD
child: Optional[CRUDOneToManyCreateInput[ChildInput]] = UNSET

# ✅ NEW (ForeignKey)
child: Optional[CRUDOneToManyCreateInput[ChildInput, ID]] = UNSET

# ✅ NEW (GenericForeignKey)
child: Optional[CRUDOneToManyCreateInput[ChildInput, ChildAssignInput]] = UNSET
```

#### Update Input
```python
# ❌ OLD
child: Optional[CRUDOneToManyUpdateInput[ChildInput, ChildPartial]] = UNSET

# ✅ NEW (ForeignKey)
child: Optional[CRUDOneToManyUpdateInput[ChildInput, ID, ChildPartial]] = UNSET

# ✅ NEW (GenericForeignKey)
child: Optional[CRUDOneToManyUpdateInput[ChildInput, ChildAssignInput, ChildPartial]] = UNSET
```

## Removal of Convenience Imports (v0.2.0)

### Summary

All convenience imports have been removed from the main package `__init__.py` to prevent eager loading and resolve async context detection issues. This is a **breaking change** that requires updating all import statements in your code.

### Why This Change Was Made

Convenience imports in `__init__.py` caused modules to be eagerly loaded during Django startup, which led to:
- Field extensions being built in sync context during import time
- Schema evaluation happening too early (before async context was available)
- Crashes when mixing sync/async execution chains during testing

By removing these imports, modules are only loaded when explicitly imported, ensuring proper async context detection.

### What You Need to Do

Update all imports to use direct module paths instead of importing from the main package.

### Migration Examples

#### Field Extensions
```python
# ❌ OLD (no longer works)
from strawberry_django_extras import (
    mutation_hooks,
    with_validation,
    with_permissions,
    with_cud_relationships,
    with_total_count
)

# ✅ NEW (required)
from strawberry_django_extras.field_extensions import (
    mutation_hooks,
    with_validation,
    with_permissions, 
    with_cud_relationships,
    with_total_count
)
```

#### JWT Authentication
```python
# ❌ OLD (no longer works)
from strawberry_django_extras import JWTMutations

# ✅ NEW (required)
from strawberry_django_extras.jwt.mutations import JWTMutations
```

#### Input Types
```python
# ❌ OLD (no longer works)
from strawberry_django_extras import (
    CRUDInput,
    CRUDOneToOneCreateInput,
    CRUDManyToManyUpdateInput
)

# ✅ NEW (required)
from strawberry_django_extras.inputs import (
    CRUDInput,
    CRUDOneToOneCreateInput,
    CRUDManyToManyUpdateInput
)
```

#### Decorators
```python
# ❌ OLD (no longer works)
from strawberry_django_extras import sync_or_async

# ✅ NEW (required)
from strawberry_django_extras.decorators import sync_or_async
```

### Module Structure

The new import structure follows this pattern:

```
strawberry_django_extras/
├── decorators.py          # sync_or_async
├── field_extensions.py    # All field extensions and factory functions
├── inputs.py             # CRUD input types
├── lazy.py               # Context-aware lazy view/consumer classes
└── jwt/
    └── mutations.py      # JWTMutations
```

### Need Help?

- Check the [documentation](/docs/guide/jwt/) for detailed examples
- All existing functionality remains the same - only import paths have changed
