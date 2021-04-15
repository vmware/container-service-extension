# Check-list

This is the checklist of steps to be performed at the beginning of each 
release cycle of CSE.

# Server

## API versioning
(To be updated by Aritra)
Update the CSE server supported API version set - (file references)

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
(To be updated by Aniruddha)
1. Determine the CSE server API version at runtime.
2. Ensure right runtime RDE version is loaded into the config variable.
3. Ensure the templates' metadata is correctly loaded into config variable.
    
## Telemetry
(To be filled by Sakthi)

# CLI
(To be updated by Aritra sen and Aniruddha)
1. Auto-negotiate the VCD api version to be used to communicate with CSE server.
   - Update the CSE CLI supported API version set.
2. Dynamically compute the RDE version to use based on the CSE server side configuration.

# Template management
(To be updated by Aniruddha)
1. Update min and max versions of CSE version in each of the template definition
   at https://github.com/vmware/container-service-extension-templates/blob/upgrades/template_v2.yaml
2. Ensure metadata on existing templates is updated correctly during the upgrade process.
