---
Title: "Linux System Administration"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-09-13
Processed: true
tags: ["source", "linux", "os"]
---

# Linux System Administration

## Bash Scripting Best Practices

### Script Template
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="/var/log/${0##*/}.log"

# Functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

# Main
main() {
    log "Starting $0"
    # ... your code here
    log "Done"
}

main "$@"
```

### String Operations
```bash
str="Hello, World!"
echo "${#str}"           # Length: 13
echo "${str:0:5}"        # Substring: Hello
echo "${str/World/Linux}" # Replace: Hello, Linux!
echo "${str,,}"          # Lowercase: hello, world!
echo "${str^^}"          # Uppercase: HELLO, WORLD!
```

### Array Operations
```bash
arr=(one two three four five)
echo "${#arr[@]}"        # Length: 5
echo "${arr[2]}"         # Element: three
echo "${arr[@]:1:3}"     # Slice: two three four
arr+=(six)               # Append
unset 'arr[1]'           # Remove element
```

### Conditional Expressions
```bash
# File tests
[[ -f "$file" ]]     # exists and regular file
[[ -d "$dir" ]]      # exists and directory
[[ -r "$file" ]]     # readable
[[ -w "$file" ]]     # writable
[[ -x "$file" ]]     # executable
[[ -s "$file" ]]     # exists and not empty

# String tests
[[ -z "$str" ]]      # empty
[[ -n "$str" ]]      # not empty
[[ "$a" == "$b" ]]   # equal
[[ "$a" != "$b" ]]   # not equal
[[ "$a" =~ regex ]]  # regex match

# Arithmetic
(( a > b ))
(( a >= b ))
(( a == 0 ))
```

## systemd Service Management

### Create Service
```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Application
After=network.target

[Service]
Type=simple
User=myapp
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/bin/start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Manage Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable myapp
sudo systemctl start myapp
sudo systemctl status myapp
sudo journalctl -u myapp -f  # Follow logs
```

## File Permissions and ACLs

### Basic Permissions
```bash
chmod 755 file.sh    # rwxr-xr-x
chmod 644 config.txt # rw-r--r--
chown user:group file
```

### ACLs
```bash
setfacl -m u:user:rwx file
setfacl -m g:group:rx file
getfacl file
```

## Network Troubleshooting

```bash
# Ports and connections
ss -tlnp                    # Listening ports
ss -s                       # Socket statistics
netstat -i                   # Network interfaces
ip addr show                 # IP addresses
ip route show                # Routing table

# DNS
dig example.com
nslookup example.com
host example.com

# Connectivity
ping -c 4 8.8.8.8
traceroute example.com
mtr example.com

# Packet capture
sudo tcpdump -i eth0 port 80 -w capture.pcap
```

## Package Management

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install package
sudo apt remove package
sudo apt autoremove

# RHEL/CentOS
sudo yum install package
sudo yum remove package
sudo yum update

# Arch
sudo pacman -S package
sudo pacman -R package
sudo pacman -Syu  # Full update
```

## Process Management

```bash
ps aux | grep process
top -bn1 | head -20
kill -TERM PID
kill -9 PID  # Force
pkill -f pattern
pgrep -f pattern
nice -n 10 command    # Lower priority
renice -n 5 -p PID   # Change priority
```
