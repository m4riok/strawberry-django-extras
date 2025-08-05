"""
Strawberry Django Extras

A collection of extensions and utilities for Strawberry GraphQL with Django.

All imports must be done directly from their respective modules to prevent
eager loading and async context detection issues.

Core modules:
- decorators: sync_or_async utility
- inputs: CRUD input types
- field_extensions: Field extension classes and factory functions
- jwt.mutations: JWT authentication mutations
- lazy: Context-aware lazy view and consumer classes
"""

__all__ = []
