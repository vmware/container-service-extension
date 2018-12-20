These script files are used during testing, as long as tests are ran
in the 'system_tests' directory.

cust-photon-v2.sh and cust-ubuntu-16.04.sh are used during CSE installation.
By default, these scripts are blank, because most tests 
do not require the VM to be customized. This cuts down testing time significantly.

When VM customization is required, use prepare_real_customization_scripts() from system test utils.
After each test, customization files will be restored to how they were originally.