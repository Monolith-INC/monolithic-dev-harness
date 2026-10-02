import 'package:flutter/material.dart';

import 'presentation/task_list_page.dart';

void main() => runApp(const DaybookApp());

class DaybookApp extends StatelessWidget {
  const DaybookApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Daybook',
    theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
    home: const TaskListPage(),
  );
}
