import 'package:fpdart/fpdart.dart';

enum SignInFailure { emailRequired, passwordRequired, invalidCredentials }

final class DemoUser {
  const DemoUser({
    this.id = 'demo-user',
    this.email = 'demo@daybook.local',
    this.displayName = 'Daybook Demo',
  });

  final String id;
  final String email;
  final String displayName;
}

Either<SignInFailure, DemoUser> signInDemoUser(
  String email,
  String password,
) =>
    switch ((email.trim().toLowerCase(), password)) {
      ('', _) => left(SignInFailure.emailRequired),
      (_, '') => left(SignInFailure.passwordRequired),
      ('demo@daybook.local', 'daybook123') => right(const DemoUser()),
      _ => left(SignInFailure.invalidCredentials),
    };

String signInFailureMessage(SignInFailure failure) => switch (failure) {
      SignInFailure.emailRequired => 'Enter the demo email address.',
      SignInFailure.passwordRequired => 'Enter the demo password.',
      SignInFailure.invalidCredentials =>
        'The demo email or password is incorrect.',
    };
