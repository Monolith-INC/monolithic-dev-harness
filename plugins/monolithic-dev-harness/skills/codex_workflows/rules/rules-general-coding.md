# Laws of code

## General

1. Preserve stability. Before mutation: verify or implement tests.

2. Adhere to context. Integrate changes strictly into existing architectural patterns.

3. Improve clarity. If modifying: leave logic cleaner than found.

4. Enforce atomic steps. If scope is large: decompose into verifiable units.

5. Define clear intent. Reject changes lacking explicit justification.

## Stability & Extension

6. Extend functionality. Treat existing source as immutable.
7. If modification is mandatory: strictly minimize mutation scope.

## III. Dart Strictness

8. **Async Safety.** **Reject** `async` void methods (fire-and-forget) except for event handlers. **Must** use `Future<void>` and `await` calls.
9. **Error Handling.** **Reject** silent failures. All `catch` blocks **must** either handle the error (recovery) or rethrow/log it. Empty catch blocks are prohibited.
10. **Logging.** **Reject** `print()`. **Must** use `logging` package or `dart:developer.log`.
