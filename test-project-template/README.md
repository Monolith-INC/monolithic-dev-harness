# Daybook

Daybook is a small Flutter app for keeping a personal list of tasks. It is an early prototype: tasks
can be added and marked complete, and the sample list resets when the app restarts.

## Current behavior

- View a short sample task list.
- Add a task with a title.
- Mark a task complete or active.
- Keep all task data in memory for the current app session.

The project has no account, network service, or persistent storage. See [`docs/`](docs/README.md)
for product, design, and engineering context.

## Run and check

With Flutter installed, run:

```bash
flutter pub get
flutter run
flutter test
flutter analyze
```
