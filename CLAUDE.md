# ManicTime API Client Command Reference

> We are trying to build a `manictime_client` python wrapper. We can use the `ManicTime.API.Client` as a reference. I have included my credentials in the `.env` file. Let's iterate and get this client working!

## Python Commands
- Run all tests: `cd manictime_client && pytest tests/`
- Run single test: `cd manictime_client && pytest tests/test_client.py::test_function_name`

## Code Style Guidelines
- **Python**:
  - Use 4-space indentation
  - Type hints required for all functions/methods
  - Group imports: standard lib → third-party → local
  - Use custom exceptions hierarchy from `exceptions.py`
  - snake_case for functions, variables; PascalCase for classes
  - Private methods prefixed with underscore
  - Document classes and complex methods with docstrings