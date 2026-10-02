import 'package:fpdart/fpdart.dart';

enum TaskFailure { titleRequired, taskNotFound }

enum TaskFilter { all, active, complete }

final class Task {
  const Task({required this.id, required this.title, this.isComplete = false});

  final String id;
  final String title;
  final bool isComplete;

  Task withCompletion(bool value) =>
      Task(id: id, title: title, isComplete: value);

  Task withTitle(String value) =>
      Task(id: id, title: value, isComplete: isComplete);
}

const sampleTasks = <Task>[
  Task(id: 'sample-1', title: 'Review the week'),
  Task(id: 'sample-2', title: 'Buy groceries'),
  Task(id: 'sample-3', title: 'Call Sam', isComplete: true),
];

Either<TaskFailure, Task> createTask({
  required String id,
  required String title,
}) =>
    switch (title.trim()) {
      '' => left(TaskFailure.titleRequired),
      final normalizedTitle => right(Task(id: id, title: normalizedTitle)),
    };

List<Task> addTask(List<Task> tasks, Task task) =>
    List.unmodifiable([...tasks, task]);

Either<TaskFailure, List<Task>> updateTask(
  List<Task> tasks,
  String taskId,
  String title,
) =>
    createTask(id: taskId, title: title).flatMap(
      (updated) => tasks.any((task) => task.id == taskId)
          ? right(
              List.unmodifiable(
                tasks.map((task) =>
                    task.id == taskId ? task.withTitle(updated.title) : task),
              ),
            )
          : left(TaskFailure.taskNotFound),
    );

List<Task> setTaskCompletion(
  List<Task> tasks,
  String taskId,
  bool isComplete,
) =>
    List.unmodifiable(
      tasks.map(
        (task) => task.id == taskId ? task.withCompletion(isComplete) : task,
      ),
    );

List<Task> deleteTask(List<Task> tasks, String taskId) =>
    List.unmodifiable(tasks.where((task) => task.id != taskId));

List<Task> filterTasks(List<Task> tasks, TaskFilter filter, String query) =>
    List.unmodifiable(
      tasks.where((task) {
        final matchesFilter = switch (filter) {
          TaskFilter.all => true,
          TaskFilter.active => !task.isComplete,
          TaskFilter.complete => task.isComplete,
        };
        return matchesFilter &&
            task.title.toLowerCase().contains(query.trim().toLowerCase());
      }),
    );
