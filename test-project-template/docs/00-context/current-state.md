# Current state

Daybook is a small Flutter app for one person keeping a short list of everyday tasks. It starts with a local demo sign-in screen. After sign-in, the home screen shows sample tasks and lets the user add, edit, complete, search, filter, and delete tasks.

The app has no server or durable storage. Signing out returns to the sign-in screen, but the same in-memory task list remains for the current process. Restarting the app restores the sample tasks. The sign-in accepts only the credentials shown on screen and is not real authentication.

The existing code separates task rules from Flutter screens. Task values are immutable; list changes are pure transformations, while Riverpod holds the current screen state. `fpdart` represents task validation and sign-in results as either a failure or a success.

The opportunity note and backlog contain requests to investigate. They are not proof that a user need has been validated or that a proposed change is approved.
