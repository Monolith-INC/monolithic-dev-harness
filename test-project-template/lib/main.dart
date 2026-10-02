import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'application/daybook_providers.dart';
import 'presentation/login_page.dart';
import 'presentation/task_list_page.dart';

void main() => runApp(const ProviderScope(child: DaybookApp()));

class DaybookApp extends StatelessWidget {
  const DaybookApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Daybook',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0)),
          useMaterial3: true,
        ),
        home: const DaybookHome(),
      );
}

class DaybookHome extends ConsumerWidget {
  const DaybookHome({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) =>
      switch (ref.watch(authProvider)) {
        null => const LoginPage(),
        _ => const TaskListPage(),
      };
}
