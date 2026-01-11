# Generic Relationships

This page documents how to use nested mutations with Django `GenericForeignKey` (forward) and
`GenericRelation` (reverse). It includes sample Django models, the required Strawberry inputs
and oneOf definitions, plus example mutations and queries.

## Sample models

The following simplified models are enough to demonstrate both directions:

```python
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    isbn = models.CharField(max_length=13, unique=True)

    # Reverse GenericRelation (Many-to-One)
    tags = GenericRelation("Tag", related_query_name="books")


class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    published_date = models.DateField()

    # Reverse GenericRelation (Many-to-One)
    tags = GenericRelation("Tag", related_query_name="articles")


class Video(models.Model):
    title = models.CharField(max_length=200)
    url = models.URLField()
    duration = models.IntegerField()

    # Reverse GenericRelation (Many-to-One)
    tags = GenericRelation("Tag", related_query_name="videos")


class Tag(models.Model):
    name = models.CharField(max_length=50)

    # GenericForeignKey (forward) - can point to Book, Article, or Video
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")


class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # Reverse GenericRelation (One-to-One)
    featured_review = GenericRelation(
        "Review",
        content_type_field="reviewed_content_type",
        object_id_field="reviewed_object_id",
        related_query_name="featured_products",
    )


class Review(models.Model):
    rating = models.IntegerField()
    comment = models.TextField()
    reviewer_name = models.CharField(max_length=100)

    reviewed_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    reviewed_object_id = models.PositiveIntegerField(null=True, blank=True)
    reviewed_object = GenericForeignKey("reviewed_content_type", "reviewed_object_id")

    class Meta:
        # Enforce one-to-one for Product.featured_review
        unique_together = [("reviewed_content_type", "reviewed_object_id")]
```

## GenericForeignKey (forward)

For a `GenericForeignKey`, nested create/assign/update uses **oneOf inputs** so you can select the
target model. The assign type is now a generic parameter (`T_ASSIGN`) so that polymorphic assignment
is fully typed. Conceptually, the GFK is just `(content_type, object_id)` and the oneOf inputs let
you choose which model that pair should point to.

Because GraphQL does not have true “input unions”, Strawberry’s `one_of=True` inputs are the
recommended way to express “exactly one of these models”. At runtime we read the single provided
field and map it to a Django model class using `_model_mapping`.

### oneOf inputs

Create three `@strawberry.input(one_of=True)` classes that map field names to models via
`_model_mapping`. Only **one** field should be set at a time. The keys you choose (`book`, `article`,
`video`) become the **discriminator** that tells Strawberry which model to use.

Important details:
- The oneOf keys must match the keys in `_model_mapping`.
- Only one key can be set; providing multiple values raises an error.
- For `assign`, the value is an `ID`; for `create`/`update` the value is the nested input.

```python
@strawberry.input(one_of=True)
class ContentObjectCreate:
    book: BookInput | None = UNSET
    article: ArticleInput | None = UNSET
    video: VideoInput | None = UNSET

    _model_mapping: ClassVar = {
        "book": Book,
        "article": Article,
        "video": Video,
    }


@strawberry.input(one_of=True)
class ContentObjectAssign:
    book: ID | None = UNSET
    article: ID | None = UNSET
    video: ID | None = UNSET

    _model_mapping: ClassVar = {
        "book": Book,
        "article": Article,
        "video": Video,
    }


@strawberry.input(one_of=True)
class ContentObjectUpdate:
    book: BookPartial | None = UNSET
    article: ArticlePartial | None = UNSET
    video: VideoPartial | None = UNSET

    _model_mapping: ClassVar = {
        "book": Book,
        "article": Article,
        "video": Video,
    }
```

### Tag input (GenericForeignKey forward)

Now use those oneOf inputs as the create/assign/update types for the GFK field:

```python
@strawberry_django.input(Tag)
class TagInput:
    name: auto
    content_object: (
        CRUDOneToManyCreateInput[
            ContentObjectCreate,  # create oneOf
            ContentObjectAssign,  # assign oneOf
        ]
        | None
    ) = UNSET


@strawberry_django.partial(Tag)
class TagPartial:
    id: ID
    name: auto
    content_object: (
        CRUDOneToManyUpdateInput[
            ContentObjectCreate,  # create oneOf
            ContentObjectAssign,  # assign oneOf
            ContentObjectUpdate,  # update oneOf
        ]
        | None
    ) = UNSET
```

!!! note
    Strawberry converts `content_object` to `contentObject` in the GraphQL schema (camelCase).

### Example mutations

Create a tag and create an Article as the target:

```graphql
mutation {
  createTag(data: {
    name: "graphql"
    contentObject: {
      article: {
        title: "Polymorphic tags"
        content: "..."
        publishedDate: "2025-01-01"
      }
    }
  }) {
    id
    name
  }
}
```

Assign the tag to an existing Video:

```graphql
mutation {
  updateTag(data: {
    id: "1"
    contentObject: {
      video: "12"
    }
  }) {
    id
  }
}
```

Unlink the GenericForeignKey (nullable fields required). This sets both `content_type` and
`object_id` to NULL:

```graphql
mutation {
  updateTag(data: {
    id: "1"
    contentObject: {
      assign: null
    }
  }) {
    id
  }
}
```

Notes on update behavior:
- `assign: null` unlinks the GFK (requires nullable fields).
- `delete: true` is only valid when you are **also** creating or assigning a new target; it deletes
  the previous target during replacement.
- To “just unlink”, use `assign: null` without `delete: true`.

## GenericRelation (reverse)

### Many-to-One GenericRelation

`Book.tags`, `Article.tags`, and `Video.tags` are GenericRelations to `Tag` (no unique constraint),
so they use the **Many-to-One** wrappers. Think of this as “a parent has many tags”, where each tag
stores a GFK back to its parent.

In this case you manage a collection:
- `create` creates new tags and links them to the parent.
- `assign` links existing tags by ID.
- `remove` unlinks tags, and `delete: true` deletes the tag rows.

```python
@strawberry_django.input(Article)
class ArticleInput:
    title: auto
    content: auto
    published_date: auto
    tags: CRUDManyToOneCreateInput["TagInput"] | None = UNSET


@strawberry_django.partial(Article)
class ArticlePartial:
    id: ID
    title: auto
    content: auto
    published_date: auto
    tags: CRUDManyToOneUpdateInput["TagInput", "TagPartial"] | None = UNSET
```

Example: assign and remove tags (optionally deleting them). `remove` unlinks and `delete: true`
also deletes the tag record:

```graphql
mutation {
  updateArticle(data: {
    id: "1"
    tags: {
      assign: ["10", "11"]
      remove: [
        { id: "12", delete: false }
        { id: "13", delete: true }
      ]
    }
  }) {
    id
  }
}
```

### One-to-One GenericRelation

`Product.featured_review` is a GenericRelation constrained by a unique_together on Review, so it
uses **One-to-One** wrappers. The unique constraint ensures only one review can point to a given
product.

Replace semantics are FK-like:
- `create`/`assign` automatically unlinks the old review first (avoid unique constraint collisions).
- `delete: true` deletes the old review when replacing.
- `assign: null` unlinks (leaves the old review as an orphan).

```python
@strawberry_django.input(Product)
class ProductInput:
    name: auto
    price: auto
    featured_review: CRUDOneToOneCreateInput["ReviewInput"] | None = UNSET


@strawberry_django.partial(Product)
class ProductPartial:
    id: ID
    name: auto
    price: auto
    featured_review: CRUDOneToOneUpdateInput["ReviewInput", "ReviewPartial"] | None = UNSET
```

Example: replace the featured review, deleting the old one:

```graphql
mutation {
  updateProduct(data: {
    id: "1"
    featuredReview: {
      create: {
        rating: 5
        comment: "Actually great!"
        reviewerName: "Bob"
      }
      delete: true
    }
  }) {
    id
    featuredReview { id rating comment reviewerName }
  }
}
```

## Querying polymorphic targets

When querying a `GenericForeignKey`, expose a **union** in your GraphQL type and return the
underlying `content_object`. You must define the union type in Python and then query it using
inline fragments.

### GraphQL union type

```python
TagContentType = strawberry.union(
    "TagContentType",
    (BookType, ArticleType, VideoType),
)


@strawberry.django.type(Tag)
class TagType:
    id: ID
    name: auto

    @strawberry.django.field
    def content_object(self) -> TagContentType | None:
        instance = getattr(self, "instance", self)
        return getattr(instance, "content_object", None)
```

### Inline fragments query

```graphql
query {
  tags {
    id
    name
    contentObject {
      ... on BookType { id title author }
      ... on ArticleType { id title content publishedDate }
      ... on VideoType { id title url duration }
    }
  }
}
```
