# Streamlit Cloud Redeploy Instructions

## Issue
The app is showing the old error: `'FunctionTool' object is not callable`

## Solution
The fix has been committed and pushed to the repository. Streamlit Cloud needs to redeploy to pick up the changes.

## Steps to Redeploy

### Option 1: Wait for Automatic Redeploy
Streamlit Cloud should automatically detect the new commit and redeploy. This usually takes 1-2 minutes.

### Option 2: Manual Redeploy
1. Go to [Streamlit Cloud Dashboard](https://share.streamlit.io)
2. Navigate to your app: **zillow-agent-demo**
3. Click on the **"⋮"** (three dots) menu
4. Select **"Reboot app"** or **"Redeploy"**
5. Wait for the deployment to complete

### Option 3: Force Redeploy via Git
If automatic redeploy doesn't work, you can force it by making a small change:

```bash
# Make a trivial change to trigger redeploy
echo "# Redeploy trigger" >> src/ui/streamlit_app.py
git add src/ui/streamlit_app.py
git commit -m "chore: Trigger Streamlit Cloud redeploy"
git push origin main
```

## Verify the Fix

After redeploy, test the app with:
- Query: "houses in las vegas"
- Expected: Properties should be found without the FunctionTool error

## What Was Fixed

The fix refactored all MCP server tools to have:
1. Internal implementations (`_*_impl` functions)
2. MCP tool wrappers (`@mcp.tool()` decorated functions)
3. Direct callable versions (`*_direct` functions) for agents

Agents now use the `*_direct` versions which bypass the FunctionTool wrapper.

## Commit
The fix was committed with message:
```
fix: Resolve 'FunctionTool object is not callable' error
```

Check the commit history to verify it's deployed.

