import 'package:flutter_test/flutter_test.dart';

import 'package:daybook/domain/task.dart';

void main() {
  test('adding a task keeps existing tasks and appends the new task', () {
    const added = Task(id: 'new', title: 'Plan tomorrow');

    final result = addTask(sampleTasks, added);

    expect(result.map((task) => (task.id, task.title, task.isComplete)), [
      ...sampleTasks.map((task) => (task.id, task.title, task.isComplete)),
      (added.id, added.title, added.isComplete),
    ]);
    expect(sampleTasks, hasLength(3));
  });

  test('changing completion updates only the matching task', () {
    final result = setTaskCompletion(sampleTasks, 'sample-1', true);

    expect(result.first.isComplete, isTrue);
    expect(result.skip(1), sampleTasks.skip(1));
    expect(sampleTasks.first.isComplete, isFalse);
  });

  test('changing an unknown task leaves the list unchanged', () {
    final result = setTaskCompletion(sampleTasks, 'missing', true);

    expect(
      result.map((task) => (task.id, task.title, task.isComplete)),
      sampleTasks.map((task) => (task.id, task.title, task.isComplete)),
    );
  });
}
