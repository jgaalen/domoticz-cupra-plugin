# Cupra Plugin v2.0.0 - Installation & Update Guide

## Quick Fix for Parameter Error

If you're getting this error:
```
ValueError: invalid literal for int() with base 10: ''
```

This happens when the new parameters (Mode3, Mode4, Mode5) are empty strings. The updated plugin now handles this correctly.

## Installation Steps

### Option 1: Update Existing Installation

1. **Backup your current plugin** (just in case):
   ```bash
   cd /opt/domoticz/userdata/plugins/
   cp -r domoticz-cupra-plugin domoticz-cupra-plugin.backup
   ```

2. **Replace the plugin file**:
   ```bash
   cd domoticz-cupra-plugin
   # Replace plugin.py with the new version
   # Copy the new plugin.py file over the existing one
   ```

3. **Install/update dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Restart Domoticz**:
   ```bash
   sudo systemctl restart domoticz
   ```

### Option 2: Fresh Installation

1. **Remove old plugin** (if exists):
   ```bash
   cd /opt/domoticz/userdata/plugins/
   rm -rf domoticz-cupra-plugin
   ```

2. **Clone the updated plugin**:
   ```bash
   git clone https://github.com/jgaalen/domoticz-cupra-plugin.git
   cd domoticz-cupra-plugin
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Restart Domoticz**:
   ```bash
   sudo systemctl restart domoticz
   ```

## Configuration After Installation

1. **Go to Domoticz Hardware page**
2. **Find your Cupra Born hardware entry**
3. **Configure the new parameters**:
   - **Update Interval**: Set to `300` (5 minutes) or higher
   - **Max Retries**: Set to `3`
   - **Rate Limit Delay**: Set to `2`
   - **Debug Level**: Set to `Normal`

## Troubleshooting

### If you still get parameter errors:

1. **Check the hardware configuration**:
   - Make sure all new parameter fields have values
   - Don't leave any fields completely empty

2. **If fields are empty, set these values manually**:
   - Update Interval: `300`
   - Max Retries: `3`
   - Rate Limit Delay: `2`
   - Debug Level: `Normal`

3. **Check the logs**:
   ```bash
   tail -f /opt/domoticz/userdata/domoticz.log | grep "Cupra"
   ```

### Expected log messages after successful start:

```
Cupra Born Status Plugin v2.0.0 started
Update interval set to: 300 seconds
Max retries set to: 3
Rate limit delay set to: 2.0 seconds
Debug level set to: Normal
Worker thread started
Successfully connected to WeConnect API
```

### If you see parameter parsing errors:

The plugin will automatically use default values and log messages like:
```
Failed to parse update interval, using default 300 seconds
Failed to parse max retries, using default 3
```

This is normal and the plugin will continue to work with safe defaults.

## Testing the Fix

You can test the parameter parsing logic before installing:

```bash
cd /path/to/plugin/directory
python3 test_plugin.py
```

This will show you how the plugin handles various parameter scenarios.

## Key Improvements in v2.0.0

- ✅ **Fixed**: "thread seems to have ended unexpectedly" errors
- ✅ **Fixed**: Parameter parsing errors with empty strings
- ✅ **Added**: Rate limiting protection (HTTP 429 handling)
- ✅ **Added**: Exponential backoff retry logic
- ✅ **Added**: Connection monitoring and auto-recovery
- ✅ **Added**: Configurable debug levels
- ✅ **Added**: Worker thread architecture for stability

## Support

If you continue to experience issues:

1. Check the full error log in Domoticz
2. Verify your WeConnect credentials are still valid
3. Ensure your internet connection is stable
4. Try increasing the update interval to 600 seconds (10 minutes)

The plugin is now much more resilient and should handle temporary issues automatically.