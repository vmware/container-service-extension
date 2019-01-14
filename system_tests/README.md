# CSE Testing

## Usage

```bash
$ pip install -r test-requirements.txt
$ cd container-service-extension/system_tests

# modify base_config.yaml

# Run all tests (either works)
$ pytest
$ python -m pytest

# Run a test module
$ pytest test_cse_server.py

# Run a test function
$ pytest test_cse_server.py::mytestfunction

# Useful options
$ pytest --exitfirst # -x stop after first failure
$ pytest --maxfail=2 # stop after 2 failures
$ pytest --verbose # -v
$ pytest --capture=no # -s print all output during testing (tells pytest not to capture output)
$ pytest --disable-warnings
```

---

## Writing Tests with Pytest

### Fixtures (setUp, tearDown)

```python
@pytest.fixture()
def my_fixture():
    print('my_fixture setup')
    yield
    print('my_fixture teardown')

@pytest.fixture()
def another_fixture():
    important_variable = {'key': 'value'}
    yield important_variable
    print('another_fixture teardown')

def my_test(my_fixture):
    assert my_fixture is None

def my_test_2(another_fixture):
    assert isinstance(another_fixture, dict)
    print(another_fixture['key'])
```

Common keyword arguments for @pytest.fixture()

|   | keyword | description                                                | value type | possible values                          | default value |
|---|---------|------------------------------------------------------------|------------|------------------------------------------|---------------|
|   | scope   | defines when and how often the fixture should run          | str        | 'session', 'module', 'class', 'function' | 'function'    |
|   | autouse | if True, fixture runs automatically with respect to @scope | bool       | True, False                              | False         |

*Shared fixtures should be defined in **conftest.py** according to pytest conventions. Fixtures defined here are autodiscovered by pytest and don't need to be imported.*

*Fixtures specific to a test module should be defined in the module directly.*

---

### Helpful links:

- Usage and Invocations: https://docs.pytest.org/en/latest/usage.html
- Fixtures: https://docs.pytest.org/en/latest/fixture.html
