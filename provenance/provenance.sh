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
    awk  'NR > 3 && /^#/ {print "\""$2":"$3"\""}' ./requirements.txt
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

head=$(git log -1 --pretty=format:%H)
version=$(git describe --tags --abbrev=0)
identifier=$(git describe --tags)
components=$(getComponents)

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
                    \"branch\": \"main\",
                    \"host\": \"github.com\",
                    \"path\": \"vmware/$project\",
                    \"ref\": \"$head\",
                    \"protocol\": \"git\"
                }
            ],
            \"target_repositories\": [
                {
                    \"content\": \"binary\",
                    \"protocol\": \"https\",
                    \"host\": \"github.com\",
                    \"path\": [
                        \"vmware/$project/releases/tag/$version\"
                    ]
                }
            ],
            \"components\": [
                ${components%,}
            ],
            \"actions\": {
                \"edit-changelog\": {
                    \"typename\": \"action\"
                },
                \"create-zipped-binaries\": {
                    \"typename\": \"action\"
                },
                \"create-github-tag\": {
                    \"typename\": \"action\"
                },
                \"prepare-next-version\": {
                    \"typename\": \"action\"
                }
            }
        }
    }
}"

cd ..
rm -rf $tmpDir
echo "$provenanceJsonTemplate" > provenance-$project-$version.json
