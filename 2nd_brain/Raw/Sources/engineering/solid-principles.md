---
Title: "Software Engineering Best Practices"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-09-13
Processed: true
tags: ["source", "engineering"]
---

# Software Engineering Best Practices

## SOLID Principles

### Single Responsibility Principle (SRP)
A class should have only one reason to change.

```python
# Bad: handles both user data and persistence
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
    def save(self):
        # save to database
        pass

# Good: separated concerns
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

class UserRepository:
    def save(self, user: User):
        # save to database
        pass
```

### Open/Closed Principle (OCP)
Software entities should be open for extension, closed for modification.

```python
# Good: extend via inheritance/composition
class Shape:
    def area(self) -> float:
        raise NotImplementedError

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius
    def area(self) -> float:
        return 3.14159 * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
    def area(self) -> float:
        return self.width * self.height
```

### Liskov Substitution Principle (LSP)
Objects of a superclass should be replaceable with objects of its subclasses.

### Interface Segregation Principle (ISP)
No client should be forced to depend on methods it does not use.

### Dependency Inversion Principle (DIP)
Depend on abstractions, not concretions.

## Design Patterns

### Factory Pattern
```python
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def pay(self, amount: float) -> bool: pass

class StripeProcessor(PaymentProcessor):
    def pay(self, amount: float) -> bool:
        # Stripe API call
        return True

class PaymentFactory:
    @staticmethod
    def create(method: str) -> PaymentProcessor:
        if method == "stripe":
            return StripeProcessor()
        raise ValueError(f"Unknown method: {method}")
```

### Observer Pattern
```python
class EventEmitter:
    def __init__(self):
        self._listeners = {}
    
    def on(self, event: str, callback):
        self._listeners.setdefault(event, []).append(callback)
    
    def emit(self, event: str, *args):
        for cb in self._listeners.get(event, []):
            cb(*args)
```

### Strategy Pattern
```python
class SortStrategy:
    def sort(self, data: list) -> list:
        raise NotImplementedError

class QuickSort(SortStrategy):
    def sort(self, data: list) -> list:
        if len(data) <= 1:
            return data
        pivot = data[len(data) // 2]
        left = [x for x in data if x < pivot]
        middle = [x for x in data if x == pivot]
        right = [x for x in data if x > pivot]
        return self.sort(left) + middle + self.sort(right)
```

## System Design

### CAP Theorem
- **Consistency**: All nodes see the same data
- **Availability**: Every request gets a response
- **Partition Tolerance**: System works despite network failures

### Microservices Principles
1. Single responsibility per service
2. Own your data (database per service)
3. API-first design
4. Design for failure
5. Automated deployment

## CI/CD Pipeline Design

1. **Source**: Version control (Git)
2. **Build**: Compile, package
3. **Test**: Unit, integration, e2e
4. **Deploy**: Staging → Production
5. **Monitor**: Logs, metrics, alerts

## Testing Strategies

| Level | What | Speed | Coverage |
|-------|------|-------|----------|
| Unit | Individual functions | Fast | ~70% |
| Integration | Module interactions | Medium | ~20% |
| E2E | Full user flows | Slow | ~10% |

## Code Review Checklist

- [ ] Code compiles/runs
- [ ] Tests pass
- [ ] No security vulnerabilities
- [ ] Follows coding standards
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Error handling present
- [ ] Performance acceptable
