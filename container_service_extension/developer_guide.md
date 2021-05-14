# Check-list

This is the checklist of steps to be performed at the beginning of each 
release cycle of CSE.

# Server

## Terminology
* remote template cookbook - refers to the template descriptor yaml file (template.yaml or template_v2.yaml).
  Templates released by CSE are found in https://github.com/vmware/container-service-extension-templates.
* Supported templates - new templates introduced since CSE 3.1 will have template descriptors containing min_cse_version
  and max_cse_version keys. Supported templates for a given CSE version are those templates such that the CSE version falls
  between min_cse_version and max_cse_version of the template.
* Unsupported templates - Templates whose template descriptor values for min_cse_version and max_cse_version falls
  out of range of the given CSE version.

## API versioning
(To be updated by Aritra)
Update the CSE server supported API version set - (file references)

Starting 3.1, CSE is going to be liberal at what it accepts and conservative in what it sends out.
One cluster API handler (request_handlers/cluster_handler.py) is expected to 
accept and process all the requests coming at any API version (>=36) and any 
RDE payload version (>= 2.0)

## API endpoints
(To be updated by Aritra)
Guidelines on
- how to edit the request dispatcher maps.
- when to add a new endpoint.
- rules to follow to maintain backward compatibility

## RDE
RDEs offer persistence in VCD for otherwise CSE's K8 clusters. It contains two 
parts a)the latest desired state expressed by the user b)the current state of the cluster. 

Versioning terminology:
- Runtime RDE version represents the RDE version chosen by the CSE server to 
  represent the clusters. It varies depending on the VCD version that is configured with CSE server. 
  For example, a)when CSE 3.1 is configured with VCD 10.2, RDE 1.0 becomes CSE 3.1's runtime RDE version.
  b)when CSE 3.1 is configured with VCD 10.3, RDE 2.0 becomes CSE 3.1's runtime RDE version.
- 2.X represents the latest minor version under the given major version line 
- 2.1 literally represents the 2.1 version.
  
Versioning guidelines:
- Based on the anticipated schema changes and its dependencies on VCD version, 
  determine whether major or minor version needs to be bumped up. 
  Use https://semver.org/ for versioning guidelines. In short, bump up the 
  major version only when there is an addition of new required properties, deletion of 
  existing required properties or strict dependency on features of a particular VCD version.
- The goal must be always to provide the latest features (newer RDE versions) 
  on older versions of VCD. When this cannot be achieved for any reason, that 
  is an indication to bump up the major version.
  
Code organization:
- cluster_service_2x.py represents the backend related to RDE major version = 2. 
  We are supposed to overwrite the file for any changes related to minor version 
  increments under major version = 2.
- The idea is to maintain one cluster_service_XX file per each major version line.

Steps:
1. Create new schema file under /cse_def_schema/schema_x_y_z.json.
2. Update below classes and tables for the finalized RDE version. There could 
   be more trivial constructs to be updated. Updating the below should lead you 
   to the other constructs. Below can be found in ../rde/constants.py and ../rde/common_models.py
   - class SchemaFile(Enum): represents the Schema file to be used for a given RDE version
   - class EntityType(Enum): represents the Entity Type for a given RDE version
   - class RuntimeRDEVersion(Enum): represents the RDE version to be used for a given major version line.
   - MAP_VCD_API_VERSION_TO_RUNTIME_RDE_VERSION: dictates the RDE version to be used by the CSE server at runtime based on the VCD version it is configured with.
   - MAP_RDE_VERSION_TO_ITS_METADATA: dictates the constructs to be registered at the time of installation and upgrade for a given RDE version.
   - MAP_VCD_API_VERSION_TO_RDE_VERSION: Maps the RDE version introduced at a given API version
   - MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION: maps the payload version string to the rde version.

## CSE Install
1. RDE schema registration - Ensure right runtime RDE version is chosen and 
   right schema is registered - container_service_extension.installer.configure_cse._register_def_schema
   
## CSE Upgrade
(To be updated by Aritra and Sakthi)
1. RDE schema registration - Ensure right runtime RDE version is chosen and 
   right schema is registered - container_service_extension.installer.configure_cse._register_def_schema
2. Open new upgrade paths (references and guidelines - to be updated)
3. Upgrade existing RDE instances to newer runtime RDE chosen by the server (references and guidelines - to be updated)

## CSE start-up
1. Make sure feature flags, VCD api version in extension are not changed after CSE install/upgrade
2. Ensure that unsupported templates are not loaded into runtime config.
3. Ensure native placement policies are set up and are loaded to runtime config.
4. Determine the CSE server API version at runtime.
5. Ensure right runtime RDE version is loaded into the config variable.
6. Ensure the templates' metadata is correctly loaded into config variable.
    
## Telemetry
(To be filled by Sakthi)

# CLI
1. Update any new NativeEntity models with sample_native_entity()
2. Ensure proper mapping between VCD api version and Runtime RDE version for all supported VCD API versions are available.
3. Update mappings in command_filter.py and make sure right commands and sub-commands are exposed at the right API versions.
4. Auto-negotiate the VCD api version to be used to communicate with CSE server.
   - Update the CSE CLI supported API version set.
5. Ensure the right cloudapi endpoint is used for cluster list and cluster info operations.
6. Dynamically compute the RDE version to use based on the CSE server side configuration.

# Template management
1. Ensure all scripts for each of the template descriptor in template.yaml and template_v2.yaml are present in scripts and scripts_v2 directories respectively.
2. Make sure that only one revision of a template (not necessarily the same) is present in each of tempalte.yaml and template_v2.yaml.
2. Block non-legacy template install, CSE upgrade or CSE install if remote template cookbook doesn't contain required keys (min_cse_version and max_cse_version).
3. Ensure only supported templates are installed during CSE install/CSE upgrade.
4. Make sure non-legacy CSE upgrade with skip-template-install option ignores update to unsupported templates which are already present.
5. Ensure cse template list yields only the list of templates supported by the CSE version.
6. Update min and max versions of CSE version in each of the template definition
   at https://github.com/vmware/container-service-extension-templates/blob/upgrades/template_v2.yaml
7. Ensure metadata on existing templates is updated correctly during the upgrade process.
