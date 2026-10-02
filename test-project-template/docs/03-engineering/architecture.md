# Code layout

The app is intentionally small, but separates rules, state, and presentation so a new request has clear places to fit.

| Path | Responsibility |
| --- | --- |
| `lib/domain/task.dart` | Immutable task values, title validation, and pure list transformations for create, update, completion, delete, and filtering. |
| `lib/domain/auth.dart` | Demo sign-in result and user-facing failure descriptions. |
| `lib/application/daybook_providers.dart` | Riverpod controllers that hold the signed-in demo user and current task list. |
| `lib/presentation/login_page.dart` | Sign-in form and local error display. |
| `lib/presentation/task_list_page.dart` | Task search, filters, count, editing, and list display. |
| `lib/main.dart` | App setup and signed-out/signed-in screen selection. |
| `test/domain/task_test.dart` | Existing checks for task creation and completion transformations. |

Task functions return new lists and do not change the list they receive. Validation uses `Either` from `fpdart`, making success and failure explicit. Riverpod is the state boundary between those rules and the Flutter screens. The app does not yet have repositories, networking, routing, or saved storage; add them only when an approved feature needs them.
