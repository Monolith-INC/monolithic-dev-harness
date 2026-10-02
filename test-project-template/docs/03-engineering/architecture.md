# Architecture

- `lib/main.dart` starts the Material app.
- `lib/domain/task.dart` defines the immutable task record, sample data, and pure list updates.
- `lib/presentation/task_list_page.dart` renders the task list and owns temporary screen state.
- `test/domain/task_test.dart` checks the task-list transformations.

The app has no persistence or network boundary. Keep changes small while the project is a prototype;
add a boundary when a real requirement needs one.
