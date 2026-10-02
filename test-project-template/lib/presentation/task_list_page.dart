import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fpdart/fpdart.dart' hide State, Task;

import '../application/daybook_providers.dart';
import '../domain/task.dart';

class TaskListPage extends ConsumerStatefulWidget {
  const TaskListPage({super.key});

  @override
  ConsumerState<TaskListPage> createState() => _TaskListPageState();
}

class _TaskListPageState extends ConsumerState<TaskListPage> {
  final _searchController = TextEditingController();
  TaskFilter _filter = TaskFilter.all;
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _openEditor({Task? task}) => showDialog<void>(
        context: context,
        builder: (_) => TaskEditorDialog(
          initialTitle: task?.title ?? '',
          onSave: (title) => task == null
              ? ref.read(taskListProvider.notifier).add(title).map((_) => true)
              : ref
                  .read(taskListProvider.notifier)
                  .update(task.id, title)
                  .map((_) => true),
        ),
      );

  Future<void> _confirmDelete(Task task) async {
    final shouldDelete = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete task?'),
        content: Text('“${task.title}” will be removed from this list.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (shouldDelete case true) {
      ref.read(taskListProvider.notifier).delete(task.id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider);
    final allTasks = ref.watch(taskListProvider);
    final visibleTasks = filterTasks(allTasks, _filter, _query);
    final remaining = allTasks.where((task) => !task.isComplete).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Daybook'),
        actions: [
          IconButton(
            key: const Key('sign-out-button'),
            tooltip: 'Sign out',
            onPressed: ref.read(authProvider.notifier).signOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
                child: Text(
                  'Hello, ${user?.displayName ?? 'friend'}',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  remaining == 1 ? '1 task left' : '$remaining tasks left',
                  key: const Key('remaining-task-count'),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: TextField(
                  key: const Key('task-search-input'),
                  controller: _searchController,
                  onChanged: (query) => setState(() => _query = query),
                  decoration: InputDecoration(
                    labelText: 'Find a task',
                    prefixIcon: const Icon(Icons.search),
                    border: const OutlineInputBorder(),
                    suffixIcon: _query.isEmpty
                        ? null
                        : IconButton(
                            tooltip: 'Clear search',
                            onPressed: () {
                              _searchController.clear();
                              setState(() => _query = '');
                            },
                            icon: const Icon(Icons.clear),
                          ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Wrap(
                  spacing: 8,
                  children: TaskFilter.values
                      .map(
                        (filter) => ChoiceChip(
                          label: Text(_filterLabel(filter)),
                          selected: _filter == filter,
                          onSelected: (_) => setState(() => _filter = filter),
                        ),
                      )
                      .toList(growable: false),
                ),
              ),
              Expanded(
                child: visibleTasks.isEmpty
                    ? Center(
                        child: Text(
                          allTasks.isEmpty
                              ? 'Your list is empty. Add a task to get started.'
                              : 'No tasks match this view.',
                          textAlign: TextAlign.center,
                        ),
                      )
                    : ListView(
                        padding: const EdgeInsets.all(16),
                        children: visibleTasks
                            .map(
                              (task) => Card(
                                child: CheckboxListTile(
                                  key: ValueKey('task-${task.id}'),
                                  title: Text(task.title),
                                  value: task.isComplete,
                                  onChanged: (value) {
                                    if (value case final bool isComplete) {
                                      ref
                                          .read(taskListProvider.notifier)
                                          .setCompletion(task.id, isComplete);
                                    }
                                  },
                                  secondary: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        tooltip: 'Edit ${task.title}',
                                        onPressed: () =>
                                            _openEditor(task: task),
                                        icon: const Icon(Icons.edit_outlined),
                                      ),
                                      IconButton(
                                        tooltip: 'Delete ${task.title}',
                                        onPressed: () => _confirmDelete(task),
                                        icon: const Icon(Icons.delete_outline),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            )
                            .toList(growable: false),
                      ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('add-task-button'),
        onPressed: () => _openEditor(),
        icon: const Icon(Icons.add),
        label: const Text('Add task'),
      ),
    );
  }
}

String _filterLabel(TaskFilter filter) => switch (filter) {
      TaskFilter.all => 'All',
      TaskFilter.active => 'To do',
      TaskFilter.complete => 'Done',
    };

class TaskEditorDialog extends StatefulWidget {
  const TaskEditorDialog({
    required this.initialTitle,
    required this.onSave,
    super.key,
  });

  final String initialTitle;
  final Either<TaskFailure, bool> Function(String title) onSave;

  @override
  State<TaskEditorDialog> createState() => _TaskEditorDialogState();
}

class _TaskEditorDialogState extends State<TaskEditorDialog> {
  late final _titleController = TextEditingController(
    text: widget.initialTitle,
  );
  String? _errorMessage;

  @override
  void dispose() {
    _titleController.dispose();
    super.dispose();
  }

  void _save() => widget.onSave(_titleController.text).match(
        (failure) => setState(() => _errorMessage = switch (failure) {
              TaskFailure.titleRequired => 'Enter a task title.',
              TaskFailure.taskNotFound => 'This task is no longer available.',
            }),
        (_) => Navigator.pop(context),
      );

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(widget.initialTitle.isEmpty ? 'Add a task' : 'Edit task'),
        content: TextField(
          key: const Key('task-title-input'),
          autofocus: true,
          controller: _titleController,
          textCapitalization: TextCapitalization.sentences,
          onSubmitted: (_) => _save(),
          decoration: InputDecoration(
            labelText: 'Task title',
            border: const OutlineInputBorder(),
            errorText: _errorMessage,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(onPressed: _save, child: const Text('Save')),
        ],
      );
}
