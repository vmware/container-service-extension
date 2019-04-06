These script files are used during testing, as long as tests are ran
in the 'system_tests' directory.

cust-photon-v2.sh and cust-ubuntu-16.04.sh are used during CSE installation.
Some tests will blank out these files to cut down testing time significantly.

By default, these scripts are populated. When these scripts become blanked out,
they become restored via copying the identical static scripts in: `system_tests/scripts/static/`
