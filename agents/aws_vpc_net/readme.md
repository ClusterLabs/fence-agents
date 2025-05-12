# Fence AWS VPC Network Agent Design Document

## Overview

The fence_aws_vpc_net agent is a network and power fencing agent for AWS VPC that operates by manipulating security groups. This document outlines the design and architecture of the agent.

## Class Diagram

```mermaid
classDiagram
    class FenceAWSVPCNet {
        -logger: Logger
        -conn: boto3.resource
        -options: dict
        +main()
        +define_new_opts()
        +fence_action()
    }

    class PowerManagement {
        +get_power_status()
        +set_power_status()
        +get_nodes_list()
        +get_self_power_status()
    }

    class InstanceOperations {
        +get_instance_id()
        +get_instance_details()
        +shutdown_instance()
        +check_sg_modifications()
    }

    class SecurityGroupOperations {
        +modify_security_groups()
        +restore_security_groups()
        +restore_security_groups_from_options()
    }

    class TagOperations {
        +set_lastfence_tag()
        +create_backup_tag()
    }

    class InputProcessing {
        +process_input()
        +check_input()
        +run_delay()
        +show_docs()
    }

    FenceAWSVPCNet --> PowerManagement
    FenceAWSVPCNet --> InputProcessing
    PowerManagement --> InstanceOperations
    PowerManagement --> SecurityGroupOperations
    SecurityGroupOperations --> TagOperations
    SecurityGroupOperations --> InstanceOperations
```

## Sequence Diagrams

### Fence Operation (Power Off)

```mermaid
sequenceDiagram
    participant Client
    participant FenceAgent
    participant AWS
    participant SecurityGroups
    participant Tags

    Client->>FenceAgent: Execute fence operation
    FenceAgent->>AWS: Validate AWS credentials
    AWS-->>FenceAgent: Credentials valid

    opt skip-race-check not set
        FenceAgent->>AWS: Get self instance ID
        AWS-->>FenceAgent: Instance ID
        FenceAgent->>FenceAgent: Check for self-fencing
    end

    FenceAgent->>AWS: Get instance details
    AWS-->>FenceAgent: Instance details

    alt Instance is running or ignore-instance-state set
        alt interface options present
            FenceAgent->>SecurityGroups: Modify security groups using interface options
            SecurityGroups-->>FenceAgent: Groups modified
        else
            FenceAgent->>SecurityGroups: Backup current security groups
            SecurityGroups-->>FenceAgent: Backup created

            alt ignore-tag-write-failure not set
                FenceAgent->>Tags: Create lastfence tag
                Tags-->>FenceAgent: Tag created
            end

            FenceAgent->>SecurityGroups: Modify security groups using --secg option
            SecurityGroups-->>FenceAgent: Groups modified
        end

        opt onfence-poweroff enabled
            FenceAgent->>AWS: Initiate shutdown
            AWS-->>FenceAgent: Shutdown initiated
        end

        FenceAgent-->>Client: Success
    else Instance not running and ignore-instance-state not set
        FenceAgent-->>Client: Fail - Instance not running
    end
```

### Unfence Operation (Power On)

```mermaid
sequenceDiagram
    participant Client
    participant FenceAgent
    participant AWS
    participant SecurityGroups
    participant Tags

    Client->>FenceAgent: Execute unfence operation
    FenceAgent->>AWS: Validate AWS credentials
    AWS-->>FenceAgent: Credentials valid

    alt interface options present
        FenceAgent->>SecurityGroups: Restore security groups using interface options
        SecurityGroups-->>FenceAgent: Groups restored
        FenceAgent-->>Client: Success
    else interface options not present
        alt unfence-ignore-restore not set
            FenceAgent->>Tags: Get lastfence tag
            Tags-->>FenceAgent: Lastfence tag

            FenceAgent->>Tags: Get backup tags
            Tags-->>FenceAgent: Backup tags

            alt Valid backup found
                FenceAgent->>SecurityGroups: Restore original security groups
                SecurityGroups-->>FenceAgent: Groups restored

                FenceAgent->>Tags: Cleanup backup tags
                Tags-->>FenceAgent: Tags cleaned

                FenceAgent-->>Client: Success
            else No valid backup
                FenceAgent-->>Client: Fail - No valid backup found
            end
        else unfence-ignore-restore set
            FenceAgent-->>Client: Success - Restore skipped
        end
    end
```

## Component Details

### 1. Main Controller (FenceAWSVPCNet)
- **Purpose**: Main entry point and orchestration
- **Key Responsibilities**:
  - Process command line options
  - Initialize AWS connection
  - Execute fence operations
  - Handle logging and errors
  - Manage self-fencing prevention
  - Support tag write failure handling

### 2. Instance Operations
- **Purpose**: Handle EC2 instance operations
- **Key Responsibilities**:
  - Get instance details and metadata
  - Handle instance power operations
  - Validate instance states
  - List and filter instances
  - Handle instance shutdown

### 3. Security Group Operations
- **Purpose**: Manage security group operations
- **Key Responsibilities**:
  - Modify security groups (remove or keep-only modes)
  - Handle chunked backup operations
  - Restore security groups from backups
  - Validate security group changes
  - Support partial success scenarios

### 4. Tag Operations
- **Purpose**: Manage AWS resource tagging
- **Key Responsibilities**:
  - Create and manage backup tags
  - Handle chunked tag data
  - Manage lastfence tags
  - Clean up tags after operations
  - Support tag write failure scenarios

### 5. Logging Manager
- **Purpose**: Handle logging configuration
- **Key Responsibilities**:
  - Configure application logging
  - Manage boto3 debug logging
  - Handle debug file output
  - Control log propagation

## Success and Failure Paths

### Success Paths

1. **Normal Fence Operation (Without ignore-tag-write-failure)**
```
Start
├── Validate AWS credentials
├── Check for self-fencing (if enabled)
├── Check instance is running
├── Backup security groups (with chunking)
│   ├── Create backup tags for each interface
│   └── Verify backup tag creation
├── Create lastfence tag
├── Modify security groups
│   ├── Remove specified groups
│   └── Verify modifications
├── [Optional] Shutdown instance
└── Success
```

2. **Fence Operation (With ignore-tag-write-failure)**
```
Start
├── Validate AWS credentials
├── Check for self-fencing (if enabled)
├── Check instance is running
├── Attempt backup tag creation
│   ├── Success: Create backup tags
│   └── Failure: Log warning and continue
├── Attempt lastfence tag creation
│   ├── Success: Create tag
│   └── Failure: Log warning and continue
├── Modify security groups
│   ├── Remove specified groups
│   ├── Verify modifications
│   └── Check all interfaces modified
│       ├── All modified: Success
│       └── Partial: Fail with modification error
├── [Optional] Shutdown instance
└── Success (if security groups modified)
```

3. **Normal Unfence Operation**
```
Start
├── Validate AWS credentials
├── [Skip if unfence-ignore-restore]
│   ├── Find lastfence tag
│   ├── Find backup tags
│   ├── Restore security groups
│   └── Clean up tags
└── Success
```

### Failure Paths

1. **Authentication Failures**
```
Start
├── Invalid AWS credentials
│   ├── Missing credentials
│   ├── Invalid access key
│   ├── Invalid secret key
│   └── Invalid region
└── Fail with auth error
```

2. **Instance State Failures**
```
Start
├── Instance not found
│   └── Fail with instance error
├── Instance not in required state
│   └── Fail with state error
└── Self-fencing detected
    └── Fail with self-fencing error
```

3. **Security Group Operation Failures (Without ignore-tag-write-failure)**
```
Start
├── Backup creation fails
│   ├── Tag size too large
│   ├── API error
│   └── Fail with backup error
├── Security group modification fails
│   ├── Permission denied
│   ├── Invalid group ID
│   ├── Rate limit exceeded
│   └── Fail with modification error
└── Restoration fails
    ├── Missing backup data
    ├── Invalid backup format
    ├── Modification error
    └── Fail with restore error
```

4. **Security Group Operation Failures (With ignore-tag-write-failure)**
```
Start
├── Backup creation fails
│   ├── Log warning
│   └── Continue to modifications
├── Security group modification attempt
│   ├── Success: All interfaces modified
│   │   └── Continue to completion
│   ├── Partial success
│   │   ├── Verify fencing state
│   │   │   ├── Sufficient interfaces modified
│   │   │   │   └── Continue to completion
│   │   │   └── Insufficient modifications
│   │   │       └── Fail with partial error
│   │   └── Log warning
│   └── Complete failure
│       └── Fail with modification error
├── [Optional] Shutdown attempt
│   ├── Success
│   │   └── Continue to completion
│   └── Failure
│       └── Log warning (non-fatal)
└── Final state determined by SG modifications
```

5. **Tag Operation Failures (Without ignore-tag-write-failure)**
```
Start
├── Tag creation fails
│   ├── Size limit exceeded
│   ├── API error
│   └── Fail with tag error
├── Tag retrieval fails
│   ├── Missing tags
│   ├── Invalid format
│   └── Fail with retrieval error
└── Tag cleanup fails
    └── Warning (non-fatal)
```

6. **Tag Operation Failures (With ignore-tag-write-failure)**
```
Start
├── Backup tag creation fails
│   ├── Log warning
│   └── Continue operation
├── Lastfence tag creation fails
│   ├── Log warning
│   └── Continue operation
├── Tag retrieval fails
│   ├── Check security group state
│   │   ├── Groups properly modified
│   │   │   └── Continue operation
│   │   └── Groups not modified
│   │       └── Fail with SG error
│   └── Log warning
└── Tag cleanup fails
    └── Warning (non-fatal)
```

## Error Handling

### Error Categories
1. **AWS API Errors**
   - ConnectionError
   - ClientError
   - EndpointConnectionError
   - NoRegionError
   - Tag size limitations
   - API rate limiting

2. **Validation Errors**
   - Invalid parameters
   - Missing required options
   - Invalid security group configurations
   - Malformed tag data

3. **State Errors**
   - Instance state conflicts
   - Security group conflicts
   - Self-fencing detection
   - Partial operation completion

### Error Recovery
- Automatic retries for transient AWS API errors
- Chunked tag handling for large security group lists
- Support for continuing operation despite tag failures
- Rollback of security group changes on partial failures
- Preservation of backup tags for manual recovery
- Detailed logging for troubleshooting

## Configuration Options

### Required Options
- `--plug`: AWS Instance ID
- AWS credentials (via options or environment)

### Optional Options
- `--region`: AWS region
- `--access-key`: AWS access key
- `--secret-key`: AWS secret key
- `--secg`: Security groups to remove/keep
- `--skip-race-check`: Skip self-fencing check
- `--invert-sg-removal`: Keep only specified security groups
- `--unfence-ignore-restore`: Skip restore on unfence
- `--onfence-poweroff`: Power off on fence
- `--ignore-tag-write-failure`: Continue despite tag failures
- `--filter`: Filter instances for list operation
- `--boto3_debug`: Enable boto3 debug logging

## Logging and Monitoring

### Log Levels
- ERROR: Operation failures and AWS API errors
- WARNING: Non-critical issues and tag operation failures
- INFO: Operation progress and success
- DEBUG: Detailed operation data and API responses

### Key Metrics
- Operation success/failure rates
- Tag operation success rates
- Security group modification status
- AWS API call latency
- Error frequency and types
- Tag size and chunking metrics

## Security Considerations

### Authentication
- AWS credential management
- IAM role requirements
- Access key security
- Instance metadata security

### Operation Safety
- Self-fencing prevention
- Backup verification
- Security group validation
- State verification
- Tag operation integrity
- Partial success handling

## Best Practices

1. **Operation Safety**
   - Always verify instance state
   - Use self-fencing prevention
   - Validate security group changes
   - Maintain accurate backups
   - Handle tag operation failures gracefully

2. **Error Handling**
   - Implement proper rollbacks
   - Use chunked tag operations
   - Maintain detailed logs
   - Preserve recovery data
   - Handle edge cases
   - Support partial success scenarios

3. **Performance**
   - Minimize API calls
   - Implement retries
   - Handle rate limiting
   - Optimize tag operations
   - Use efficient security group modifications

4. **Maintenance**
   - Regular backup cleanup
   - Log rotation
   - Configuration updates
   - Security updates
   - Monitor tag usage
   - Clean up orphaned tags

