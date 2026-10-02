import 'package:flutter/material.dart';

import '../domain/task.dart';

class TaskListPage extends StatefulWidget {
  const TaskListPage({super.key});

  @override
  State<TaskListPage> createState() => _TaskListPageState();
}

class _TaskListPageState extends State<TaskListPage> {
  final ValueNotifier<List<Task>> _tasks = ValueNotifier(sampleTasks);
  final TextEditingController _titleController = TextEditingController();

  @override
  void dispose() {
    _tasks.dispose();
    _titleController.dispose();
    super.dispose();
  }

  void _addTask() {
    final title = _titleController.text.trim();
    if (title.isNotEmpty) {
      _tasks.value = addTask(
        _tasks.value,
        Task(
          id: DateTime.now().microsecondsSinceEpoch.toString(),
          title: title,
        ),
      );
      _titleController.clear();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Daybook')),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('task-title-input'),
                  controller: _titleController,
                  decoration: const InputDecoration(
                    labelText: 'New task',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _addTask(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                key: const Key('add-task-button'),
                tooltip: 'Add task',
                onPressed: _addTask,
                icon: const Icon(Icons.add),
              ),
            ],
          ),
        ),
        Expanded(
          child: ValueListenableBuilder<List<Task>>(
            valueListenable: _tasks,
            builder: (context, tasks, _) => ListView(
              children: tasks
                  .map(
                    (task) => CheckboxListTile(
                      key: ValueKey('task-${task.id}'),
                      title: Text(task.title),
                      value: task.isComplete,
                      onChanged: (value) {
                        if (value case final bool isComplete) {
                          _setTaskCompletion(task.id, isComplete);
                        }
                      },
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
        ),
      ],
    ),
  );

  void _setTaskCompletion(String taskId, bool isComplete) =>
      _tasks.value = setTaskCompletion(_tasks.value, taskId, isComplete);
}
