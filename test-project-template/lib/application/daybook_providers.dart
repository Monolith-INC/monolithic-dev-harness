import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fpdart/fpdart.dart' hide Task;

import '../domain/auth.dart';
import '../domain/task.dart';

final authProvider = NotifierProvider<AuthController, DemoUser?>(
  AuthController.new,
);

final taskListProvider = NotifierProvider<TaskListController, List<Task>>(
  TaskListController.new,
);

class AuthController extends Notifier<DemoUser?> {
  @override
  DemoUser? build() => null;

  Either<SignInFailure, DemoUser> signIn(String email, String password) {
    final result = signInDemoUser(email, password);
    result.match((_) {}, (user) => state = user);
    return result;
  }

  void signOut() => state = null;
}

class TaskListController extends Notifier<List<Task>> {
  @override
  List<Task> build() => sampleTasks;

  Either<TaskFailure, Task> add(String title) {
    final result = createTask(
      id: DateTime.now().microsecondsSinceEpoch.toString(),
      title: title,
    );
    result.match((_) {}, (task) => state = addTask(state, task));
    return result;
  }

  Either<TaskFailure, List<Task>> update(String taskId, String title) {
    final result = updateTask(state, taskId, title);
    result.match((_) {}, (tasks) => state = tasks);
    return result;
  }

  void setCompletion(String taskId, bool isComplete) =>
      state = setTaskCompletion(state, taskId, isComplete);

  void delete(String taskId) => state = deleteTask(state, taskId);
}
