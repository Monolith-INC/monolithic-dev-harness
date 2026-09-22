# Automated Testing Standards

**Codex Anchor**: `[[Knowledge/Agentic_Governance]]` (Section 4: Agentic Testing & Verification)
*Read the anchor above to align with the Recursive Verification Loop protocol.*

## 1. Core Philosophy

* **Behavior Driven Development (BDD)**: All tests must be structured to describe behavior, not implementation.
* **Layer-Specific Strategies**: The testing strategy changes depending on the architectural layer being tested.
* **Zero-Mock Domain**: The domain layer must remain pure and testable without mocks.

## 2. Naming & Structure

* **File Naming**: `*_test.dart`
* **Group Structure**:
  * Outer `group`: The class or method under test.
  * Context `group`: Starts with "Given" (e.g., `group('Given User is Administrator', ...)`).
  * Test case `test`: Starts with "should" (e.g., `test('should return true', ...)`).
* **Record Patterns**: Use Dart Records for parameterized tests to avoid duplication.

    ```dart
    final scenarios = [
      (input: 'a', expected: true),
      (input: 'b', expected: false),
    ];
    for (final scenario in scenarios) {
      test('Given ${scenario.input}, should result in ${scenario.expected}', () { ... });
    }
    ```

## 3. Layer-Specific Rules

### A. Domain Layer (Entities, Value Objects, Aggregates)

* **Strategy**: **Sociable Unit Tests**.
* **Mocks**: **FORBIDDEN**. Never mock domain entities. Instantiate real objects.
* **Reasoning**: Domain logic is self-contained. Using real objects ensures the integrity of the domain model and simplifies test setup.
* **Example**:

    ```dart
    // CORRECT
    final user = User(id: UserId('1'));
    final account = Account(members: [user]);
    
    // INCORRECT
    final user = MockUser();
    ```

### B. Application Layer (Use Cases, Services)

* **Strategy**: **Solitary Unit Tests**.
* **Mocks**: **REQUIRED** for external dependencies (Repositories, Gateways).
* **Tools**: Use `Mockito` with `@GenerateMocks`.
* **Dependency Injection**: Inject test doubles through the project's own dependency-injection mechanism (its test mode, a container override, or constructor injection).
* **Focus**: Verify orchestration, validation logic, and repository interactions using `verify()`.

### C. Infrastructure Layer (Repositories, Mappers, Data Sources)

* **Strategy**: **Hybrid / Integration**.
* **Mocks**: Allow manual mocking for simple data containers or 3rd party wrappers.
* **Focus**: Verify data transformations (`fromDataModel`, `toDataModel`), handling of nulls, and error mapping.

## 4. Testing Tools

* **Framework**: `package:flutter_test` (even for pure Dart unit tests to keep consistency).
* **Mocking**: `package:mockito`.
* **Assertions**: `package:flutter_test` matchers (`expect`, `isA`, `throwsA`).
