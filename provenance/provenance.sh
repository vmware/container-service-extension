#!/bin/bash
catch() {
  retval=$?
  error_message="$(date) $(caller): $BASH_COMMAND"
  echo "$error_message" &> error.log
}
trap 'catch $? $LINENO' ERR
set -e


# Reads requirements.txt and returns its contents with the following syntax:
# <module>:<version>
function getPyModules {
    awk  'NR > 3 && /^#/ {print "\""$2":"$3"\","}' ./requirements.txt
}

# Returns the given amount of spaces, intended for JSON identation
function indent {
    for _ in $(seq 1 $1)
    do
        printf ' '
    done
}

# Gets the "components" elements for the Provenance JSON
function getComponents {
    rawPyModules=$(getPyModules)
    for module in $rawPyModules
    do
        indent 16
        echo "{"
        indent 20
        echo "\"name\": $module"
        indent 20
        echo "\"incorporated\": true"
        indent 16
        echo "},"
    done
}

# ---------------
# Script init
# ---------------

if [ $# != 1 ]
then
    echo "Usage: ./provenance.sh <PROJECT NAME>"
    echo ""
    echo "PROJECT NAME: container-service-extension'"
    exit 1
fi

project="$1"

if [[ "$project" != 'container-service-extension' ]] 
then
    echo "PROJECT NAME must be container-service-extension"
    exit 1
fi

tmpDir='tmp'

rm -rf $tmpDir
git clone https://github.com/vmware/$project.git $tmpDir
cd $tmpDir
git checkout origin/cse_3_1_updates

head=$(git log -1 --pretty=format:%H)
version=$(git describe --tags --abbrev=0)
identifier=$(git describe --tags)
components=$(getComponents)
release_version=`curl -s 'https://pypi.org/pypi/container-service-extension/json' | python -mjson.tool | grep \"version\" | awk -F"\"" '{print $4}'`

provenanceJsonTemplate="
{
    \"id\": \"http://vmware.com/schemas/software_provenance-0.2.5.json\",
    \"root\": [\"$project\"],
    \"all_components\": {
        \"$project-$identifier\": {
            \"typename\": \"comp.build\",
            \"name\": \"$project\",
            \"version\": \"$version\",
            \"source_repositories\": [
                {
                    \"content\": \"source\",
                    \"branch\": \"cse_3_1_updates\",
                    \"host\": \"github.com\",
                    \"path\": \"vmware/$project\",
                    \"ref\": \"$head\",
                    \"protocol\": \"git\"
                }
            ],
            \"target_repositories\": [
                {
                    \"content\": \"bdist_wheel\",
                    \"protocol\": \"https\",
                    \"host\": \"pypi.org\",
                    \"path\": [
                        \"project/$project/$release_version/\"
                    ]
                }
            ],
            \"components\": [
                ${components%,}
            ]
        }
    }
}"

cd ..
rm -rf $tmpDir
echo "$provenanceJsonTemplate" > provenance-$project-$version.json
