final class Task {
  const Task({required this.id, required this.title, this.isComplete = false});

  final String id;
  final String title;
  final bool isComplete;

  Task withCompletion(bool value) =>
      Task(id: id, title: title, isComplete: value);
}

const sampleTasks = <Task>[
  Task(id: 'sample-1', title: 'Review the week'),
  Task(id: 'sample-2', title: 'Buy groceries'),
  Task(id: 'sample-3', title: 'Call Sam', isComplete: true),
];

List<Task> addTask(List<Task> tasks, Task task) =>
    List.unmodifiable([...tasks, task]);

List<Task> setTaskCompletion(
  List<Task> tasks,
  String taskId,
  bool isComplete,
) => List.unmodifiable(
  tasks.map(
    (task) => switch (task.id == taskId) {
      true => task.withCompletion(isComplete),
      false => task,
    },
  ),
);
