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
        +process_input()
        +check_input()
    }

    class AWSConnection {
        -region: str
        -access_key: str
        -secret_key: str
        +establish_connection()
        +validate_credentials()
    }

    class SecurityGroupManager {
        +modify_security_groups()
        +create_backup_tag()
        +restore_security_groups()
        -validate_sg_changes()
    }

    class InstanceManager {
        +get_instance_details()
        +shutdown_instance()
        +get_power_status()
        +set_power_status()
        -validate_instance_state()
    }

    class TagManager {
        +set_lastfence_tag()
        +get_backup_tags()
        +cleanup_tags()
        -validate_tag_operations()
    }

    FenceAWSVPCNet --> AWSConnection
    FenceAWSVPCNet --> SecurityGroupManager
    FenceAWSVPCNet --> InstanceManager
    SecurityGroupManager --> TagManager
    InstanceManager --> TagManager

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
    
    FenceAgent->>AWS: Get instance details
    AWS-->>FenceAgent: Instance details
    
    alt Instance is running
        FenceAgent->>SecurityGroups: Backup current security groups
        SecurityGroups-->>FenceAgent: Backup created
        
        FenceAgent->>Tags: Create lastfence tag
        Tags-->>FenceAgent: Tag created
        
        FenceAgent->>SecurityGroups: Modify security groups
        SecurityGroups-->>FenceAgent: Groups modified
        
        opt onfence-poweroff enabled
            FenceAgent->>AWS: Initiate shutdown
            AWS-->>FenceAgent: Shutdown initiated
        end
        
        FenceAgent-->>Client: Success
    else Instance not running
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
```

## Component Details

### 1. Main Controller (FenceAWSVPCNet)
- **Purpose**: Main entry point and orchestration
- **Key Responsibilities**:
  - Process command line options
  - Initialize AWS connection
  - Execute fence operations
  - Handle logging and errors

### 2. AWS Connection Manager
- **Purpose**: Handle AWS connectivity
- **Key Responsibilities**:
  - Establish and maintain AWS connection
  - Handle credentials and regions
  - Manage API retries and timeouts

### 3. Security Group Manager
- **Purpose**: Manage security group operations
- **Key Responsibilities**:
  - Modify security groups
  - Create backups of security group configurations
  - Restore security groups from backups
  - Validate security group changes

### 4. Instance Manager
- **Purpose**: Handle EC2 instance operations
- **Key Responsibilities**:
  - Get instance details and status
  - Handle instance power operations
  - Validate instance states
  - Manage self-fencing prevention

### 5. Tag Manager
- **Purpose**: Manage AWS resource tagging
- **Key Responsibilities**:
  - Create and manage backup tags
  - Handle lastfence tags
  - Clean up tags after operations
  - Validate tag operations

## Success and Failure Paths

### Success Paths

1. **Normal Fence Operation**
```
Start
├── Validate AWS credentials
├── Check instance is running
├── Backup security groups
├── Create lastfence tag
├── Modify security groups
├── [Optional] Shutdown instance
└── Success
```

2. **Normal Unfence Operation**
```
Start
├── Validate AWS credentials
├── Find lastfence tag
├── Find backup tags
├── Restore security groups
├── Clean up tags
└── Success
```

### Failure Paths

1. **Authentication Failures**
```
Start
├── Invalid AWS credentials
└── Fail with auth error
```

2. **Instance State Failures**
```
Start
├── Instance not in required state
└── Fail with state error
```

3. **Security Group Operation Failures**
```
Start
├── Backup creation fails
│   └── Fail with backup error
├── Security group modification fails
│   └── Fail with modification error
└── Restoration fails
    └── Fail with restore error
```

4. **Tag Operation Failures**
```
Start
├── Tag creation fails
│   └── Fail with tag error
├── Tag retrieval fails
│   └── Fail with retrieval error
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

2. **Validation Errors**
   - Invalid parameters
   - Missing required options
   - Invalid security group configurations

3. **State Errors**
   - Instance state conflicts
   - Security group conflicts
   - Self-fencing detection

### Error Recovery
- Automatic retries for transient AWS API errors
- Rollback of security group changes on partial failures
- Preservation of backup tags for manual recovery
- Detailed logging for troubleshooting

## Configuration Options

### Required Options
- `--plug`: AWS Instance ID
- AWS credentials (via options or environment)

### Optional Options
- `--region`: AWS region
- `--secg`: Security groups to remove
- `--skip-race-check`: Skip self-fencing check
- `--invert-sg-removal`: Invert security group removal
- `--unfence-ignore-restore`: Skip restore on unfence
- `--onfence-poweroff`: Power off on fence

## Logging and Monitoring

### Log Levels
- ERROR: Operation failures
- WARNING: Non-critical issues
- INFO: Operation progress
- DEBUG: Detailed operation data

### Key Metrics
- Operation success/failure rates
- Operation duration
- AWS API call latency
- Error frequency and types

## Security Considerations

### Authentication
- AWS credential management
- IAM role requirements
- Access key security

### Operation Safety
- Self-fencing prevention
- Backup verification
- Security group validation
- State verification

## Best Practices

1. **Operation Safety**
   - Always verify instance state
   - Validate security group changes
   - Maintain accurate backups
   - Prevent self-fencing

2. **Error Handling**
   - Implement proper rollbacks
   - Maintain detailed logs
   - Preserve recovery data
   - Handle edge cases

3. **Performance**
   - Minimize API calls
   - Implement retries
   - Handle rate limiting
   - Optimize operations

4. **Maintenance**
   - Regular backup cleanup
   - Log rotation
   - Configuration updates
   - Security updates
