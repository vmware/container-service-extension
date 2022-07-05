#!/usr/bin/env bash

set -ex

# URLs for downloading the SRP CLI and Build Observer, depending on the OS that executes this script
# FIXME: The macOS version used is buggy: https://vmware.slack.com/archives/C03GZ0FHSNL/p1656498956140179
if [[ $OSTYPE == 'darwin'* ]]; then
    SRP_CLI_URL='https://artifactory.eng.vmware.com/artifactory/helix-docker-local/cli/srpcli/0.2.20220628180501-5d0311a-22/darwin/srp'
    SRP_OBSERVER_URL='https://artifactory.eng.vmware.com/osspicli-local/observer/macosx-intel-observer-0.0.4.tar.gz'
else
    SRP_CLI_URL='https://artifactory.eng.vmware.com/artifactory/helix-docker-local/cli/srpcli/0.2.20220628180501-5d0311a-22/linux/srp'
    SRP_OBSERVER_URL='https://artifactory.eng.vmware.com/osspicli-local/observer/linux-observer-1.0.4.tar.gz'
fi

# SRP requires a client ID and secret, that can be generated following this guide:
# https://confluence.eng.vmware.com/display/SRPIPELINE/Onboarding+to+SRP+APIs
# Then, the values are stored securely in the Cerberus vault:
# https://console.cerberus.vmware.com/ui/vaults/908a01bc-f9ce-4169-835c-fb7ec9dca68f/secrets
if [ -z "${SRP_CLIENT_ID}" ]; then
    >&2 echo "[ERROR] Environment variable SRP_CLIENT_ID must be defined"
    exit 1
fi

if [ -z "${SRP_CLIENT_SECRET}" ]; then
    >&2 echo "[ERROR] Environment variable SRP_CLIENT_SECRET must be defined"
    exit 1
fi

# Display the help menu if not enough arguments are provided
if [ $# != 3 ]
then
    echo "Usage: SRP_CLIENT_ID='myId' SRP_CLIENT_SECRET='myKey' ./provenance_v2.sh PROJECT_NAME GIT_REF JENKINS_BUILD_NUMBER"
    echo ""
    echo "Required environment variables:"
    echo ""
    echo "  SRP_CLIENT_ID          Oauth client ID to upload Provenance files to SRP platform"
    echo "  SRP_CLIENT_SECRET      Oauth secret to upload Provenance files to SRP platform"
    echo ""
    echo "Required arguments:"   
    echo ""
    echo "  PROJECT_NAME           Should be container-service-extension"
    echo "  GIT REF                Git reference to checkout (ie: HEAD, a commit hash, a branch, a tag...)"
    echo "  JENKINS_BUILD_NUMBER   Jenkins build number, ie: '248'"
    echo ""
    exit 1
fi

project="$1"
git_ref="$2"
jenkins_build_number="$3"
jenkins_job_name="cse-provenance"

# This script creates and uploads provenance data for only one project
if [[ "${project}" != "container-service-extension" ]]
then
    >&2 echo "[ERROR] Project name must be 'container-service-extension' but it was '${project}'"
    exit 1
fi

# Download the SRP CLI which is used to create source provenance and the Build Observer which monitors dependency fetching
echo "[INFO] Downloading SRP tools..."
rm -rf srp-tools

mkdir srp-tools
mkdir srp-tools/observer

wget --quiet --output-document srp-tools/srp "${SRP_CLI_URL}"
wget --quiet --output-document srp-tools/srp-observer.tar.gz "${SRP_OBSERVER_URL}"

tar zxf srp-tools/srp-observer.tar.gz --directory=srp-tools/observer
rm -f srp-tools/srp-observer.tar.gz

chmod +x srp-tools/srp
chmod +x srp-tools/observer/bin/observer_agent.bash

echo "[INFO] SRP cli version: $(./srp-tools/srp --version)"

# Generate SRP UIDs. The convention is described at https://confluence.eng.vmware.com/display/SRPIPELINE/How+to+create+a+SRP+UID
jenkins_job_name="${project}-provenance"
jenkins_instance='sp-taas-vcd-butler.svc.eng.vmware.com'
timestamp="$(date +%Y%m%d%H%M%S)"

obj_uid="uid.obj.build.jenkins(instance='${jenkins_instance}',job_name='${jenkins_job_name}',build_number='${jenkins_build_number}')"
provenance_fragment_uid="uid.mtd.provenance_2_5.fragment(obj_uid=${obj_uid},revision='${timestamp}')"

echo "[INFO] obj_uid: ${obj_uid}"
echo "[INFO] provenance_fragment_uid: ${provenance_fragment_uid}"

# Create local auth configuration with the injected client ID and secret
./srp-tools/srp config auth --client-id="${SRP_CLIENT_ID}" --client-secret="${SRP_CLIENT_SECRET}"
# Force an update to the SRP cli
./srp-tools/srp update --yes

# Clone the project from GitHub to generate the Provenance with its source code
rm -rf tmp
mkdir tmp
git clone "https://github.com/vmware/${project}.git" tmp
cd tmp
git checkout "$git_ref"
pip3 install .
version="$(pip show container-service-extension | awk '/Version: / {print $2}')"
cd ..

# Generate source code provenance file
echo "[INFO] Generating main provenance file..."
rm -rf provenance
mkdir provenance
./srp-tools/srp provenance source --scm-type git --name "${project}" --path ./tmp --saveto ./provenance/source.json \
--comp-uid "${obj_uid}" --build-number "${jenkins_build_number}" --version "${version}" --all-ephemeral true --build-type release

# Generate dependencies provenance file
echo "[INFO] Generating dependencies provenance file..."
cd tmp
../srp-tools/observer/bin/observer_agent.bash -t -o ./ -- pip3 install . --force-reinstall
mv provenance.json ../provenance/dependencies.json
cd ..

# Merge the two files generated above into a final one that will be uploaded to SRP servers
echo "[INFO] Generating final provenance file..."
./srp-tools/srp provenance merge --source ./provenance/source.json --network ./provenance/dependencies.json --saveto ./provenance.json
echo "[INFO] Final provenance file to upload:"
cat provenance.json

# Submit the provenance file to SRP servers
echo "[INFO] Submitting provenance..."
./srp-tools/srp metadata submit --uid "${provenance_fragment_uid}" --path ./provenance.json

# Cleanup
rm -rf provenance
rm -rf srp-tools
rm -rf tmp

