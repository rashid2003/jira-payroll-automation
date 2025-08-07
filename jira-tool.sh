#!/usr/bin/env bash

# Set strict error handling
set -euo pipefail

# Function to check if terminal supports color
supports_color() {
    if command -v tput >/dev/null 2>&1; then
        [[ -t 1 ]] && [[ $(tput colors 2>/dev/null || echo 0) -ge 8 ]]
    else
        false
    fi
}

# Function to print success messages in green
success() {
    if supports_color; then
        echo "$(tput setaf 2)✅ SUCCESS: $1$(tput sgr0)"
    else
        echo "✅ SUCCESS: $1"
    fi
}

# Function to print error messages in red
error() {
    if supports_color; then
        echo "$(tput setaf 1)❌ ERROR: $1$(tput sgr0)" >&2
    else
        echo "❌ ERROR: $1" >&2
    fi
}

# Function to print info messages in blue
info() {
    if supports_color; then
        echo "$(tput setaf 4)ℹ️ INFO: $1$(tput sgr0)"
    else
        echo "ℹ️ INFO: $1"
    fi
}

# Function to load environment variables
load_environment() {
    local env_file=".env"
    
    # Check if .env file exists and source it
    if [[ -f "$env_file" ]]; then
        info "Loading environment variables from $env_file"
        # Source the .env file, ignoring comments and empty lines
        set -a  # automatically export all variables
        # shellcheck source=/dev/null
        source "$env_file"
        set +a  # turn off automatic export
    else
        info "No .env file found, using environment variables"
    fi
    
    # Skip environment validation in test mode
    if [[ "${JIRA_TEST_MODE:-}" == "true" ]]; then
        info "Running in test mode - skipping environment validation"
        return 0
    fi
    
    # Validate required environment variables
    local required_vars=("JIRA_BASE_URL" "JIRA_EMAIL" "JIRA_API_TOKEN")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var" >&2
        done
        echo "" >&2
        echo "Please either:" >&2
        echo "  1. Create a .env file with the required variables (see .env.example)" >&2
        echo "  2. Set the variables in your environment" >&2
        exit 1
    fi
    
    info "Environment variables loaded successfully"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."
    
    local required_commands=("curl" "jq" "sed" "grep")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! command_exists "$cmd"; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        error "Missing required commands:"
        for cmd in "${missing_commands[@]}"; do
            echo "  - $cmd" >&2
        done
        echo "" >&2
        echo "Please install the missing commands:" >&2
        echo "  - On macOS: brew install curl jq" >&2
        echo "  - On Ubuntu/Debian: apt-get install curl jq" >&2
        echo "  - On RHEL/CentOS: yum install curl jq" >&2
        echo "  Note: sed and grep are typically pre-installed on Unix systems" >&2
        exit 1
    fi
    
    info "All prerequisites satisfied"
}

# Utility function to print error and exit
die() {
    local message="$1"
    if supports_color; then
        echo "$(tput setaf 1)💀 FATAL: $message$(tput sgr0)" >&2
    else
        echo "💀 FATAL: $message" >&2
    fi
    exit 1
}

# Function to extract JIRA key from URL or return as-is if already a key
extract_key() {
    local input="$1"
    
    # If input matches JIRA key pattern (PROJ-123), return as-is
    if [[ "$input" =~ ^[A-Z]+[A-Z0-9]*-[0-9]+$ ]]; then
        echo "$input"
        return 0
    fi
    
    # Extract key from JIRA URL using regex
    # Matches patterns like: /browse/PROJ-123, /PROJ-123, etc.
    if [[ "$input" =~ ([A-Z]+[A-Z0-9]*-[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
        return 0
    fi
    
    # If no valid key found, return error
    die "Invalid JIRA key or URL format: $input"
}

# Generic JIRA API wrapper with curl, auth, and error handling
jira_api() {
    local method="${1:-GET}"
    local endpoint="$2"
    local data="${3:-}"
    local api_version="${4:-2}"  # Default to v2 for backward compatibility
    
    # Test mode - just print the curl command that would be executed
    if [[ "${JIRA_TEST_MODE:-}" == "true" ]]; then
        echo "[TEST MODE] Would execute curl command:" >&2
        echo "Method: $method" >&2
        echo "Endpoint: $endpoint" >&2
        echo "Data: ${data:-"(none)"}" >&2
        echo "API Version: $api_version" >&2
        echo "Full URL: ${JIRA_BASE_URL:-"https://example.atlassian.net"}/rest/api/${api_version}/${endpoint}" >&2
        echo "" >&2
        
        # Return different mock responses based on endpoint
        if [[ "$endpoint" =~ /transitions$ ]]; then
            # Mock transitions endpoint
            cat <<'EOF'
{
  "transitions": [
    {
      "id": "21",
      "name": "Done",
      "to": {
        "name": "Done",
        "id": "3"
      }
    },
    {
      "id": "11",
      "name": "In Progress",
      "to": {
        "name": "In Progress",
        "id": "2"
      }
    },
    {
      "id": "31",
      "name": "To Do",
      "to": {
        "name": "To Do",
        "id": "1"
      }
    }
  ]
}
EOF
        elif [[ "$method" == "POST" && "$endpoint" =~ /transitions$ ]]; then
            # Mock successful transition response (empty response is typical)
            echo ""
        elif [[ "$method" == "POST" && "$endpoint" =~ /comment$ ]]; then
            # Mock comment creation response
            cat <<'EOF'
{
  "id": "10123",
  "created": "2024-01-16T15:30:45.123Z",
  "updated": "2024-01-16T15:30:45.123Z",
  "author": {
    "displayName": "Test User"
  },
  "body": {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "paragraph",
        "content": [
          {
            "type": "text",
            "text": "This is a test comment"
          }
        ]
      }
    ]
  }
}
EOF
        elif [[ "$method" == "POST" && "$endpoint" =~ /worklog$ ]]; then
            # Mock worklog creation response with remaining estimate
            cat <<'EOF'
{
  "id": "10456",
  "created": "2024-01-16T16:15:30.456Z",
  "updated": "2024-01-16T16:15:30.456Z",
  "author": {
    "displayName": "Test User",
    "emailAddress": "test@example.com"
  },
  "timeSpent": "2h 30m",
  "timeSpentSeconds": 9000,
  "comment": {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "paragraph",
        "content": [
          {
            "type": "text",
            "text": "Development work completed"
          }
        ]
      }
    ]
  },
  "issue": {
    "fields": {
      "timeestimate": 14400
    }
  }
}
EOF
        else
            # Default mock issue response
            cat <<'EOF'
{
  "key": "PROJ-123",
  "fields": {
    "summary": "Test Issue Summary",
    "status": {"name": "In Progress"},
    "assignee": {"displayName": "John Doe"},
    "reporter": {"displayName": "Jane Smith"},
    "issuetype": {"name": "Story"},
    "priority": {"name": "High"},
    "created": "2024-01-15T10:30:00.000Z",
    "updated": "2024-01-16T14:45:00.000Z",
    "description": "This is a test issue description that demonstrates how the tool formats and displays JIRA issue information.",
    "customfield_10016": 5
  },
  "renderedFields": {
    "description": "This is a test issue description that demonstrates how the tool formats and displays JIRA issue information."
  }
}
EOF
        fi
        return 0
    fi
    
    # Validate required environment variables are available
    if [[ -z "${JIRA_BASE_URL:-}" ]] || [[ -z "${JIRA_EMAIL:-}" ]] || [[ -z "${JIRA_API_TOKEN:-}" ]]; then
        die "JIRA environment variables not set. Please run init first."
    fi
    
    # Prepare curl command with common options
    # Note: removing --fail to handle HTTP status codes manually
    local curl_cmd=(
        curl
        --silent
        --show-error
        --location
        --max-time 30
        --write-out "\n%{http_code}"
        --header "Accept: application/json"
        --header "Content-Type: application/json"
        --user "${JIRA_EMAIL}:${JIRA_API_TOKEN}"
        --request "$method"
    )
    
    # Add data if provided (for POST/PUT requests)
    if [[ -n "$data" ]]; then
        curl_cmd+=(--data "$data")
    fi
    
    # Add the full URL
    curl_cmd+=("${JIRA_BASE_URL}/rest/api/${api_version}/${endpoint}")
    
    # Execute curl and capture response with HTTP status code
    local curl_output
    local exit_code
    
    if ! curl_output=$("${curl_cmd[@]}" 2>&1); then
        exit_code=$?
        error "JIRA API request failed (curl exit code: $exit_code)"
        die "Network error or timeout occurred. Check your JIRA_BASE_URL and internet connection."
    fi
    
    # Extract HTTP status code from the last line
    local http_status=$(echo "$curl_output" | tail -n1)
    local response_body=$(echo "$curl_output" | sed '$d')
    
    # Check HTTP status code
    if [[ "$http_status" -ge 400 ]]; then
        error "JIRA API returned HTTP $http_status"
        
        # Try to extract error message from JSON response
        local error_message=""
        if command_exists "jq" && [[ -n "$response_body" ]]; then
            # Try different error message formats used by JIRA
            error_message=$(echo "$response_body" | jq -r '.errorMessages[]? // .message? // .errors? | tostring' 2>/dev/null | head -1)
            if [[ "$error_message" == "null" || -z "$error_message" ]]; then
                # Try alternative error format
                error_message=$(echo "$response_body" | jq -r '.error? // .detail? // empty' 2>/dev/null)
            fi
        fi
        
        if [[ -n "$error_message" && "$error_message" != "null" ]]; then
            die "API Error: $error_message"
        else
            # Fallback error message based on common HTTP status codes
            case "$http_status" in
                400) die "Bad Request: Invalid request format or parameters" ;;
                401) die "Unauthorized: Invalid credentials or API token" ;;
                403) die "Forbidden: Insufficient permissions for this operation" ;;
                404) die "Not Found: Issue or resource does not exist" ;;
                429) die "Rate Limited: Too many requests, please try again later" ;;
                500) die "Internal Server Error: JIRA server error" ;;
                503) die "Service Unavailable: JIRA service temporarily unavailable" ;;
                *) die "HTTP $http_status: Request failed" ;;
            esac
        fi
    fi
    
    echo "$response_body"
}

# Pretty print JSON with jq, colorized and minimal
pretty_print_json() {
    if command_exists "jq"; then
        # Use jq with color output and compact formatting
        jq --color-output --compact-output "."
    else
        # Fallback if jq is not available
        cat
    fi
}

# Function to trim text to specified length
trim_text() {
    local text="$1"
    local max_length="${2:-200}"
    
    if [[ ${#text} -gt $max_length ]]; then
        echo "${text:0:$max_length}..."
    else
        echo "$text"
    fi
}

# Function to extract field value from JSON using jq
get_field() {
    local json="$1"
    local field_path="$2"
    local default_value="${3:-N/A}"
    
    if command_exists "jq"; then
        echo "$json" | jq -r "$field_path // \"$default_value\""
    else
        echo "$default_value"
    fi
}

# Function to format and display JIRA issue information
format_issue() {
    local json="$1"
    
    echo "📋 JIRA Issue Details"
    echo "==================="
    echo ""
    
    # Extract and display key fields
    local key=$(get_field "$json" ".key")
    local summary=$(get_field "$json" ".fields.summary")
    local status=$(get_field "$json" ".fields.status.name")
    local assignee=$(get_field "$json" ".fields.assignee.displayName")
    local reporter=$(get_field "$json" ".fields.reporter.displayName")
    local story_points=$(get_field "$json" ".fields.customfield_10016")
    local issue_type=$(get_field "$json" ".fields.issuetype.name")
    local priority=$(get_field "$json" ".fields.priority.name")
    local created=$(get_field "$json" ".fields.created")
    local updated=$(get_field "$json" ".fields.updated")
    
    # Get description from rendered fields if available, otherwise from regular fields
    local description=$(get_field "$json" ".renderedFields.description // .fields.description")
    
    # Format and display the information
    echo "🔑 Key:          $key"
    echo "📝 Summary:      $summary"
    echo "📊 Status:       $status"
    echo "📋 Type:         $issue_type"
    echo "⚡ Priority:     $priority"
    echo "👤 Assignee:     $assignee"
    echo "📧 Reporter:     $reporter"
    
    # Only show story points if it's not null/N/A
    if [[ "$story_points" != "N/A" && "$story_points" != "null" ]]; then
        echo "📈 Story Points: $story_points"
    fi
    
    echo "📅 Created:      $created"
    echo "🔄 Updated:      $updated"
    echo ""
    
    # Display trimmed description
    if [[ "$description" != "N/A" && "$description" != "null" ]]; then
        echo "📄 Description:"
        echo "---------------"
        local trimmed_desc=$(trim_text "$description" 500)
        echo "$trimmed_desc"
        echo ""
    fi
}

# Function to get available transitions for an issue
get_transitions() {
    local issue_key="$1"
    local response
    response=$(jira_api "GET" "issue/${issue_key}/transitions" "" "3")
    echo "$response"
}

# Function to perform a transition
perform_transition() {
    local issue_key="$1"
    local transition_id="$2"
    local data="{\"transition\":{\"id\":\"${transition_id}\"}}"
    local response
    response=$(jira_api "POST" "issue/${issue_key}/transitions" "$data" "3")
    echo "$response"
}

# Function to add a comment to an issue
add_comment() {
    local issue_key="$1"
    local comment_text="$2"
    
    # Create JSON payload for the comment
    # Using simple plain text format as requested
    local data
    data=$(jq -n \
        --arg body "$comment_text" \
        '{
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": $body
                            }
                        ]
                    }
                ]
            }
        }')
    
    local response
    response=$(jira_api "POST" "issue/${issue_key}/comment" "$data" "3")
    echo "$response"
}

# Function to parse human-readable time duration to seconds (following Jira rules)
# Supports formats like: "2h 30m", "1h", "45m", "3d 2h 15m", "1w 2d"
# Jira time units: w (weeks=5 days), d (days=8 hours), h (hours=60 minutes), m (minutes=60 seconds)
parse_time() {
    local duration="$1"
    local total_seconds=0
    
    # Remove extra whitespace and convert to lowercase
    duration=$(echo "$duration" | tr '[:upper:]' '[:lower:]' | sed 's/[[:space:]]*//g')
    
    # Define Jira time conversion factors (in seconds) using traditional approach for compatibility
    local w_seconds=144000  # 1 week = 5 days * 8 hours * 60 minutes * 60 seconds
    local d_seconds=28800   # 1 day = 8 hours * 60 minutes * 60 seconds
    local h_seconds=3600    # 1 hour = 60 minutes * 60 seconds
    local m_seconds=60      # 1 minute = 60 seconds
    
    # Extract time components using regex
    # Match patterns like: 2w, 3d, 4h, 30m
    while [[ $duration =~ ([0-9]+)([wdhm]) ]]; do
        local value="${BASH_REMATCH[1]}"
        local unit="${BASH_REMATCH[2]}"
        
        # Convert to seconds and add to total based on unit
        local unit_seconds=0
        case "$unit" in
            w) unit_seconds=$w_seconds ;;
            d) unit_seconds=$d_seconds ;;
            h) unit_seconds=$h_seconds ;;
            m) unit_seconds=$m_seconds ;;
            *) die "Invalid time unit: $unit. Supported units: w (weeks), d (days), h (hours), m (minutes)" ;;
        esac
        
        total_seconds=$((total_seconds + value * unit_seconds))
        
        # Remove the matched part from the duration string
        duration=${duration/${BASH_REMATCH[0]}/}
    done
    
    # Check if there are any unprocessed characters (invalid input)
    if [[ -n "$duration" ]]; then
        die "Invalid time format: '$1'. Use format like '2h 30m', '1d 4h', '3w 2d 5h 15m'"
    fi
    
    if [[ $total_seconds -eq 0 ]]; then
        die "Invalid or empty time duration: '$1'"
    fi
    
    echo "$total_seconds"
}

# Function to add worklog to an issue
add_worklog() {
    local issue_key="$1"
    local time_spent_seconds="$2"
    local comment_text="$3"
    
    # Create JSON payload for the worklog
    local data
    data=$(jq -n \
        --arg timeSpentSeconds "$time_spent_seconds" \
        --arg comment "$comment_text" \
        '{
            "timeSpentSeconds": ($timeSpentSeconds | tonumber),
            "comment": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": $comment
                            }
                        ]
                    }
                ]
            }
        }')
    
    local response
    response=$(jira_api "POST" "issue/${issue_key}/worklog" "$data" "3")
    echo "$response"
}

# Function to find transition ID by status name (case-insensitive)
find_transition_by_status() {
    local transitions_json="$1"
    local desired_status="$2"
    local matches=()
    local transition_names=()
    
    # Extract all transitions and find matches
    while IFS= read -r line; do
        local id=$(echo "$line" | jq -r '.id')
        local name=$(echo "$line" | jq -r '.to.name')
        transition_names+=("$name")
        
        # Case-insensitive comparison using tr
        local name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local desired_lower=$(echo "$desired_status" | tr '[:upper:]' '[:lower:]')
        if [[ "$name_lower" == "$desired_lower" ]]; then
            matches+=("$id:$name")
        fi
    done < <(echo "$transitions_json" | jq -c '.transitions[]')
    
    if [[ ${#matches[@]} -eq 0 ]]; then
        echo "ERROR:No transitions found for status '${desired_status}'"
        echo "Available transitions:" >&2
        printf "  - %s\n" "${transition_names[@]}" >&2
        return 1
    elif [[ ${#matches[@]} -eq 1 ]]; then
        # Single match found
        local match="${matches[0]}"
        echo "${match%:*}" # Return just the ID
        return 0
    else
        # Multiple matches - should be rare but handle it
        echo "ERROR:Multiple transitions found for status '${desired_status}'"
        for match in "${matches[@]}"; do
            echo "  - ${match#*:} (ID: ${match%:*})" >&2
        done
        return 1
    fi
}

# Status subcommand - change issue status via transitions
cmd_status() {
    local issue_key=""
    local desired_status=""
    local list_flag=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --list)
                list_flag=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 status [--list] <issue-key-or-url> [<new-status>]"
                echo ""
                echo "Options:"
                echo "  --list    List available transitions for the issue"
                echo "  --help    Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 status PROJ-123                    # List available transitions"
                echo "  $0 status PROJ-123 'In Progress'      # Transition to 'In Progress'"
                echo "  $0 status PROJ-123 done               # Transition to 'Done' (case-insensitive)"
                echo "  $0 status --list PROJ-123             # List available transitions"
                return 0
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                if [[ -z "$issue_key" ]]; then
                    issue_key="$1"
                elif [[ -z "$desired_status" ]]; then
                    desired_status="$1"
                else
                    die "Too many arguments. Use --help for usage information."
                fi
                shift
                ;;
        esac
    done
    
    # Validate that issue key was provided
    if [[ -z "$issue_key" ]]; then
        die "Issue key or URL is required. Use --help for usage information."
    fi
    
    # Extract clean JIRA key from input
    local key
    key=$(extract_key "$issue_key")
    
    info "Getting transitions for issue: $key"
    
    # Get available transitions
    local transitions_response
    transitions_response=$(get_transitions "$key")
    
    # If --list flag or no desired status, show available transitions
    if [[ "$list_flag" == "true" || -z "$desired_status" ]]; then
        echo "📋 Available Transitions for $key"
        echo "================================"
        echo ""
        
        # Get current status first
        local issue_response
        issue_response=$(jira_api "GET" "issue/${key}" "" "3")
        local current_status=$(get_field "$issue_response" ".fields.status.name")
        echo "🔄 Current Status: $current_status"
        echo ""
        
        if echo "$transitions_response" | jq -e '.transitions | length > 0' >/dev/null; then
            echo "➡️ Available Transitions:"
            echo "$transitions_response" | jq -r '.transitions[] | "  - \(.to.name) (ID: \(.id))"'
        else
            echo "❌ No transitions available for this issue"
        fi
        echo ""
        return 0
    fi
    
    # Find the transition ID for the desired status
    local transition_id
    if ! transition_id=$(find_transition_by_status "$transitions_response" "$desired_status"); then
        exit 1
    fi
    
    info "Transitioning $key to '$desired_status' (transition ID: $transition_id)"
    
    # Perform the transition
    local transition_response
    if ! transition_response=$(perform_transition "$key" "$transition_id"); then
        die "Failed to transition issue $key"
    fi
    
    # Get updated issue to confirm the transition
    info "Verifying transition..."
    local updated_issue
    updated_issue=$(jira_api "GET" "issue/${key}" "" "3")
    local new_status=$(get_field "$updated_issue" ".fields.status.name")
    
    success "Issue $key transitioned to: $new_status"
    echo ""
    
    # Show brief issue summary with new status
    local summary=$(get_field "$updated_issue" ".fields.summary")
    echo "📋 Issue Summary:"
    echo "🔑 Key:     $key"
    echo "📝 Title:   $summary"
    echo "📊 Status:  $new_status"
}

# Comment subcommand - add comment to JIRA issue
cmd_comment() {
    local issue_key=""
    local comment_text=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                echo "Usage: $0 comment <issue-key-or-url> <comment-text>"
                echo ""
                echo "Options:"
                echo "  --help    Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 comment PROJ-123 'This is a comment'"
                echo "  $0 comment https://company.atlassian.net/browse/PROJ-123 'Bug fix applied'"
                echo "  $0 comment PROJ-123 'Multi word comment with spaces'"
                return 0
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                if [[ -z "$issue_key" ]]; then
                    issue_key="$1"
                elif [[ -z "$comment_text" ]]; then
                    comment_text="$1"
                else
                    # Concatenate additional arguments to comment text
                    comment_text="$comment_text $1"
                fi
                shift
                ;;
        esac
    done
    
    # Validate that both issue key and comment text were provided
    if [[ -z "$issue_key" ]]; then
        die "Issue key or URL is required. Use --help for usage information."
    fi
    
    if [[ -z "$comment_text" ]]; then
        die "Comment text is required. Use --help for usage information."
    fi
    
    # Extract clean JIRA key from input
    local key
    key=$(extract_key "$issue_key")
    
    info "Adding comment to issue: $key"
    
    # Add the comment
    local response
    response=$(add_comment "$key" "$comment_text")
    
    # Extract comment ID and created date from response
    local comment_id=$(get_field "$response" ".id")
    local created_date=$(get_field "$response" ".created")
    local author=$(get_field "$response" ".author.displayName")
    
    success "Comment added successfully!"
    echo ""
    echo "💬 Comment Details:"
    echo "🔑 Comment ID:  $comment_id"
    echo "📅 Created:     $created_date"
    echo "👤 Author:      $author"
    echo "📝 Text:        $comment_text"
    echo ""
}

# Time subcommand - log work time to JIRA issue
cmd_time() {
    local issue_key=""
    local duration=""
    local description=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                echo "Usage: $0 time <issue-key-or-url> <duration> <description>"
                echo ""
                echo "Duration format follows Jira time tracking conventions:"
                echo "  w = weeks (5 working days)"
                echo "  d = days (8 working hours)"
                echo "  h = hours (60 minutes)"
                echo "  m = minutes (60 seconds)"
                echo ""
                echo "Options:"
                echo "  --help    Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 time PROJ-123 '2h 30m' 'Development work completed'"
                echo "  $0 time PROJ-123 '1h' 'Bug fix'"
                echo "  $0 time PROJ-123 '45m' 'Code review'"
                echo "  $0 time PROJ-123 '1d 2h' 'Feature implementation'"
                echo "  $0 time PROJ-123 '1w 2d 4h 30m' 'Project milestone completed'"
                return 0
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                if [[ -z "$issue_key" ]]; then
                    issue_key="$1"
                elif [[ -z "$duration" ]]; then
                    duration="$1"
                elif [[ -z "$description" ]]; then
                    description="$1"
                else
                    # Concatenate additional arguments to description
                    description="$description $1"
                fi
                shift
                ;;
        esac
    done
    
    # Validate that all required arguments were provided
    if [[ -z "$issue_key" ]]; then
        die "Issue key or URL is required. Use --help for usage information."
    fi
    
    if [[ -z "$duration" ]]; then
        die "Duration is required. Use --help for usage information."
    fi
    
    if [[ -z "$description" ]]; then
        die "Description is required. Use --help for usage information."
    fi
    
    # Extract clean JIRA key from input
    local key
    key=$(extract_key "$issue_key")
    
    info "Parsing duration: $duration"
    
    # Parse duration to seconds using helper function
    local time_spent_seconds
    time_spent_seconds=$(parse_time "$duration")
    
    info "Adding worklog to issue: $key (${time_spent_seconds}s)"
    
    # Add the worklog
    local response
    response=$(add_worklog "$key" "$time_spent_seconds" "$description")
    
    # Extract worklog details from response
    local worklog_id=$(get_field "$response" ".id")
    local created_date=$(get_field "$response" ".created")
    local author=$(get_field "$response" ".author.displayName")
    local time_spent=$(get_field "$response" ".timeSpent")
    
    # Get remaining estimate from the response (if available)
    local remaining_estimate_seconds=$(get_field "$response" ".issue.fields.timeestimate")
    local remaining_estimate="N/A"
    
    if [[ "$remaining_estimate_seconds" != "N/A" && "$remaining_estimate_seconds" != "null" && "$remaining_estimate_seconds" -gt 0 ]]; then
        # Convert seconds to human-readable format
        local hours=$((remaining_estimate_seconds / 3600))
        local minutes=$(( (remaining_estimate_seconds % 3600) / 60 ))
        
        if [[ $hours -gt 0 && $minutes -gt 0 ]]; then
            remaining_estimate="${hours}h ${minutes}m"
        elif [[ $hours -gt 0 ]]; then
            remaining_estimate="${hours}h"
        elif [[ $minutes -gt 0 ]]; then
            remaining_estimate="${minutes}m"
        else
            remaining_estimate="0m"
        fi
    fi
    
    success "Worklog added successfully!"
    echo ""
    echo "⏰ Worklog Details:"
    echo "🔑 Worklog ID:      $worklog_id"
    echo "📅 Created:         $created_date"
    echo "👤 Author:          $author"
    echo "⏱️ Time Spent:       $duration (${time_spent_seconds}s)"
    echo "📝 Description:     $description"
    
    if [[ "$remaining_estimate" != "N/A" ]]; then
        echo "⏳ Remaining Est.:   $remaining_estimate"
    fi
    
    echo ""
    
    # Show brief issue summary
    info "Fetching updated issue details..."
    local issue_response
    issue_response=$(jira_api "GET" "issue/${key}" "" "3")
    local summary=$(get_field "$issue_response" ".fields.summary")
    local status=$(get_field "$issue_response" ".fields.status.name")
    
    echo "📋 Issue Summary:"
    echo "🔑 Key:     $key"
    echo "📝 Title:   $summary"
    echo "📊 Status:  $status"
}

# Get subcommand - fetch and display JIRA issue
cmd_get() {
    local raw_flag=false
    local issue_key=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --raw)
                raw_flag=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 get [--raw] <issue-key-or-url>"
                echo ""
                echo "Options:"
                echo "  --raw     Dump full JSON response"
                echo "  --help    Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 get PROJ-123"
                echo "  $0 get https://company.atlassian.net/browse/PROJ-123"
                echo "  $0 get --raw PROJ-123"
                return 0
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                if [[ -z "$issue_key" ]]; then
                    issue_key="$1"
                else
                    die "Too many arguments. Expected one issue key or URL."
                fi
                shift
                ;;
        esac
    done
    
    # Validate that issue key was provided
    if [[ -z "$issue_key" ]]; then
        die "Issue key or URL is required. Use --help for usage information."
    fi
    
    # Extract clean JIRA key from input
    local key
    key=$(extract_key "$issue_key")
    
    info "Fetching issue: $key"
    
    # Make API call to get issue with rendered fields
    local response
    response=$(jira_api "GET" "issue/${key}?expand=renderedFields" "" "3")
    
    if [[ "$raw_flag" == "true" ]]; then
        # Display raw JSON
        echo "$response" | pretty_print_json
    else
        # Display formatted information
        format_issue "$response"
    fi
}

# Show help information
show_help() {
    echo "JIRA CLI Tool"
    echo "=============="
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  get <issue-key>      Fetch and display JIRA issue details"
    echo "  status <issue-key>   Change issue status via transitions"
    echo "  comment <issue-key>  Add a comment to a JIRA issue"
    echo "  time <issue-key>     Log work time to a JIRA issue"
    echo "  help                 Show this help message"
    echo ""
    echo "Global Options:"
    echo "  --help, -h           Show help for command"
    echo ""
    echo "Examples:"
    echo "  $0 get PROJ-123"
    echo "  $0 get --raw PROJ-456"
    echo "  $0 get https://company.atlassian.net/browse/PROJ-123"
    echo "  $0 status PROJ-123"
    echo "  $0 status PROJ-123 'In Progress'"
    echo "  $0 status PROJ-123 done"
    echo "  $0 comment PROJ-123 'This is a comment'"
    echo "  $0 time PROJ-123 '2h 30m' 'Development work completed'"
    echo ""
    echo "Environment Variables Required:"
    echo "  JIRA_BASE_URL      Your JIRA instance URL (e.g., https://company.atlassian.net)"
    echo "  JIRA_EMAIL         Your email address"
    echo "  JIRA_API_TOKEN     Your API token from JIRA"
    echo ""
}

# Show usage information for invalid commands or arguments
show_usage() {
    echo "Usage: $0 {get|status|comment|time|help} [options]"
    echo ""
    echo "Commands:"
    echo "  get      - Fetch and display JIRA issue details"
    echo "  status   - Change issue status via transitions"
    echo "  comment  - Add a comment to a JIRA issue"
    echo "  time     - Log work time to a JIRA issue"
    echo "  help     - Show detailed help information"
    echo ""
    echo "Use '$0 <command> --help' for detailed command usage."
    echo "Use '$0 help' for comprehensive documentation."
}

# Main initialization function
init() {
    info "Initializing JIRA Tool..."
    
    # Load environment variables
    load_environment
    
    # Check prerequisites
    check_prerequisites
    
    success "JIRA Tool initialized successfully"
}

# Main function to handle command dispatch using case statement on $1
main() {
    # If no arguments provided, show usage
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi
    
    # Parse command using case statement on $1
    case "$1" in
        get)
            shift
            # Check for help flag before initialization
            if [[ $# -gt 0 && ("$1" == "--help" || "$1" == "-h") ]]; then
                cmd_get "$@"
                exit 0
            fi
            init
            cmd_get "$@"
            ;;
        status)
            shift
            # Check for help flag before initialization
            if [[ $# -gt 0 && ("$1" == "--help" || "$1" == "-h") ]]; then
                cmd_status "$@"
                exit 0
            fi
            init
            cmd_status "$@"
            ;;
        comment)
            shift
            # Check for help flag before initialization
            if [[ $# -gt 0 && ("$1" == "--help" || "$1" == "-h") ]]; then
                cmd_comment "$@"
                exit 0
            fi
            init
            cmd_comment "$@"
            ;;
        time)
            shift
            # Check for help flag before initialization
            if [[ $# -gt 0 && ("$1" == "--help" || "$1" == "-h") ]]; then
                cmd_time "$@"
                exit 0
            fi
            init
            cmd_time "$@"
            ;;
        help|--help|-h)
            show_help
            exit 0
            ;;
        *)
            # Invalid command - show error and usage
            error "Invalid command: '$1'"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
