#!/bin/bash

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Install pm2 if not installed
if ! command_exists pm2; then
  echo "PM2 not found. Installing via npm..."
  # Try global install first, likely requires sudo which we want to avoid if possible,
  # but often users have npm configured for global without sudo or we can use npx.
  # Let's try to use 'npx pm2' directly if we don't want to install,
  # OR install locally and add to path.
  
  # Easier approach for this env: try to install globally using user permissions or rely on npx
  npm install -g pm2 || echo "Global install failed, trying to run with npx..."
  
  if ! command_exists pm2; then
     echo "PM2 not in PATH. Usage via npx enabled."
     PM2_CMD="npx pm2"
  else
     PM2_CMD="pm2"
  fi
else
  PM2_CMD="pm2"
fi

echo "Starting services using $PM2_CMD..."

# Start the ecosystem
$PM2_CMD start ecosystem.config.js

# Save the process list to resurrect on reboot (optional, might require permissions)
$PM2_CMD save

echo "Services started! Use '$PM2_CMD status' to check status and '$PM2_CMD logs' to see logs."
