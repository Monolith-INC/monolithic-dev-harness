# Daybook

Daybook is a small Flutter task-list app used as a realistic project for trying the development harness. It builds on the original task-list prototype and keeps its data local to the running app.

## What works

- Sign in and sign out with the built-in demo account.
- Add a task, view the task list, edit a title, mark a task done or active, and delete a task.
- Search task titles and view all, active, or completed tasks.
- See how many tasks are still active.
- Reject blank task titles and show sign-in errors.

The demo credentials are `demo@daybook.local` and `daybook123`. This is a local demonstration only: there is no account server, password security, or saved sign-in session. Tasks reset to the sample list when the app restarts.

## Run the app

With Flutter installed:

```sh
flutter pub get
flutter run
```

See [the project notes](docs/README.md) for the current product, design, code, and testing context. The local backlog is in [backlog/](backlog/README.md).
