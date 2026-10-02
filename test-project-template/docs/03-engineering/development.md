# Local development

## Requirements

- Flutter and Dart versions compatible with `pubspec.yaml`.
- Network access the first time packages are resolved.

## Start

From the project directory:

```sh
flutter pub get
flutter run
```

Use the demo email and password shown on the sign-in screen. The project uses `fpdart` for explicit success and failure results and `flutter_riverpod` for app state. It does not require credentials, cloud configuration, or a server.

For the harness workflow goals and observation rules, see the project-root [`ideas.md`](../../ideas.md) file and the [local backlog](../../backlog/README.md).
