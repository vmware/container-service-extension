# CSE Testing

## Usage

```bash
$ pip install -r test-requirements.txt
$ cd container-service-extension/system_tests

# modify base_config.yaml (more info in next section)
# set up vCD instance (org, ovdc, ovdc network)

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
$ pytest --verbose # -v increases testing verbosity
$ pytest --capture=no # -s print all output during testing (tells pytest not to capture output)
$ pytest --disable-warnings

# Common use case (outputs to 'testlog')
$ pytest --disable-warnings -x -v -s test_cse_server.py > testlog
```

## base_config.yaml

Testers should fill out this config file with vCD instance details

Options for **'test'** section:

| key                  | description                                                                                                                                                                                                                                         | value type | possible values | default value |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|-----------------|---------------|
| teardown_installation | - Affects **test_cse_server.py** <br> - If True, delete all installation entities (even on test failure) <br> - If False, do not delete installation entities (even on test failure) <br> - If omitted, defaults to True                            | bool       | True, False     | True          |
| teardown_clusters     | - Affects **test_cse_client.py** <br> - If True, delete test cluster on test failure <br> - If False, do not delete test cluster on test failure <br> - If omitted, defaults to True <br> - Successful client tests will not leave clusters up <br> | bool       | True, False     | True          |
| test_all_templates    | - Affects **test_cse_client.py** <br> - If True, tests cluster operations on all templates found <br> - If False, tests cluster operations only for 1st template found <br> - If omitted, defaults to False                                         | bool       | True, False     | False         |

## Notes

- Client tests (**test_cse_client.py**) require an cluster admin and cluster author user with the same username and password specified in the config file **vcd** section
- Server tests (**test_cse_server.py**) require you to have a public/private SSH key (RSA)
  - These keys should be at: `~/.ssh/id_rsa` and `~/.ssh/id_rsa.pub`
  - Keys must not be password protected (to remove key password, use `ssh-keygen -p`)
  - ssh-key help: <https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/>
- More detailed information can be found in the module docstrings

---

## Writing Tests with Pytest and Click

Before writing a test, first check **conftest.py** for any 'autouse=True' fixtures. Then check
the module itself for any 'autouse=True' fixtures. When writing a test, any fixtures
defined in **conftest.py** can be used. When creating new fixtures, place it in the module
if its functionality is specific to that test module. If the functionality can be used
across multiple test modules, then place it in **conftest.py**

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

| keyword | description                                                | value type | possible values                          | default value |
|---------|------------------------------------------------------------|------------|------------------------------------------|---------------|
| scope   | defines when and how often the fixture should run          | str        | 'session', 'module', 'class', 'function' | 'function'    |
| autouse | if True, fixture runs automatically with respect to @scope | bool       | True, False                              | False         |

- Fixture teardown (after yield) executes even if test raises an exception (including AssertionError)

- Shared fixtures should be defined in **conftest.py** according to pytest conventions. Fixtures defined here are autodiscovered by pytest and don't need to be imported.

- Fixtures specific to a test module should be defined in the module directly.

### Click's CLIRunner

## Example

```python
import container_service_extension.system_test_framework.environment as env
from container_service_extension.server_cli import cli
from vcd_cli.vcd import vcd

# test command: `cse sample --output myconfig.yaml`
cmd = 'sample --output myconfig.yaml'
result = env.CLI_RUNNER.invoke(cli, cmd.split(), catch_exceptions=False)
# catch_exceptions=False tell Click not to swallow exceptions, so we can inspect if something went wrong
assert result.exit_code == 0, f"Command [{cmd}] failed."

# test command: `vcd cse template list`
cmd = 'cse template list'
result = env.CLI_RUNNER.invoke(vcd, cmd.split(), catch_exceptions=False)
assert result.exit_code == 0, f"Command[{cmd}] failed."
```

These small tests using Click's `CLIRunner` and `invoke` function only validate command structure.
These assert statements will pass because the commands themselves are valid, even if an error is thrown during the command execution.

## Pytest logging mechanism

pytest-logger is a plugin used to log during test execution. The plugin makes use of hooks to configure logs.
The `pytest_logger.py` file contains the logger which can be imported in different test files.

The hooks `pytest_logger_config(logger_config)` and `pytest_logger_logdirlink(config)` are configured in conftest.py to create
a symlink `pytest_log` to log directory created by pytest. A different log file will be created for each test executed.

To log information, please import and use the logger PYTEST_LOGGER defined in `pytest_logger.py` module.

---

### Helpful links

- Usage and Invocations: <https://docs.pytest.org/en/latest/usage.html>
- Fixtures: <https://docs.pytest.org/en/latest/fixture.html>
- Click Testing: <http://click.palletsprojects.com/en/7.x/testing/>
- Logging: <https://pypi.org/project/pytest-logger/>