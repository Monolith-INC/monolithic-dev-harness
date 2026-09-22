# Clean Architecture & Feature-First Structure

## 1. Core Principles

1. **Adhere strictly to Clean Architecture**. The application is divided into layers: Presentation, Domain, and Data.
2. **Dependency Rule**: Dependencies ONLY point inwards.
   - **Domain** (Inner circle): Depends on NOTHING. Pure Dart code.
   - **Data** (Outer circle): Depends on **Domain**.
   - **Presentation** (Outer circle): Depends on **Domain**.
   - **Drivers/Frameworks**: The outermost layer (UI, DB, External APIs) depends on adapters in Data/Presentation.

## 2. Folder Structure (Feature-Based)

Organize the codebase by **Feature**, not by Type. Every feature must be self-contained.

**REQUIRED PATTERN**: `lib/features/<feature_name>/` containing:

- **`domain/`**:
  - `entities/`: Pure business objects.
  - `repositories/`: Abstract interfaces (contracts) for data access.
  - `usecases/`: Application-specific business rules implementation.
- **`data/`**:
  - `datasources/`: Remote/Local data fetchers (APIs, DBs).
  - `models/`: DTOs (Data Transfer Objects) that extend/implement Entities and handle serialization (JSON).
  - `repositories/`: Concrete implementations of domain repository interfaces.
- **`presentation/`**:
  - `pages/` or `screens/`: UI Screens.
  - `widgets/`: Feature-specific widgets.
  - `providers/` or `blocs/`: State management (referencing UseCases).

**Example**:

```text
lib/features/authentication/
  ├── domain/
  │   ├── entities/user.dart
  │   ├── repositories/auth_repository.dart
  │   └── usecases/login_user.dart
  ├── data/
  │   ├── datasources/auth_remote_datasource.dart
  │   ├── models/user_model.dart
  │   └── repositories/auth_repository_impl.dart
  └── presentation/
      ├── pages/login_page.dart
      └── providers/auth_provider.dart
```

## 3. Strict Compliance Rules

- **DO NOT** import `data` layers into `domain`.
- **DO NOT** import `presentation` layers into `domain` or `data`.
- **DO NOT** put business logic in Widgets. Use UseCases.
- **DO** define repository interfaces in `domain` and implement them in `data`.
- **DO** use DTOs/Models in the `data` layer and map them to Entities before returning to `domain`.

Failure to follow this structure violates the project workspace rules.
